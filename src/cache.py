"""
Cache implementation for Lichess API responses.
"""
from datetime import datetime, timedelta
import json
import os
import yaml
from typing import Dict, List, Tuple, Any, Optional

# Load cache TTL from config
CONFIG_PATH = os.path.join(os.getcwd(), "config", "config.yaml")
DEFAULT_CACHE_TTL = 15  # Default to 15 minutes if config not found

try:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f) or {}
    CACHE_TTL = config.get("performance", {}).get("cache", {}).get("ttl_minutes", DEFAULT_CACHE_TTL)
except Exception:
    CACHE_TTL = DEFAULT_CACHE_TTL

class LichessCache:
    """A simple cache for Lichess API responses to reduce API calls."""
    
    def __init__(self, cache_ttl_minutes: int = CACHE_TTL):
        """Initialize the cache with a TTL value.
        
        Args:
            cache_ttl_minutes: How long to cache responses, in minutes.
        """
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.team_tournaments: Dict[str, Tuple[datetime, List[Dict[str, Any]]]] = {}
        
    def get_tournaments(self, team_slug: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached tournaments for a team if available and not expired.
        
        Args:
            team_slug: The Lichess team slug.
            
        Returns:
            List of tournament data if cache valid, None if cache miss or expired.
        """
        if team_slug not in self.team_tournaments:
            return None
            
        timestamp, tournaments = self.team_tournaments[team_slug]
        if datetime.now() - timestamp > self.cache_ttl:
            # Cache expired
            return None
            
        return tournaments
        
    def set_tournaments(self, team_slug: str, tournaments: List[Dict[str, Any]]) -> None:
        """Store tournaments in cache with current timestamp.
        
        Args:
            team_slug: The Lichess team slug.
            tournaments: List of tournament data.
        """
        self.team_tournaments[team_slug] = (datetime.now(), tournaments)
        
    def invalidate(self, team_slug: str) -> None:
        """Invalidate cache for a specific team.
        
        Args:
            team_slug: The Lichess team slug.
        """
        if team_slug in self.team_tournaments:
            del self.team_tournaments[team_slug]
            
    def invalidate_all(self) -> None:
        """Clear the entire cache."""
        self.team_tournaments.clear()

# Singleton cache instance for use throughout the app
cache = LichessCache()
