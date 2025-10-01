# config/ai_config.py
import os

AI_PROVIDER_CONFIG = {
    "Groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant", # Updated to current supported model
        "keys_env": "GROQ_API_KEY" # Prefix for numbered keys
    },
    "Cohere": {
        "url": "https://api.cohere.ai/v1/chat", # ✅ URL Corregida
        "model": "command-r-08-2024",  # Updated to current live model
        "keys_env": "COHERE_API_KEY"
    },
    "HuggingFace": {
        "url": "https://api-inference.huggingface.co/models", # ✅ URL Base
        "model": "mistralai/Mistral-7B-Instruct-v0.2", # ✅ Modelo corregido
        "keys_env": "HUGGINGFACE_API_KEY"
    },
    "Gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models", # ✅ URL Base
        "model": "gemini-1.5-flash-latest", # ✅ Modelo corregido
        "keys_env": "GEMINI_API_KEY"
    }
}
