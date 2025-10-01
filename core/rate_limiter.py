import os
import time
import redis
import asyncio # Added for asyncio.sleep
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv

from core.logging_config import get_logger, log_execution

logger = get_logger('rate_limiter')

# Load environment variables
load_dotenv()

class RateLimiter:
    """
    Implements a rate limiting mechanism for API providers using Redis for persistence.
    Supports configurable limits per minute, hour, and day, with exponential backoff.
    """
    def __init__(self, redis_client: redis.Redis, namespace: str = "rate_limiter"):
        self.redis = redis_client
        self.namespace = namespace
        self.limits: Dict[str, Dict[str, int]] = {} # {provider: {interval: limit}}
        self._load_limits_from_env()
        logger.info("RateLimiter initialized.")

    def _load_limits_from_env(self):
        """Loads rate limits for providers from environment variables."""
        providers = ['GROQ', 'COHERE', 'HUGGINGFACE', 'GEMINI']
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

# Initialize Redis client for RateLimiter
try:
    redis_url = os.getenv('REDIS_URL')

    if redis_url:
        # Usar Redis Cloud con REDIS_URL (default DB 0)
        redis_client_rate_limiter = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=10,
            retry_on_timeout=True,
            health_check_interval=30
        )
        logger.info("✅ Connected to Redis Cloud using REDIS_URL for Rate Limiter")
    else:
        # Fallback a Redis local (para desarrollo, default DB 0)
        redis_client_rate_limiter = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True
        )
        logger.info("✅ Connected to local Redis for Rate Limiter")

    # Test de conexión
    redis_client_rate_limiter.ping()
    REDIS_AVAILABLE_RATE_LIMITER = True
    logger.info("🎯 Redis Cloud connection successful for Rate Limiter persistence")

except Exception as e:
    REDIS_AVAILABLE_RATE_LIMITER = False
    logger.warning(f"⚠️ Redis Cloud not available for Rate Limiter: {str(e)[:200]}. Using in-memory fallback.")
    redis_client_rate_limiter = None

# Global instance of RateLimiter
rate_limiter = RateLimiter(redis_client_rate_limiter) if redis_client_rate_limiter else None
