# test_api.py (Debug for Cohere)
import os
import asyncio
import httpx
import logging
from dotenv import load_dotenv
from config.ai_config import AI_PROVIDER_CONFIG

async def test_cohere_detailed():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    API_KEY = os.getenv("COHERE_API_KEY_1")
    if not API_KEY:
        logging.error("No se encontró COHERE_API_KEY_1 en el archivo .env.")
        return

    # --- CONFIG FOR COHERE ---
    cohere_config = AI_PROVIDER_CONFIG["Cohere"]
    MODEL = cohere_config["model"]
    API_URL = cohere_config["url"]

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    data = {
        "model": MODEL,
        "message": "What is 2+2?"  # Use 'message' as string, not 'messages'
    }

    logging.info(f"--- Probando Cohere con el modelo: {MODEL} ---")
    logging.info(f"Request data: {data}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(API_URL, json=data, headers=headers)
            logging.info(f"Response status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                content = result.get('text', '')
                if content:
                    logging.info(f"✅ ¡ÉXITO! Respuesta:\n{content}")
                else:
                    logging.error(f"❌ FALLO (Formato): Respuesta inesperada. Respuesta: {result}")
            else:
                logging.error(f"❌ FALLO HTTP: {response.status_code}")
                logging.error(f"DETALLES DEL ERROR DE LA API: {response.text}")
    except httpx.HTTPStatusError as e:
        logging.error(f"❌ FALLO HTTP: {e.response.status_code}")
        logging.error(f"DETALLES DEL ERROR DE LA API: {e.response.text}")
    except Exception as e:
        logging.error(f"❌ FALLO INESPERADO: {e}")

if __name__ == "__main__":
    asyncio.run(test_cohere_detailed())
