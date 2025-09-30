import os
import logging
from supabase import create_client, Client
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env
load_dotenv()

class DatabaseService:
    """
    Servicio para interactuar con Supabase
    """
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        logger.info(f"Supabase URL loaded: {bool(self.supabase_url)}")
        logger.info(f"Supabase Key loaded: {bool(self.supabase_key)}")
        self.client: Optional[Client] = None
        self._initialize_client()

    def _initialize_client(self):
        """Inicializa el cliente de Supabase"""
        try:
            if not self.supabase_url or not self.supabase_key:
                logger.warning("Supabase URL or KEY not found in environment variables")
                return

            self.client = create_client(self.supabase_url, self.supabase_key)
            logger.info("✅ Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase client: {e}")

    def is_connected(self) -> bool:
        """Verifica si la conexión a Supabase está activa"""
        return self.client is not None

    async def save_article(self, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Guarda un artículo en la tabla 'articles'
        """
        if not self.is_connected():
            logger.error("Cannot save article - Supabase not connected")
            return None

        try:
            response = self.client.table('articles').insert(article_data).execute()
            logger.info(f"✅ Article saved to Supabase: {article_data.get('title')}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"❌ Error saving article to Supabase: {e}")
            return None

    async def save_video(self, video_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Guarda metadata de video en la tabla 'videos'
        """
        if not self.is_connected():
            logger.error("Cannot save video - Supabase not connected")
            return None

        try:
            response = self.client.table('videos').insert(video_data).execute()
            logger.info(f"✅ Video saved to Supabase: {video_data.get('title')}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"❌ Error saving video to Supabase: {e}")
            return None

    async def update_article_status(self, article_id: str, status: str) -> Optional[Dict[str, Any]]:
        """
        Actualiza el estado de un artículo en la tabla 'articles'
        """
        if not self.is_connected():
            logger.error("Cannot update article - Supabase not connected")
            return None

        try:
            response = self.client.table('articles').update({"status": status}).eq("id", article_id).execute()
            logger.info(f"✅ Article status updated to '{status}' for ID: {article_id}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"❌ Error updating article status: {e}")
            return None

# Instancia global para usar en todo el proyecto
db_service = DatabaseService()
