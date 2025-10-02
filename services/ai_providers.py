# services/ai_providers.py (VERSIÓN CORREGIDA Y REFACTORIZADA)
import asyncio
import httpx
import logging
from config.motor_config import get_motor_config
from core.api_rotator import APIRotator

config = get_motor_config()

class AIProvider:
    def __init__(self, name: str):
        self.name = name
        if name not in config.AI_PROVIDER_CONFIG:
            raise ValueError(f"Configuración para el proveedor {name} no encontrada.")

        self.config = config.AI_PROVIDER_CONFIG[name]
        self.rotator = APIRotator(name, self.config['keys_env'])
        self.client = httpx.AsyncClient(timeout=self.config.get('timeout', 30))
        logging.info(f"{self.name} provider initialized.")

    async def generate_text(self, prompt: str, retries: int = 3):
        for attempt in range(retries):
            key = self.rotator.get_key()
            if not key:
                logging.error(f"No active keys available for {self.name}")
                return None

            try:
                response_content = await self._handle_request(prompt, key)
                if response_content:
                    self.rotator.mark_key_success(key)
                    return response_content
            except Exception as e:
                logging.error(f"Error with {self.name} key {key[:5]}...: {e}")
                self.rotator.mark_key_failed(key, str(e))

        logging.error(f"All retries failed for {self.name}")
        return None

    async def _handle_request(self, prompt: str, api_key: str):
        provider_map = {
            "Groq": self._call_openai_compatible,
            "Cohere": self._call_cohere,
            "HuggingFace": self._call_huggingface,
            "Gemini": self._call_gemini,
        }
        call_function = provider_map.get(self.name)
        if not call_function:
            raise NotImplementedError(f"Provider {self.name} call logic not implemented.")
        return await call_function(prompt, api_key)

    async def _call_openai_compatible(self, prompt: str, api_key: str):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": self.config['model'], "messages": [{"role": "user", "content": prompt}]}
        response = await self.client.post(self.config['url'], json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']

    async def _call_cohere(self, prompt: str, api_key: str):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {
            "model": self.config['model'],
            "messages": [{"role": "user", "content": prompt}]
        }
        response = await self.client.post(self.config['url'], json=data, headers=headers)
        response.raise_for_status()
        return response.json()['text']

    async def _call_huggingface(self, prompt: str, api_key: str):
        headers = {"Authorization": f"Bearer {api_key}"}
        url = f"{self.config['url']}/{self.config['model']}"
        data = {"inputs": prompt}
        response = await self.client.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()["generated_text"]

    async def _call_gemini(self, prompt: str, api_key: str):
        url = f"{self.config['url']}/{self.config['model']}:generateContent?key={api_key}"
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        response = await self.client.post(url, json=data)
        response.raise_for_status()
        return response.json()['candidates']['content']['parts']['text']

# Inicialización de servicios para ser importados en otras partes
groq = AIProvider("Groq")
cohere = AIProvider("Cohere")
huggingface = AIProvider("HuggingFace")
gemini = AIProvider("Gemini")
