import asyncio
import logging
import os # Keep os for subprocess.run
import time
import subprocess
import sys
from typing import List, Dict, Any, Optional

# Add the project root to sys.path to allow imports from motor_base
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.cache_provider import redis # Import the global redis client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HiveManager:
    """
    Manages the lifecycle and health of the entire agent hive system.
    Includes health checks for critical components and graceful shutdown.
    """
    def __init__(self):
        self.redis_client = redis # Use the global redis client from the provider
        logger.info("HiveManager initialized.")

    def _check_redis_health(self) -> bool:
        """Checks if the Redis server is reachable."""
        try:
            if not self.redis_client:
                logger.error("Redis client not initialized in HiveManager.")
                return False
            self.redis_client.ping()
            logger.info("Redis server is healthy.")
            return True
        except Exception as e: # Catch all exceptions for health check
            logger.error(f"Redis connection error: {e}")
            return False

    def _check_celery_worker_status(self) -> bool:
        """
        Checks if Celery workers are running. This is a basic check and can be improved
        by querying Celery's built-in monitoring tools (e.g., `celery inspect ping`).
        """
        python_executable = sys.executable
        try:
            # This command checks if any Celery worker is alive
            result = subprocess.run(
                [python_executable, "-m", "celery", "-A", "core.celery_config", "inspect", "ping"],
                capture_output=True, text=True, timeout=10
            )
            if "pong" in result.stdout:
                logger.info("Celery worker(s) detected and responsive.")
                return True
            else:
                logger.warning(f"No active Celery workers detected. Output: {result.stdout.strip()}")
                return False
        except FileNotFoundError:
            logger.error("Celery command not found. Is Celery installed and in PATH?")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("Celery inspect ping timed out. Workers might be unresponsive.")
            return False
        except Exception as e:
            logger.error(f"Error checking Celery worker status: {e}")
            return False

    def _check_celery_beat_status(self) -> bool:
        """
        Checks if Celery Beat is running. This is a heuristic check, as Beat doesn't
        have a direct 'ping' command like workers. We assume if Redis is up and
        workers are up, Beat should also be managed externally.
        For a more robust check, one might look for the beat schedule file lock.
        """
        # This is a placeholder. A robust check for Celery Beat is more involved.
        # For now, we'll rely on external monitoring or assume it's managed.
        logger.info("Celery Beat status check is a heuristic. Assuming external management.")
        return True # Assume Beat is running if Redis and workers are healthy

    def perform_health_check(self) -> bool:
        """Performs a comprehensive health check of the hive components."""
        logger.info("Performing comprehensive hive health check...")
        redis_ok = self._check_redis_health()
        celery_worker_ok = self._check_celery_worker_status()
        celery_beat_ok = self._check_celery_beat_status()

        if redis_ok and celery_worker_ok and celery_beat_ok:
            logger.info("All core hive components are healthy.")
            return True
        else:
            logger.error("One or more core hive components are unhealthy.")
            return False

    async def start_system(self):
        """Starts the overall hive system (primarily for logging and health checks)."""
        logger.info("Starting HiveManager system...")
        if self.perform_health_check():
            logger.info("Hive system started successfully. Monitoring active.")
        else:
            logger.error("Hive system started with unhealthy components. Please check logs.")

    async def shutdown_system(self):
        """Performs a graceful shutdown of the hive system."""
        logger.info("Initiating graceful shutdown of HiveManager system...")
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis client connection closed.")
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
        logger.info("HiveManager system shutdown complete.")

# Example usage (for testing purposes)
async def main():
    # This main is for testing HiveManager in isolation.
    # The actual main entry point will be in main.py
    manager = HiveManager()
    await manager.start_system()

    # Simulate some uptime
    logger.info("Simulating system uptime for 5 seconds...")
    await asyncio.sleep(5)

    await manager.shutdown_system()

if __name__ == "__main__":
    # Ensure REDIS_URL is set in environment or .env file for local testing
    # For this test, you might need to manually start a Redis server and Celery worker/beat
    # e.g., `redis-server`
    # `celery -A core.celery_config worker -l info -P eventlet`
    # `celery -A core.celery_config beat -l info`
    asyncio.run(main())
