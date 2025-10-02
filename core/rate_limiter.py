import os # Keep os for getenv in _load_limits_from_env
import time
import asyncio # Added for asyncio.sleep
from typing import Dict, Optional, Tuple

from core.logging_config import get_logger, log_execution
from config.motor_config import get_motor_config
from providers.cache_provider import redis # Import the global redis client

logger = get_logger('rate_limiter')

config = get_motor_config()

class RateLimiter:
    """
    Implements a rate limiting mechanism for API providers using Redis for persistence.
    Supports configurable limits per minute, hour, and day, with exponential backoff.
    """
    def __init__(self, redis_client, namespace: str = "rate_limiter"): # Type hint changed as redis.Redis is not directly imported
        self.redis = redis_client
        self.namespace = namespace
        self.limits: Dict[str, Dict[str, int]] = {} # {provider: {interval: limit}}
        self._load_limits_from_env()
        logger.info("RateLimiter initialized.")

    def _load_limits_from_env(self):
        """Loads rate limits for providers from environment variables."""
        # Use AI_PROVIDER_CONFIG from motor_config to get provider names
        providers = [p.upper() for p in config.AI_PROVIDER_CONFIG.keys()]
        intervals = ['PER_MINUTE', 'PER_HOUR', 'PER_DAY']

        for provider in providers:
            self.limits[provider.lower()] = {}
            for interval in intervals:
                env_var_name = f"{provider}_RATE_LIMIT_{interval}"
                limit = os.getenv(env_var_name)
                if limit:
                    self.limits[provider.lower()][interval.lower()] = int(limit)
                    logger.debug(f"Loaded rate limit for {provider.lower()} {interval.lower()}: {limit}")
                else:
                    logger.debug(f"No rate limit configured for {provider.lower()} {interval.lower()}.")

    def _key(self, provider_name: str, interval: str) -> str:
        """Generates a Redis key for a given provider and interval."""
        return f"{self.namespace}:{provider_name}:{interval}:{int(time.time() // self._get_interval_seconds(interval))}"

    def _get_interval_seconds(self, interval: str) -> int:
        """Returns the duration of an interval in seconds."""
        if interval == 'per_minute':
            return 60
        elif interval == 'per_hour':
            return 3600
        elif interval == 'per_day':
            return 86400
        raise ValueError(f"Unknown interval: {interval}")

    @log_execution(logger_name='rate_limiter')
    def can_make_request(self, provider_name: str) -> bool:
        """
        Checks if a request can be made for the given provider without exceeding limits.
        """
        provider_name = provider_name.lower()
        if provider_name not in self.limits:
            logger.debug(f"No rate limits configured for provider '{provider_name}'. Allowing request.")
            return True

        current_time = int(time.time())
        for interval, limit in self.limits[provider_name].items():
            key = self._key(provider_name, interval)
            count = self.redis.get(key)
            current_count = int(count) if count else 0

            if current_count >= limit:
                logger.warning(f"Rate limit exceeded for '{provider_name}' ({interval}). Current: {current_count}, Limit: {limit}")
                return False
        return True

    @log_execution(logger_name='rate_limiter')
    async def wait_if_needed(self, provider_name: str, initial_backoff: float = 1.0, max_backoff: float = 60.0):
        """
        Waits if the rate limit for the given provider has been reached,
        using exponential backoff.
        """
        provider_name = provider_name.lower()
        if provider_name not in self.limits:
            return

        backoff_time = initial_backoff
        while not self.can_make_request(provider_name):
            logger.info(f"Rate limit hit for '{provider_name}'. Waiting for {backoff_time:.2f} seconds with exponential backoff.")
            await asyncio.sleep(backoff_time)
            backoff_time = min(backoff_time * 2, max_backoff) # Exponential backoff

    @log_execution(logger_name='rate_limiter')
    def record_request(self, provider_name: str):
        """
        Records a request for the given provider, incrementing counters in Redis.
        """
        provider_name = provider_name.lower()
        if provider_name not in self.limits:
            return

        for interval in self.limits[provider_name]:
            key = self._key(provider_name, interval)
            with self.redis.pipeline() as pipe:
                pipe.incr(key)
                pipe.expire(key, self._get_interval_seconds(interval)) # Set expiration for the current interval
                pipe.execute()
        logger.debug(f"Request recorded for '{provider_name}'.")

# Global instance of RateLimiter
# Use the redis client from the cache_provider
rate_limiter = RateLimiter(redis) if redis else None
