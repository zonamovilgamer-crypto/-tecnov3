import asyncio
import os
import sys
import logging
import datetime

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.database_service import db_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_supabase_connection():
    """Prueba la conexión y funcionalidad de Supabase"""

    logger.info("🧪 TESTEANDO CONEXIÓN SUPABASE")

    # 1. Verificar conexión
    if not db_service.is_connected():
        logger.error("❌ No hay conexión a Supabase")
        return False

    logger.info("✅ Cliente Supabase inicializado")

    # Crear timestamp único para evitar duplicados
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    # 2. Probar inserción de artículo de prueba
    test_article = {
        "title": f"Artículo de Prueba - {timestamp}",
        "content": "Este es un artículo de prueba para verificar que Supabase está funcionando correctamente con el motor autónomo.",
        "excerpt": "Prueba de conexión a base de datos",
        "slug": f"prueba-conexion-supabase-{timestamp}",
        "status": "draft",
        "source_type": "test",
        "author": "Sistema Automatizado",
        "word_count": 45,
        "reading_time": 1
    }

    try:
        saved_article = await db_service.save_article(test_article)
        if saved_article:
            logger.info(f"✅ Artículo guardado en Supabase - ID: {saved_article['id']}")
        else:
            logger.error("❌ No se pudo guardar el artículo")
            return False
    except Exception as e:
        logger.error(f"❌ Error guardando artículo: {e}")
        return False

    # 3. Probar inserción de video de prueba
    test_video = {
        "youtube_id": f"test_video_{timestamp}",
        "title": f"Video de Prueba - {timestamp}",
        "description": "Video de prueba para verificar conexión",
        "thumbnail_url": "https://example.com/thumbnail.jpg",
        "channel_title": "Canal de Prueba",
        "embed_url": "https://www.youtube.com/embed/test123",
        "query_used": "tecnología prueba"
    }

    try:
        saved_video = await db_service.save_video(test_video)
        if saved_video:
            logger.info(f"✅ Video guardado en Supabase - ID: {saved_video['id']}")
        else:
            logger.error("❌ No se pudo guardar el video")
            return False
    except Exception as e:
        logger.error(f"❌ Error guardando video: {e}")
        return False

    logger.info("🎉 ¡TODAS LAS PRUEBAS DE SUPABASE EXITOSAS!")
    return True

if __name__ == "__main__":
    logger.info("🔗 INICIANDO PRUEBA DE CONEXIÓN SUPABASE")
    success = asyncio.run(test_supabase_connection())

    if success:
        logger.info("🚀 Supabase configurado correctamente - Listo para producción")
    else:
        logger.error("💥 Prueba fallida - Revisa credenciales y conexión")
        sys.exit(1)
