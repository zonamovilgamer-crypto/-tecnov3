import asyncio
import logging
import sys
import os

# Agregar el directorio raíz al path para imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tasks.orchestrator import HiveOrchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_full_pipeline():
    """Prueba el pipeline completo de generación de contenido tech"""

    # Keywords específicas para nicho tecnología
    tech_youtube_queries = [
        "inteligencia artificial 2025",
        "machine learning tutorial",
        "python programming",
        "startups tecnología",
        "herramientas desarrollo software"
    ]

    tech_news_sources = [
        "https://techcrunch.com",
        "https://www.theverge.com/tech",
        "https://www.wired.com/category/tech/"
    ]

    logger.info("🚀 INICIANDO PRUEBA DEL SISTEMA TECH")
    logger.info(f"YouTube queries: {tech_youtube_queries}")
    logger.info(f"News sources: {tech_news_sources}")

    try:
        # Inicializar orchestrator
        orchestrator = HiveOrchestrator()

        # Probar el pipeline
        await orchestrator.start_hive(tech_youtube_queries, tech_news_sources)

        logger.info("✅ PRUEBA INICIADA CORRECTAMENTE")
        logger.info("💡 El sistema está procesando en segundo plano con Celery")
        logger.info("📊 Revisa los logs de Celery para ver el progreso")

    except Exception as e:
        logger.error(f"❌ ERROR en la prueba: {e}")
        return False

    return True

if __name__ == "__main__":
    logger.info("🧪 EJECUTANDO PRUEBA DEL MOTOR AUTÓNOMO TECH")
    success = asyncio.run(test_full_pipeline())

    if success:
        logger.info("🎉 ¡PRUEBA EXITOSA! El sistema está funcionando")
        logger.info("🔄 Ahora puedes ejecutar el sistema completo con: python main.py")
    else:
        logger.error("💥 Prueba fallida - Revisa los errores arriba")
        sys.exit(1)
