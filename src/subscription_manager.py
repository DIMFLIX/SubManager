"""
Main subscription management module.
"""
import logging
import asyncio
from pathlib import Path
from typing import Set, Dict, List, Optional

from .models import Config, SubscriptionState
from .github_client import GitHubClient
from .promotion import PromotionManager
from .utils import batch_process


logger = logging.getLogger(__name__)


class SubscriptionManager:
    """Manages GitHub subscriptions with async operations."""
    
    def __init__(self, config: Config, config_manager=None):
        """
        Initialize subscription manager.
        
        Args:
            config: Application configuration
            config_manager: Configuration manager instance
        """
        self.config = config
        self.config_manager = config_manager
        self.client = GitHubClient(config.username, config.token)
        self.promotion_manager = PromotionManager(self.client, config)
        
        # File paths (kept for backward compatibility)
        self.base_path = Path(__file__).parent.parent
        
        self.state = SubscriptionState()
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
        
    async def load_ban_lists(self):
        """Load ban lists from configuration."""
        logger.info("Loading ban lists...")
        
        if not self.config_manager:
            raise ValueError("ConfigManager is required for loading ban lists")
        
        # Load from YAML config
        # ban_list_followers = users we should NOT follow (never_follow + ignore_completely)
        self.state.ban_list_followers = self.config_manager.get_combined_ban_list_followers()
        # ban_list_following = users we should NOT unfollow (never_unfollow)
        self.state.ban_list_following = self.config_manager.get_combined_ban_list_following()
        
        logger.info(f"Loaded {len(self.state.ban_list_followers)} users to never follow, {len(self.state.ban_list_following)} users to never unfollow")
        
    async def fetch_current_state(self):
        """Fetch current followers and following from GitHub."""
        logger.info("Fetching current subscription state from GitHub...")
        
        # Fetch followers and following concurrently
        followers_task = self.client.get_followers()
        following_task = self.client.get_following()
        
        followers, following = await asyncio.gather(followers_task, following_task)
        
        # Filter out banned users
        self.state.followers = set(followers) - self.state.ban_list_followers
        self.state.following = set(following) - self.state.ban_list_following
        
        logger.info(f"Current state: {len(self.state.followers)} followers, {len(self.state.following)} following")
        
    async def process_subscriptions(self):
        """Process subscriptions: follow/unfollow users."""
        logger.info("Processing subscriptions...")
        
        # Process promotion if enabled
        if self.config.promotion:
            updated_followers, updated_following = await self.promotion_manager.process_promotion(
                self.state.followers,
                self.state.following,
                self.state.ban_list_followers
            )
            self.state.followers = updated_followers
            self.state.following = updated_following
        
        # Calculate users to follow and unfollow
        users_to_follow = self.state.get_users_to_follow()
        users_to_unfollow = self.state.get_users_to_unfollow()
        
        logger.info(f"Users to follow: {len(users_to_follow)}, Users to unfollow: {len(users_to_unfollow)}")
        
        # Process follows and unfollows concurrently
        results = await asyncio.gather(
            self._process_follows(list(users_to_follow)),
            self._process_unfollows(list(users_to_unfollow)),
            return_exceptions=True
        )
        
        # Log any errors
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error during subscription processing: {result}")
                
    async def _process_follows(self, users: List[str]) -> Dict[str, bool]:
        """
        Process user follows with progress tracking.
        
        Args:
            users: List of users to follow
            
        Returns:
            Dictionary of results
        """
        if not users:
            return {}
            
        logger.info(f"Following {len(users)} users...")
        
        # Sort users for consistent ordering
        users = sorted(users)
        
        results = {}
        batch_size = 5  # Reduced batch size to avoid rate limiting
        delay = 1.5  # Increased delay between batches
        
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            
            # Follow users in batch with increased delay
            batch_results = await self.client.batch_follow(batch, delay=0.5)
            results.update(batch_results)
            
            # Log progress
            logger.info(f"Progress: {min(i + batch_size, len(users))}/{len(users)} users followed")
            
            # Delay between batches (except for last batch)
            if i + batch_size < len(users):
                await asyncio.sleep(delay)
                
        # Log summary
        successful = sum(1 for v in results.values() if v)
        logger.info(f"Successfully followed {successful}/{len(users)} users")
        
        return results
        
    async def _process_unfollows(self, users: List[str]) -> Dict[str, bool]:
        """
        Process user unfollows with progress tracking.
        
        Args:
            users: List of users to unfollow
            
        Returns:
            Dictionary of results
        """
        if not users:
            return {}
            
        logger.info(f"Unfollowing {len(users)} users...")
        
        # Sort users for consistent ordering
        users = sorted(users)
        
        results = {}
        batch_size = 5  # Reduced batch size to avoid rate limiting
        delay = 1.5  # Increased delay between batches
        
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            
            # Unfollow users in batch with increased delay
            batch_results = await self.client.batch_unfollow(batch, delay=0.5)
            results.update(batch_results)
            
            # Log progress
            logger.info(f"Progress: {min(i + batch_size, len(users))}/{len(users)} users unfollowed")
            
            # Delay between batches
            if i + batch_size < len(users):
                await asyncio.sleep(delay)
                
        # Log summary
        successful = sum(1 for v in results.values() if v)
        logger.info(f"Successfully unfollowed {successful}/{len(users)} users")
        
        return results
        
    async def run(self):
        """Run the complete subscription management process."""
        try:
            # Load ban lists
            await self.load_ban_lists()
            
            # Fetch current state from GitHub
            await self.fetch_current_state()
            
            # Process subscriptions
            await self.process_subscriptions()
            
            logger.info("Subscription management completed successfully")
            
        except Exception as e:
            logger.error(f"Error during subscription management: {e}")
            raise
            
        
    async def get_statistics(self) -> Dict[str, int]:
        """
        Get current statistics.
        
        Returns:
            Dictionary with statistics
        """
        await self.fetch_current_state()
        
        stats = {
            "followers": len(self.state.followers),
            "following": len(self.state.following),
            "mutual": len(self.state.followers & self.state.following),
            "not_following_back": len(self.state.following - self.state.followers),
            "not_followed_back": len(self.state.followers - self.state.following),
            "banned_followers": len(self.state.ban_list_followers),
            "banned_following": len(self.state.ban_list_following),
        }
        
        if self.config.promotion:
            promoted_users = await self.promotion_manager.check_and_update_promoted_users()
            stats["promoted_active"] = len(promoted_users[0])
            stats["promoted_expired"] = len(promoted_users[1])
            
        return stats
