"""
Utility functions for SubManager.
"""
import logging
import sys
from pathlib import Path
from typing import Set, List, Optional
from datetime import datetime
import asyncio
import aiofiles
import aiohttp

from .models import PromotedUser


# Setup logging
def setup_logging(log_file: Optional[Path] = None, level: int = logging.INFO):
    """
    Setup application logging.
    
    Args:
        log_file: Path to log file
        level: Logging level
    """
    log_file = log_file or Path(__file__).parent.parent / "subscription_manager.log"
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Console handler with simpler format
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


async def load_ban_list(file_path: Path) -> Set[str]:
    """
    Load ban list from file asynchronously.
    
    Args:
        file_path: Path to ban list file
        
    Returns:
        Set of banned usernames
    """
    if not file_path.exists():
        logging.info(f"Ban list file not found: {file_path}")
        return set()
        
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            ban_list = {line.strip() for line in content.splitlines() if line.strip()}
            logging.info(f"Loaded {len(ban_list)} entries from {file_path}")
            return ban_list
    except Exception as e:
        logging.error(f"Error loading ban list from {file_path}: {e}")
        return set()


async def save_ban_list(file_path: Path, ban_list: Set[str]):
    """
    Save ban list to file asynchronously.
    
    Args:
        file_path: Path to ban list file
        ban_list: Set of banned usernames
    """
    try:
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            content = '\n'.join(sorted(ban_list))
            await f.write(content)
        logging.info(f"Saved {len(ban_list)} entries to {file_path}")
    except Exception as e:
        logging.error(f"Error saving ban list to {file_path}: {e}")


async def load_promoted_users(file_path: Path) -> List[PromotedUser]:
    """
    Load promoted users from file asynchronously.
    
    Args:
        file_path: Path to promoted users file
        
    Returns:
        List of promoted users
    """
    if not file_path.exists():
        logging.info(f"Promoted users file not found: {file_path}")
        return []
        
    promoted_users = []
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            
        for line in content.splitlines():
            if not line.strip():
                continue
                
            try:
                # Format: "username YYYY-MM-DD"
                parts = line.rsplit(' ', 1)
                if len(parts) == 2:
                    username, date_str = parts
                    promotion_date = datetime.strptime(date_str.strip(), "%Y-%m-%d")
                    promoted_users.append(PromotedUser(username=username, promotion_date=promotion_date))
            except ValueError as e:
                logging.warning(f"Invalid promoted user entry: {line} - {e}")
                
        logging.info(f"Loaded {len(promoted_users)} promoted users from {file_path}")
        return promoted_users
        
    except Exception as e:
        logging.error(f"Error loading promoted users from {file_path}: {e}")
        return []


async def save_promoted_users(file_path: Path, promoted_users: List[PromotedUser]):
    """
    Save promoted users to file asynchronously.
    
    Args:
        file_path: Path to promoted users file
        promoted_users: List of promoted users
    """
    try:
        lines = []
        for user in promoted_users:
            date_str = user.promotion_date.strftime("%Y-%m-%d")
            lines.append(f"{user.username} {date_str}")
            
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            content = '\n'.join(lines)
            await f.write(content)
            
        logging.info(f"Saved {len(promoted_users)} promoted users to {file_path}")
    except Exception as e:
        logging.error(f"Error saving promoted users to {file_path}: {e}")


async def check_internet_connection() -> bool:
    """
    Check if internet connection is available.
    
    Returns:
        True if connected to internet
    """
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('https://github.com') as response:
                return response.status in [200, 301, 302]
    except aiohttp.ClientError as e:
        logging.warning(f"Connection check failed: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error checking connection: {e}")
        return False


def print_logo():
    """Print application logo."""
    logo = r"""
  _____       _    ___  ___                                  
 /  ___|     | |   |  \/  |                                  
 \ `--. _   _| |__ | .  . | __ _ _ __   __ _  __ _  ___ _ __ 
  `--. \ | | | '_ \| |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|
 /\__/ / |_| | |_) | |  | | (_| | | | | (_| | (_| |  __/ |   
 \____/ \__,_|_.__/\_|  |_|\__,_|_| |_|\__,_|\__, |\___|_|   
                                              __/ |          
                                             |___/           
_____________________________________________________________

  Enhanced with Async/Await for Lightning-Fast Performance ⚡
_____________________________________________________________          
    """
    print(logo)


class ProgressBar:
    """Simple progress bar for console output."""
    
    def __init__(self, total: int, prefix: str = "", width: int = 50):
        """
        Initialize progress bar.
        
        Args:
            total: Total number of items
            prefix: Prefix text
            width: Width of progress bar
        """
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0
        
    def update(self, current: int, suffix: str = ""):
        """
        Update progress bar.
        
        Args:
            current: Current item number
            suffix: Suffix text
        """
        self.current = current
        if self.total == 0:
            percent = 100
        else:
            percent = (current / self.total) * 100
            
        filled = int(self.width * current // max(self.total, 1))
        bar = '█' * filled + '░' * (self.width - filled)
        
        sys.stdout.write(f'\r{self.prefix} |{bar}| {percent:.1f}% {suffix}')
        sys.stdout.flush()
        
        if current >= self.total:
            print()  # New line when complete
            
    def increment(self, suffix: str = ""):
        """Increment progress by one."""
        self.update(self.current + 1, suffix)


async def batch_process(items: List, process_func, batch_size: int = 10, delay: float = 0.1):
    """
    Process items in batches with delay between batches.
    
    Args:
        items: List of items to process
        process_func: Async function to process each item
        batch_size: Number of items per batch
        delay: Delay between batches
        
    Returns:
        List of results
    """
    results = []
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_tasks = [process_func(item) for item in batch]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        results.extend(batch_results)
        
        # Delay between batches (except for the last batch)
        if i + batch_size < len(items):
            await asyncio.sleep(delay)
            
    return results
