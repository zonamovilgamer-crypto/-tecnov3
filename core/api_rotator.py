import os
import time
import logging
from typing import List, Optional

# Use basic logging; can integrate with core.logging_config later
logger = logging.getLogger('api_rotator')

class APIRotator:
    def __init__(self, service_name: str, keys_env: str):
        self.api_keys: List[str] = []
        for i in range(1, 4):  # Load up to 3 keys
            key = os.getenv(f"{keys_env}_{i}")
            if key:
                self.api_keys.append(key)
        if not self.api_keys:
            raise ValueError(f"No API keys found for {service_name} using prefix {keys_env}")
        self.service_name = service_name
        self.current_key_index = 0
        self.key_usage = {key: 0 for key in self.api_keys}
        self.failed_keys: dict[str, float] = {}  # key: timestamp
        logger.info(f"APIRotator initialized for {service_name} with {len(self.api_keys)} keys.")

    def get_key(self) -> Optional[str]:
        available_keys = [
            key for key in self.api_keys
            if key not in self.failed_keys or (time.time() - self.failed_keys[key] > 3600)
        ]
        if not available_keys:
            logger.warning(f"No active keys available for {self.service_name}")
            return None

        key = available_keys[self.current_key_index % len(available_keys)]
        self.current_key_index = (self.current_key_index + 1) % len(available_keys)
        self.key_usage[key] += 1
        logger.debug(f"Using key for {self.service_name}: {key[:5]}... (Usage: {self.key_usage[key]})")
        return key

    def mark_key_failed(self, key: str, reason: str = "unknown"):
        self.failed_keys[key] = time.time()
        logger.warning(f"API key {key[:5]}... for {self.service_name} marked as failed due to: {reason}. Will retry after 1 hour.")
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            logger.info(f"Rotated to next key for {self.service_name}.")

    def mark_key_success(self, key: str):
        if key in self.failed_keys:
            del self.failed_keys[key]
        logger.debug(f"Key {key[:5]}... for {self.service_name} marked as successful.")
