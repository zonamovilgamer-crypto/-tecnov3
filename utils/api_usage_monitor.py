import os
import redis
import time
import json
from typing import Dict, Any
from dotenv import load_dotenv

from core.logging_config import get_logger
from core.rate_limiter import RateLimiter

load_dotenv()
logger = get_logger('api_usage_monitor')

class APIUsageMonitor:
    """
    Monitors API usage for different providers and provides alerts when limits are approached.
    """
    def __init__(self):
        REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        try:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            logger.info("Successfully connected to Redis for API Usage Monitor.")
        except redis.exceptions.ConnectionError as e:
            logger.critical(f"Could not connect to Redis for API Usage Monitor: {e}. Monitoring will be limited.", exc_info=True)
            self.redis_client = None

        self.rate_limiter = RateLimiter(self.redis_client) if self.redis_client else None
        logger.info("APIUsageMonitor initialized.")

    def get_current_usage(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves the current API usage for all configured providers and intervals.
        """
        if not self.rate_limiter:
            logger.warning("RateLimiter not initialized. Cannot retrieve API usage.")
            return {}

        usage_data: Dict[str, Dict[str, Any]] = {}
        for provider, limits in self.rate_limiter.limits.items():
            usage_data[provider] = {}
            for interval, limit in limits.items():
                key = self.rate_limiter._key(provider, interval)
                count = self.redis_client.get(key) if self.redis_client else 0
                current_count = int(count) if count else 0

                usage_data[provider][interval] = {
                    "current_usage": current_count,
                    "limit": limit,
                    "percentage_used": (current_count / limit) * 100 if limit > 0 else 0
                }
        return usage_data

    def display_usage(self):
        """
        Prints the current API usage to the console.
        """
        usage = self.get_current_usage()
        if not usage:
            print("No API usage data available.")
            return

        print("\n--- API Usage Monitor ---")
        for provider, intervals in usage.items():
            print(f"\nProvider: {provider.upper()}")
            for interval, data in intervals.items():
                status = f"  - {interval.capitalize()}: {data['current_usage']}/{data['limit']} ({data['percentage_used']:.2f}%)"
                if data['percentage_used'] > 80:
                    status += " (ALERT: Approaching limit!)"
                    logger.warning(f"API usage for {provider} {interval} is approaching limit: {data['percentage_used']:.2f}%")
                print(status)

    def export_metrics_to_json(self, filename: str = "api_usage_metrics.json"):
        """
        Exports current API usage metrics to a JSON file.
        """
        usage = self.get_current_usage()
        if not usage:
            logger.warning("No API usage data to export.")
            return

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(usage, f, indent=4)
            logger.info(f"API usage metrics exported to {filename}")
            print(f"\nAPI usage metrics exported to {filename}")
        except IOError as e:
            logger.error(f"Failed to export API usage metrics to {filename}: {e}")
            print(f"\nError: Failed to export API usage metrics to {filename}: {e}")

if __name__ == "__main__":
    monitor = APIUsageMonitor()
    monitor.display_usage()
    monitor.export_metrics_to_json()
