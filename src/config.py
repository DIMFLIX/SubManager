"""
Configuration management module.
"""
import yaml
import logging
from pathlib import Path
from typing import Optional, Set, List, Dict, Any
import aiofiles

from .models import Config


logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or Path(__file__).parent.parent / ".env.yaml"
        self.config: Optional[Config] = None
        self.ban_lists: Dict[str, Set[str]] = {
            'never_follow': set(),
            'never_unfollow': set(),
            'ignore_completely': set()
        }
        
    async def load(self) -> Config:
        """
        Load configuration from YAML file asynchronously.
        
        Returns:
            Loaded configuration object
            
        Raises:
            FileNotFoundError: If configuration file doesn't exist
            yaml.YAMLError: If configuration file is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
        try:
            async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = yaml.safe_load(content)
            
            # Convert YAML structure to Config
            config_data = {
                'USERNAME': data['github']['username'],
                'TOKEN': data['github']['token'],
                'PROMOTION': data['promotion']['enabled'],
                'DAYS_PERIOD': data['promotion']['days_period'],
                'COUNT_PROMOTION_USERS': data['promotion']['count_users'],
                'RETRY_ON': data['settings'].get('retry_on_error', True)
            }
            
            self.config = Config.from_dict(config_data)
            
            # Load ban lists
            ban_lists = data.get('ban_lists', {})
            self.ban_lists['never_follow'] = set(ban_lists.get('never_follow') or [])
            self.ban_lists['never_unfollow'] = set(ban_lists.get('never_unfollow') or [])
            self.ban_lists['ignore_completely'] = set(ban_lists.get('ignore_completely') or [])
            
            logger.info(f"Configuration loaded from {self.config_path}")
            logger.info(f"Ban lists: {len(self.ban_lists['never_follow'])} never_follow, "
                       f"{len(self.ban_lists['never_unfollow'])} never_unfollow, "
                       f"{len(self.ban_lists['ignore_completely'])} ignore_completely")
            
            # Validate configuration
            self._validate_config()
            
            return self.config
            
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in configuration file: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing required configuration key: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
            
    def _validate_config(self):
        """Validate loaded configuration."""
        if not self.config:
            raise ValueError("Configuration not loaded")
            
        if not self.config.username:
            raise ValueError("USERNAME is required in configuration")
            
        if not self.config.token:
            raise ValueError("TOKEN is required in configuration")
            
        if self.config.token.startswith("ghp_") and len(self.config.token) != 40:
            logger.warning("GitHub token appears to be invalid format")
            
        if self.config.days_period < 1:
            raise ValueError("DAYS_PERIOD must be at least 1")
            
        if self.config.count_promotion_users < 0:
            raise ValueError("COUNT_PROMOTION_USERS cannot be negative")
            
    async def save(self, config: Optional[Config] = None):
        """
        Save configuration to YAML file asynchronously.
        
        Args:
            config: Configuration object to save (uses current if not provided)
        """
        if config:
            self.config = config
            
        if not self.config:
            raise ValueError("No configuration to save")
            
        data = {
            'github': {
                'username': self.config.username,
                'token': self.config.token
            },
            'promotion': {
                'enabled': self.config.promotion,
                'days_period': self.config.days_period,
                'count_users': self.config.count_promotion_users
            },
            'settings': {
                'retry_on_error': self.config.retry_on,
                'max_concurrent_requests': 5,
                'request_delay': 0.5,
                'batch_size': 5
            },
            'ban_lists': {
                'never_follow': sorted(list(self.ban_lists.get('never_follow', set()))),
                'never_unfollow': sorted(list(self.ban_lists.get('never_unfollow', set()))),
                'ignore_completely': sorted(list(self.ban_lists.get('ignore_completely', set())))
            },
            'logging': {
                'level': 'INFO',
                'file': 'subscription_manager.log'
            }
        }
        
        async with aiofiles.open(self.config_path, 'w', encoding='utf-8') as f:
            yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False)
            await f.write(yaml_content)
            
        logger.info(f"Configuration saved to {self.config_path}")
        
    def get(self) -> Config:
        """
        Get current configuration.
        
        Returns:
            Current configuration object
            
        Raises:
            ValueError: If configuration not loaded
        """
        if not self.config:
            raise ValueError("Configuration not loaded. Call load() first.")
        return self.config
        
    async def reload(self) -> Config:
        """
        Reload configuration from file.
        
        Returns:
            Reloaded configuration object
        """
        logger.info("Reloading configuration...")
        return await self.load()
    
    def get_ban_lists(self) -> Dict[str, Set[str]]:
        """
        Get ban lists.
        
        Returns:
            Dictionary with ban lists
        """
        return self.ban_lists
    
    def get_combined_ban_list_followers(self) -> Set[str]:
        """
        Get combined ban list for followers (never_follow + ignore_completely).
        
        Returns:
            Set of usernames to never follow
        """
        return self.ban_lists['never_follow'] | self.ban_lists['ignore_completely']
    
    def get_combined_ban_list_following(self) -> Set[str]:
        """
        Get combined ban list for following (never_unfollow).
        
        Returns:
            Set of usernames to never unfollow
        """
        return self.ban_lists['never_unfollow']


# Global configuration manager instance
config_manager = ConfigManager()
