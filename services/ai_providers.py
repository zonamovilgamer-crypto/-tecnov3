import os
import time
import logging
import random
from dotenv import load_dotenv
from typing import List, Dict, Optional, Any

# Configure logging FIRST
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import AI client libraries with graceful fallback
_GROQ_AVAILABLE = False
try:
    from groq import Groq
    _GROQ_AVAILABLE = True
except ImportError:
    logging.warning("Groq library not installed. GroqService will be unavailable. Please install with 'pip install groq'")

_COHERE_AVAILABLE = False
try:
    import cohere
    _COHERE_AVAILABLE = True
except ImportError:
    logging.warning("Cohere library not installed. CohereService will be unavailable. Please install with 'pip install cohere'")

_HUGGINGFACE_AVAILABLE = False
try:
    from huggingface_hub import InferenceClient
    _HUGGINGFACE_AVAILABLE = True
except ImportError:
    logging.warning("Hugging Face Hub library not installed. HuggingFaceService will be unavailable. Please install with 'pip install huggingface_hub'")

_GEMINI_AVAILABLE = False
try:
    import google.generativeai as genai
    _GEMINI_AVAILABLE = True
except ImportError:
    logging.warning("Google Generative AI library not installed. GeminiService will be unavailable. Please install with 'pip install google-generativeai'")

class APIRotator:
    """
    Manages rotation of API keys for a given service.
    Handles rate limits and provides automatic failover.
    """
    def __init__(self, api_keys: List[str], service_name: str):
        if not api_keys:
            raise ValueError(f"No API keys provided for {service_name}")
        self.api_keys = api_keys
        self.service_name = service_name
        self.current_key_index = 0
        self.key_usage: Dict[str, int] = {key: 0 for key in api_keys}
        self.failed_keys: Dict[str, float] = {} # Stores key and timestamp of failure
        logger.info(f"APIRotator initialized for {service_name} with {len(api_keys)} keys.")

    def get_key(self) -> str:
        """
        Returns the current active API key, rotating if necessary.
        Handles failed keys by temporarily blacklisting them.
        """
        available_keys = [key for key in self.api_keys if key not in self.failed_keys or (time.time() - self.failed_keys[key] > 3600)] # Blacklist for 1 hour
        if not available_keys:
            raise Exception(f"All {self.service_name} API keys are currently failed or rate-limited.")

        # Filter out keys that are currently failed
        active_keys = [key for key in self.api_keys if key not in self.failed_keys or (time.time() - self.failed_keys[key] > 3600)]
        if not active_keys:
            raise Exception(f"All {self.service_name} API keys are currently failed or rate-limited.")

        # Simple round-robin rotation among active keys
        key = active_keys[self.current_key_index % len(active_keys)]
        self.current_key_index = (self.current_key_index + 1) % len(active_keys)

        self.key_usage[key] += 1
        logger.debug(f"Using key for {self.service_name}: {key[:5]}... (Usage: {self.key_usage[key]})")
        return key

    def mark_key_failed(self, key: str, reason: str = "unknown"):
        """
        Marks an API key as failed, temporarily removing it from rotation.
        """
        self.failed_keys[key] = time.time()
        logger.warning(f"API key {key[:5]}... for {self.service_name} marked as failed due to: {reason}. Will retry after 1 hour.")
        # Attempt to rotate to the next key immediately
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            logger.info(f"Rotated to next key for {self.service_name}.")

class AIService:
    """Base class for AI services."""
    def __init__(self, service_name: str, api_keys_env_prefix: str, is_available: bool):
        self.service_name = service_name
        self._is_available = is_available
        self.api_keys = []
        self.rotator: Optional[APIRotator] = None
        self.delay_seconds = random.uniform(1, 3) # Delay between requests

        if not self._is_available:
            logger.warning(f"{service_name} is not available due to missing library or configuration.")
            return

        self.api_keys = self._load_api_keys(api_keys_env_prefix)
        if not self.api_keys:
            self._is_available = False
            logger.warning(f"No API keys found for {service_name}. {service_name} will be unavailable.")
            return

        self.rotator = APIRotator(self.api_keys, service_name)
        logger.info(f"{service_name} initialized with {len(self.api_keys)} keys.")

    @property
    def is_available(self) -> bool:
        return self._is_available and bool(self.api_keys)

    def _load_api_keys(self, prefix: str) -> List[str]:
        keys = []
        for i in range(1, 4): # Assuming 3 rotating keys
            key = os.getenv(f"{prefix}_{i}")
            if key:
                keys.append(key)
        return keys

    def generate_text(self, prompt: str, max_tokens: int = 200, **kwargs) -> Optional[str]:
        """Abstract method for text generation."""
        if not self.is_available:
            logger.error(f"Attempted to use unavailable service: {self.service_name}")
            return None
        raise NotImplementedError

    def _handle_request(self, func, *args, **kwargs) -> Optional[str]:
        """
        Handles API requests with key rotation, retries, and failover.
        """
        if not self.is_available or not self.rotator:
            logger.error(f"Cannot handle request for unavailable service: {self.service_name}")
            return None

        retries = len(self.api_keys) * 2 # Allow multiple retries across keys
        for i in range(retries):
            try:
                key = self.rotator.get_key()
            except Exception as e:
                logger.error(f"Failed to get an active key for {self.service_name}: {e}")
                return None # No active keys available

            try:
                time.sleep(self.delay_seconds) # Introduce delay
                result = func(key, *args, **kwargs)
                logger.info(f"Successfully generated text using {self.service_name} key {key[:5]}...")
                return result
            except Exception as e:
                logger.error(f"Error with {self.service_name} key {key[:5]}...: {e}")
                self.rotator.mark_key_failed(key, str(e))
                if i == retries - 1:
                    logger.error(f"All {self.service_name} keys failed after multiple retries.")
                    return None
                logger.info(f"Retrying with another {self.service_name} key...")
        return None

class GroqService(AIService):
    def __init__(self):
        super().__init__("Groq", "GROQ_API_KEY", _GROQ_AVAILABLE)
        self.client: Optional[Groq] = None

    def _get_client(self, api_key: str) -> Optional[Groq]:
        if not self.is_available:
            return None
        if not self.client or self.client.api_key != api_key:
            self.client = Groq(api_key=api_key)
        return self.client

    def generate_text(self, prompt: str, max_tokens: int = 200, model: str = "llama-3.2-1b-preview", **kwargs) -> Optional[str]:
        if not self.is_available:
            return None
        def _generate(key: str, prompt: str, max_tokens: int, model: str):
            client = self._get_client(key)
            if not client: return None
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "user", "content": prompt},
                ],
                model=model,
                max_tokens=max_tokens,
                **kwargs
            )
            return chat_completion.choices[0].message.content

        return self._handle_request(_generate, prompt, max_tokens, model)

class CohereService(AIService):
    def __init__(self):
        super().__init__("Cohere", "COHERE_API_KEY", _COHERE_AVAILABLE)
        self.client: Optional[cohere.Client] = None

    def _get_client(self, api_key: str) -> Optional[cohere.Client]:
        if not self.is_available:
            return None
        if not self.client or self.client.api_key != api_key:
            self.client = cohere.Client(api_key=api_key)
        return self.client

    def generate_text(self, prompt: str, max_tokens: int = 200, model: str = "command-r-08-2024", **kwargs) -> Optional[str]:
        if not self.is_available:
            return None
        def _generate(key: str, prompt: str, max_tokens: int, model: str):
            client = self._get_client(key)
            if not client: return None
            # Ensure Cohere uses chat API
            response = client.chat(
                message=prompt,
                max_tokens=max_tokens,
                model=model,
                **kwargs
            )
            return response.text

        return self._handle_request(_generate, prompt, max_tokens, model)

class HuggingFaceService(AIService):
    def __init__(self):
        super().__init__("HuggingFace", "HUGGINGFACE_API_KEY", _HUGGINGFACE_AVAILABLE)
        self.client: Optional[InferenceClient] = None

    def _get_client(self, api_key: str) -> Optional[InferenceClient]:
        if not self.is_available:
            return None
        if not self.client or self.client.token != api_key:
            self.client = InferenceClient(token=api_key)
        return self.client

    def generate_text(self, prompt: str, max_tokens: int = 200, model: str = "google/gemma-2-2b-it", **kwargs) -> Optional[str]:
        if not self.is_available:
            return None
        def _generate(key: str, prompt: str, max_tokens: int, model: str):
            client = self._get_client(key)
            if not client: return None
            # Hugging Face Inference API often requires specific input formats
            # For text generation, a simple prompt is usually sufficient.
            # The `max_new_tokens` parameter controls the output length.
            response = client.text_generation(
                prompt=prompt,
                model=model,
                max_new_tokens=max_tokens,
                **kwargs
            )
            return response

        return self._handle_request(_generate, prompt, max_tokens, model)

class GeminiService(AIService):
    def __init__(self):
        super().__init__("Gemini", "GEMINI_API_KEY", _GEMINI_AVAILABLE)
        self.client: Optional[Any] = None # Gemini client is configured globally

    def _get_client(self, api_key: str, model: str):
        if not self.is_available:
            return None
        # Gemini client is configured globally, so we re-configure it with the new key
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model) # Initialize with the specific model
        return self.client

    def generate_text(self, prompt: str, max_tokens: int = 200, model: str = "gemini-2.0-flash-exp", **kwargs) -> Optional[str]:
        if not self.is_available:
            return None
        def _generate(key: str, prompt: str, max_tokens: int, model: str):
            client = self._get_client(key, model) # Pass model to _get_client
            if not client: return None
            generation_config = {
                "max_output_tokens": max_tokens,
                **kwargs
            }
            response = client.generate_content(
                prompt,
                generation_config=generation_config
            )
            return response.text

        return self._handle_request(_generate, prompt, max_tokens, model)
