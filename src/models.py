"""
Data models for SubManager application.
"""
from dataclasses import dataclass, field
from typing import List, Set, Optional
from datetime import datetime


@dataclass
class Config:
    """Application configuration model."""
    username: str
    token: str
    promotion: bool = True
    days_period: int = 3
    count_promotion_users: int = 500
    retry_on: bool = True
    # Promotion discovery tuning
    seeds_count: int = 5           # how many random followers to use as seeds per run
    pages_per_seed: int = 2        # how many follower pages to sample per seed
    max_random_page: int = 5       # max page number to sample (GitHub paginates by 100)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """Create Config instance from dictionary."""
        return cls(
            username=data['USERNAME'],
            token=data['TOKEN'],
            promotion=data.get('PROMOTION', True),
            days_period=data.get('DAYS_PERIOD', 3),
            count_promotion_users=data.get('COUNT_PROMOTION_USERS', 500),
            retry_on=data.get('RETRY_ON', True),
            seeds_count=data.get('SEEDS_COUNT', 5),
            pages_per_seed=data.get('PAGES_PER_SEED', 2),
            max_random_page=data.get('MAX_RANDOM_PAGE', 5)
        )


@dataclass
class User:
    """GitHub user model."""
    username: str
    is_follower: bool = False
    is_following: bool = False
    promoted_date: Optional[datetime] = None
    
    def __hash__(self):
        return hash(self.username)
    
    def __eq__(self, other):
        if isinstance(other, User):
            return self.username == other.username
        return self.username == other


@dataclass
class PromotedUser:
    """Model for promoted users tracking."""
    username: str
    promotion_date: datetime
    
    def is_expired(self, days: int) -> bool:
        """Check if promotion period has expired."""
        delta = datetime.now() - self.promotion_date
        return delta.days > days


@dataclass
class SubscriptionState:
    """Current subscription state."""
    followers: Set[str] = field(default_factory=set)  # People who follow us
    following: Set[str] = field(default_factory=set)  # People we follow
    ban_list_followers: Set[str] = field(default_factory=set)  # Users to never follow (never_follow + ignore_completely)
    ban_list_following: Set[str] = field(default_factory=set)  # Users to never unfollow (never_unfollow)
    promoted_users: List[PromotedUser] = field(default_factory=list)
    
    def get_users_to_follow(self) -> Set[str]:
        """Get users that should be followed."""
        # Follow: followers who we're not following yet, excluding banned users
        return self.followers - self.following - self.ban_list_followers
    
    def get_users_to_unfollow(self) -> Set[str]:
        """Get users that should be unfollowed."""
        # Don't unfollow promoted users that are still active
        active_promoted = {u.username for u in self.promoted_users}
        # Unfollow: people we follow who don't follow us back, except never_unfollow list
        return (self.following - self.followers - active_promoted) - self.ban_list_following


@dataclass
class RateLimitInfo:
    """GitHub API rate limit information."""
    limit: int
    remaining: int
    reset_time: datetime
    
    @property
    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        return self.remaining == 0
    
    @property
    def seconds_until_reset(self) -> int:
        """Get seconds until rate limit reset."""
        delta = self.reset_time - datetime.now()
        return max(0, int(delta.total_seconds()))
