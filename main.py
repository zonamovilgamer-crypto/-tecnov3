import socket
import subprocess
import sys
import time
import signal
import logging
import atexit
import redis # Added import for redis

# Tus imports existentes
from core.hive_manager import HiveManager
# ... otros imports

logger = logging.getLogger(__name__)

def check_redis_connection(host='localhost', port=6379, timeout=1):
    """Verifica si Redis está accesible"""
    try:
        # Use Redis Cloud URL for connection
        r = redis.Redis.from_url('redis://default:u9a41u5CkQMGnDlFqjqftE49xZMM7cZd@redis-19201.c8.us-east-1-3.ec2.redns.redis-cloud.com:19201')
        r.ping()
        return True
    except Exception as e:
        logger.debug(f"Redis check failed: {e}")
        return False

def start_redis_if_needed():
    """
    Verifica Redis y da instrucciones si no está corriendo.
    NO intenta iniciar automáticamente para evitar problemas de permisos.
    """
    logger.info("🔍 Checking Redis connection...")

    if check_redis_connection():
        logger.info("✅ Redis is running and accessible!")
        return True

    # Redis NO está corriendo
    logger.error("❌ Redis is NOT running!")
    logger.error("")
    logger.error("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.error("Please start Redis using ONE of these methods:")
    logger.error("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.error("")
    logger.error("📦 OPTION 1 - Docker (Recommended):")
    logger.error("   docker run -d -p 6379:6379 --name redis redis:alpine")
    logger.error("")
    logger.error("🐧 OPTION 2 - WSL (if installed):")
    logger.error("   wsl sudo service redis-server start")
    logger.error("")
    logger.error("🪟 OPTION 3 - Windows native:")
    logger.error("   Download Memurai: https://www.memurai.com/")
    logger.error("   OR run: redis-server.exe")
    logger.error("")
    logger.error("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.error("")
    logger.error("After starting Redis, run this script again.")

    sys.exit(1)

def wait_for_redis(max_attempts=10, delay=2):
    """Espera a que Redis esté disponible con reintentos"""
    logger.info("⏳ Waiting for Redis to be ready...")

    for attempt in range(1, max_attempts + 1):
        if check_redis_connection():
            logger.info(f"✅ Redis ready after {attempt} attempt(s)!")
            return True

        if attempt < max_attempts:
            logger.warning(f"Redis not ready yet. Retry {attempt}/{max_attempts} in {delay}s...")
            time.sleep(delay)

    logger.error(f"❌ Redis did not become available after {max_attempts} attempts")
    return False

# ======================================
# 🎯 AGREGAR ESTA CLASE COMPLETA AQUÍ
# ======================================
class CeleryManager:
    def __init__(self):
        self.worker_process = None
        self.beat_process = None

    def start_workers(self):
        """Inicia Celery worker y beat automáticamente"""
        logger.info("🚀 Starting Celery workers...")

        # Detectar pool según OS
        pool = "solo" if sys.platform == "win32" else "prefork"

        # Iniciar Celery worker
        self.worker_process = subprocess.Popen(
            [sys.executable, "-m", "celery", "-A", "core.celery_config",
             "worker", f"--pool={pool}", "--loglevel=info"]
        )
        logger.info(f"✅ Celery worker started (PID: {self.worker_process.pid})")

        # Iniciar Celery beat
        self.beat_process = subprocess.Popen(
            [sys.executable, "-m", "celery", "-A", "core.celery_config",
             "beat", "--loglevel=info"]
        )
        logger.info(f"✅ Celery beat started (PID: {self.beat_process.pid})")

        # Verificar
        self._wait_for_workers()

    def _wait_for_workers(self, timeout=30):
        """Verifica que workers estén ACTIVOS antes de continuar"""
        logger.info("⏳ Waiting for workers to be ready...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "celery", "-A", "core.celery_config",
                     "inspect", "active"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0 and "Error" not in result.stdout:
                    logger.info("✅ Celery workers are healthy and active!")
                    return True

            except subprocess.TimeoutExpired:
                logger.warning("Worker check timed out, retrying...")
            except Exception as e:
                logger.debug(f"Worker check failed: {e}")

            time.sleep(2)

        raise RuntimeError("❌ Celery workers failed to start within timeout!")

    def stop_workers(self):
        """Detiene workers gracefully"""
        logger.info("🛑 Stopping Celery workers...")

        if self.worker_process:
            self.worker_process.terminate()
            try:
                self.worker_process.wait(timeout=10)
                logger.info("✅ Worker stopped")
            except:
                self.worker_process.kill()
                logger.warning("⚠️ Worker forcefully killed")

        if self.beat_process:
            self.beat_process.terminate()
            try:
                self.beat_process.wait(timeout=10)
                logger.info("✅ Beat stopped")
            except:
                self.beat_process.kill()
                logger.warning("⚠️ Beat forcefully killed")

# ======================================
# 🎯 MODIFICAR TU CÓDIGO EXISTENTE
# ======================================

# Crear instancia global
celery_manager = CeleryManager()

def cleanup_handler(signum, frame):
    """Maneja shutdown graceful"""
    logger.info("🛑 Received shutdown signal, cleaning up...")
    celery_manager.stop_workers()
    sys.exit(0)

# Registrar handlers
signal.signal(signal.SIGTERM, cleanup_handler)
signal.signal(signal.SIGINT, cleanup_handler)
atexit.register(celery_manager.stop_workers)

if __name__ == "__main__":
    try:
        # PASO 1: Verificar Redis PRIMERO (crítico)
        start_redis_if_needed()

        # PASO 2: Esperar confirmación de que Redis está listo
        if not wait_for_redis():
            logger.error("Cannot start without Redis. Exiting.")
            sys.exit(1)

        # PASO 3: Iniciar Celery workers (código existente)
        celery_manager.start_workers()

        # PASO 4: Iniciar HiveManager (código existente)
        logger.info("Starting Hive system main application...")
        hive_manager = HiveManager()
        # Call the async start_system method using asyncio.run
        import asyncio
        asyncio.run(hive_manager.start_system())

        # PASO 5: Mantener sistema corriendo
        logger.info("✅ System fully operational. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("👋 Graceful shutdown initiated...")
        celery_manager.stop_workers()
        # Also shutdown HiveManager gracefully if it was started
        import asyncio
        asyncio.run(hive_manager.shutdown_system())
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        celery_manager.stop_workers()
        # Also shutdown HiveManager gracefully if it was started
        import asyncio
        asyncio.run(hive_manager.shutdown_system())
        sys.exit(1)
