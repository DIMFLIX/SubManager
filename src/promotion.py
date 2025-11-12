"""
Promotion module for finding and managing new users to follow.
"""
import logging
import asyncio
from typing import List, Set, Dict
from datetime import datetime
from pathlib import Path

from .models import PromotedUser, Config
from .github_client import GitHubClient
from .utils import load_promoted_users, save_promoted_users


logger = logging.getLogger(__name__)


class PromotionManager:
    """Manages user promotion for expanding network."""
    
    def __init__(self, client: GitHubClient, config: Config):
        """
        Initialize promotion manager.
        
        Args:
            client: GitHub API client
            config: Application configuration
        """
        self.client = client
        self.config = config
        self.promoted_users_file = Path(__file__).parent.parent / "promoted_users.txt"
        
    async def find_users_to_promote(
        self,
        current_followers: Set[str],
        ban_list: Set[str],
        count: int,
        max_depth: int = 2
    ) -> List[str]:
        """
        Find new users to promote (follow) based on a random follower's network.
        
        This picks a random user from your followers and explores their followers
        to find potential users to follow back.
        
        Args:
            current_followers: Set of your current followers
            ban_list: Set of users to exclude
            count: Number of users to find
            max_depth: Maximum depth to search (1 = direct followers, 2 = followers of followers)
            
        Returns:
            List of usernames to promote
        """
        import random
        
        logger.info(f"Starting promotion search for {count} users from a random follower")
        
        promoted = []
        visited = set()
        excluded = ban_list | current_followers | {self.config.username}
        
        # Pick several random followers as seeds (if available)
        followers_list = list(current_followers)
        if not followers_list:
            logger.info("No followers available to seed promotion search")
            return []
        
        seeds_count = min(self.config.seeds_count, len(followers_list))  # number of random seeds per run
        random.shuffle(followers_list)
        queue = followers_list[:seeds_count]
        current_depth = 0
        
        while queue and len(promoted) < count and current_depth < max_depth:
            # Process current level
            next_level = []
            
            # Batch process users at current level
            batch_size = 3  # Process 3 users concurrently (reduced to avoid rate limiting)
            
            for i in range(0, len(queue), batch_size):
                batch = queue[i:i + batch_size]
                
                # Skip already visited users
                batch = [u for u in batch if u not in visited]
                if not batch:
                    continue
                    
                visited.update(batch)
                
                # Get followers for batch of users concurrently
                try:
                    # For each seed, pick random follower pages to diversify results
                    max_random_page = max(1, int(self.config.max_random_page))  # heuristic upper bound; empty pages are skipped
                    pages_per_seed = max(1, int(self.config.pages_per_seed))   # how many different pages to sample per seed
                    pages_map = {
                        u: sorted({p for p in random.sample(range(1, max_random_page + 1), k=min(pages_per_seed, max_random_page))})
                        for u in batch
                    }
                    followers_dict = await self.client.get_followers_batch(
                        batch,
                        pages_map=pages_map
                    )
                    
                    for username, followers in followers_dict.items():
                        for follower in followers:
                            if follower not in excluded and follower not in promoted:
                                promoted.append(follower)
                                
                                if len(promoted) >= count:
                                    break
                                    
                            # Add to next level if we need to go deeper
                            if current_depth + 1 < max_depth:
                                next_level.append(follower)
                                
                        if len(promoted) >= count:
                            break
                            
                except Exception as e:
                    logger.warning(f"Error getting followers for batch: {e}")
                    
                if len(promoted) >= count:
                    break
                    
                # Increased delay between batches to avoid rate limiting
                await asyncio.sleep(1.0)
                
            # Move to next depth level
            queue = next_level[:50]  # Limit queue size to reduce API calls
            current_depth += 1
            
        logger.info(f"Found {len(promoted)} users to promote")
        
        return promoted[:count]
        
    async def check_and_update_promoted_users(self) -> tuple[List[str], List[str]]:
        """
        Check promoted users and separate active from expired.
        
        Returns:
            Tuple of (active_promoted_users, expired_promoted_users)
        """
        promoted_users = await load_promoted_users(self.promoted_users_file)
        
        active = []
        expired = []
        
        for user in promoted_users:
            if user.is_expired(self.config.days_period):
                expired.append(user.username)
            else:
                active.append(user.username)
                
        logger.info(f"Promoted users: {len(active)} active, {len(expired)} expired")
        
        # Update the file with only active users
        active_promoted = [u for u in promoted_users if not u.is_expired(self.config.days_period)]
        await save_promoted_users(self.promoted_users_file, active_promoted)
        
        return active, expired
        
    async def add_promoted_users(self, usernames: List[str]):
        """
        Add new promoted users to tracking.
        
        Args:
            usernames: List of usernames to add
        """
        if not usernames:
            return
            
        # Load existing promoted users
        existing = await load_promoted_users(self.promoted_users_file)
        existing_usernames = {u.username for u in existing}
        
        # Add new users
        now = datetime.now()
        for username in usernames:
            if username not in existing_usernames:
                existing.append(PromotedUser(username=username, promotion_date=now))
                
        # Save updated list
        await save_promoted_users(self.promoted_users_file, existing)
        logger.info(f"Added {len(usernames)} new promoted users")
        
    async def process_promotion(
        self,
        current_followers: Set[str],
        current_following: Set[str],
        ban_list: Set[str]
    ) -> tuple[Set[str], Set[str]]:
        """
        Process promotion logic and return updated follower/following sets.
        
        Args:
            current_followers: Current followers set
            current_following: Current following set
            ban_list: Ban list
            
        Returns:
            Tuple of (updated_followers, updated_following)
        """
        if not self.config.promotion:
            logger.info("Promotion is disabled")
            return current_followers, current_following
            
        logger.info("Processing promotion...")
        
        # Check existing promoted users
        active_promoted, expired_promoted = await self.check_and_update_promoted_users()
        
        # Add active promoted to followers (so we don't unfollow them)
        updated_followers = current_followers | set(active_promoted)
        
        # Remove expired promoted from following (they will be unfollowed)
        updated_following = current_following - set(expired_promoted)
        
        # Find new users to promote if needed
        current_promoted_count = len(active_promoted)
        needed_count = self.config.count_promotion_users - current_promoted_count
        
        if needed_count > 0:
            logger.info(f"Need to find {needed_count} new users to promote")
            
            new_promoted = await self.find_users_to_promote(
                current_followers,
                ban_list,
                needed_count,
                max_depth=1
            )
            
            if new_promoted:
                # Add new promoted users to tracking
                await self.add_promoted_users(new_promoted)
                
                # Add to followers set (so we follow them)
                updated_followers.update(new_promoted)
                
                logger.info(f"Added {len(new_promoted)} new users for promotion")
        else:
            logger.info(f"Already have {current_promoted_count} promoted users, no new ones needed")
            
        return updated_followers, updated_following
