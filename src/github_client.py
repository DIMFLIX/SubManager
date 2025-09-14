"""
Asynchronous GitHub API client for efficient user data fetching.
"""
import asyncio
import logging
from typing import List, Set, Optional, Dict, Any
from datetime import datetime
import aiohttp
from aiohttp import ClientSession, ClientError, ClientResponseError

from .models import RateLimitInfo, User


logger = logging.getLogger(__name__)


class GitHubClient:
    """Asynchronous GitHub API client."""
    
    BASE_URL = "https://api.github.com"
    PER_PAGE = 100  # Maximum items per page for GitHub API
    
    def __init__(self, username: str, token: str, max_concurrent: int = 10):
        """
        Initialize GitHub client.
        
        Args:
            username: GitHub username
            token: GitHub personal access token
            max_concurrent: Maximum concurrent requests
        """
        self.username = username
        self.token = token
        self.auth = aiohttp.BasicAuth(username, token)
        self.session: Optional[ClientSession] = None
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limit: Optional[RateLimitInfo] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = ClientSession(auth=self.auth)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an API request with rate limiting and retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            Response JSON data
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        async with self.semaphore:
            max_retries = 3
            retry_delay = 1
            
            for attempt in range(max_retries):
                try:
                    async with self.session.request(method, url, **kwargs) as response:
                        # Update rate limit info
                        if 'X-RateLimit-Limit' in response.headers:
                            self.rate_limit = RateLimitInfo(
                                limit=int(response.headers.get('X-RateLimit-Limit', 0)),
                                remaining=int(response.headers.get('X-RateLimit-Remaining', 0)),
                                reset_time=datetime.fromtimestamp(
                                    int(response.headers.get('X-RateLimit-Reset', 0))
                                )
                            )
                        
                        # Handle rate limiting
                        if response.status == 429:
                            if self.rate_limit:
                                wait_time = self.rate_limit.seconds_until_reset + 1
                                logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                                await asyncio.sleep(wait_time)
                                continue
                        
                        response.raise_for_status()
                        
                        # Return JSON for API endpoints
                        if response.content_type == 'application/json':
                            return await response.json()
                        return {}
                        
                except ClientResponseError as e:
                    if e.status in [502, 503, 504] and attempt < max_retries - 1:
                        logger.warning(f"Server error {e.status}. Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    raise
                except ClientError as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Connection error: {e}. Retrying...")
                        await asyncio.sleep(retry_delay)
                        continue
                    raise
                    
    async def get_followers(
        self, 
        username: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> List[str]:
        """
        Get list of followers for a user.
        
        Args:
            username: GitHub username (defaults to authenticated user)
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of follower usernames
        """
        username = username or self.username
        followers = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                break
                
            params = {'per_page': self.PER_PAGE, 'page': page}
            data = await self._make_request(
                'GET',
                f'/users/{username}/followers',
                params=params
            )
            
            if not data:
                break
                
            followers.extend([user['login'] for user in data])
            
            # If we got less than PER_PAGE items, we've reached the end
            if len(data) < self.PER_PAGE:
                break
                
            page += 1
            
        logger.info(f"Fetched {len(followers)} followers for {username}")
        return followers
        
    async def get_following(
        self, 
        username: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> List[str]:
        """
        Get list of users that a user is following.
        
        Args:
            username: GitHub username (defaults to authenticated user)
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of following usernames
        """
        username = username or self.username
        following = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                break
                
            params = {'per_page': self.PER_PAGE, 'page': page}
            data = await self._make_request(
                'GET',
                f'/users/{username}/following',
                params=params
            )
            
            if not data:
                break
                
            following.extend([user['login'] for user in data])
            
            if len(data) < self.PER_PAGE:
                break
                
            page += 1
            
        logger.info(f"Fetched {len(following)} following for {username}")
        return following
        
    async def follow_user(self, username: str) -> bool:
        """
        Follow a user.
        
        Args:
            username: Username to follow
            
        Returns:
            True if successful
        """
        try:
            await self._make_request('PUT', f'/user/following/{username}')
            logger.info(f"Successfully followed {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to follow {username}: {e}")
            return False
            
    async def unfollow_user(self, username: str) -> bool:
        """
        Unfollow a user.
        
        Args:
            username: Username to unfollow
            
        Returns:
            True if successful
        """
        try:
            await self._make_request('DELETE', f'/user/following/{username}')
            logger.info(f"Successfully unfollowed {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to unfollow {username}: {e}")
            return False
            
    async def is_following(self, username: str) -> bool:
        """
        Check if authenticated user is following a specific user.
        
        Args:
            username: Username to check
            
        Returns:
            True if following
        """
        try:
            await self._make_request('GET', f'/user/following/{username}')
            return True
        except ClientResponseError as e:
            if e.status == 404:
                return False
            raise
            
    async def batch_follow(self, usernames: List[str], delay: float = 0.3) -> Dict[str, bool]:
        """
        Follow multiple users concurrently.
        
        Args:
            usernames: List of usernames to follow
            delay: Delay between requests to avoid rate limiting
            
        Returns:
            Dictionary mapping username to success status
        """
        results = {}
        tasks = []
        
        for username in usernames:
            task = self.follow_user(username)
            tasks.append(task)
            await asyncio.sleep(delay)
            
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for username, response in zip(usernames, responses):
            if isinstance(response, Exception):
                logger.error(f"Error following {username}: {response}")
                results[username] = False
            else:
                results[username] = response
                
        return results
        
    async def batch_unfollow(self, usernames: List[str], delay: float = 0.3) -> Dict[str, bool]:
        """
        Unfollow multiple users concurrently.
        
        Args:
            usernames: List of usernames to unfollow
            delay: Delay between requests to avoid rate limiting
            
        Returns:
            Dictionary mapping username to success status
        """
        results = {}
        tasks = []
        
        for username in usernames:
            task = self.unfollow_user(username)
            tasks.append(task)
            await asyncio.sleep(delay)
            
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for username, response in zip(usernames, responses):
            if isinstance(response, Exception):
                logger.error(f"Error unfollowing {username}: {response}")
                results[username] = False
            else:
                results[username] = response
                
        return results
        
    async def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed user information.
        
        Args:
            username: GitHub username
            
        Returns:
            User information dictionary
        """
        try:
            return await self._make_request('GET', f'/users/{username}')
        except Exception as e:
            logger.error(f"Failed to get user info for {username}: {e}")
            return None
            
    async def get_followers_batch(self, usernames: List[str], max_pages: int = 1) -> Dict[str, List[str]]:
        """
        Get followers for multiple users concurrently.
        
        Args:
            usernames: List of usernames
            max_pages: Maximum pages per user
            
        Returns:
            Dictionary mapping username to list of followers
        """
        tasks = [
            self.get_followers(username, max_pages=max_pages)
            for username in usernames
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        followers_dict = {}
        for username, result in zip(usernames, results):
            if isinstance(result, Exception):
                logger.error(f"Error getting followers for {username}: {result}")
                followers_dict[username] = []
            else:
                followers_dict[username] = result
                
        return followers_dict
