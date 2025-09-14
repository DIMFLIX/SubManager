"""
SubManager - Async GitHub Subscription Manager
"""

__version__ = "2.0.0"
__author__ = "DIMFLIX"

from .models import Config, User, PromotedUser, SubscriptionState, RateLimitInfo
from .config import ConfigManager, config_manager
from .github_client import GitHubClient
from .subscription_manager import SubscriptionManager
from .promotion import PromotionManager
from .utils import setup_logging, print_logo, check_internet_connection

__all__ = [
    "Config",
    "User",
    "PromotedUser",
    "SubscriptionState",
    "RateLimitInfo",
    "ConfigManager",
    "config_manager",
    "GitHubClient",
    "SubscriptionManager", 
    "PromotionManager",
    "setup_logging",
    "print_logo",
    "check_internet_connection",
]
