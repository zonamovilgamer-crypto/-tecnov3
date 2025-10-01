import socket
import subprocess
import sys
import time
import signal
import logging
import atexit
import os # Added import for os
import redis # Added import for redis

# Tus imports existentes
from core.hive_manager import HiveManager
# ... otros imports

logger = logging.getLogger(__name__)

def check_redis_connection(host='localhost', port=6379, timeout=1):
    """Verifica si Redis está accesible"""
    try:
        # Use Redis Cloud URL for connection
        r = redis.Redis.from_url('redis://default:59UGKSDD5Zh6SyBBpnEZXdu72Z64gd4U@redis-12790.c325.us-east-1-4.ec2.redns.redis-cloud.com:12790')
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
             "worker", f"--pool={pool}", "--loglevel=info"],
            env=os.environ # Pass current environment
        )
        logger.info(f"✅ Celery worker started (PID: {self.worker_process.pid})")

        # Iniciar Celery beat
        self.beat_process = subprocess.Popen(
            [sys.executable, "-m", "celery", "-A", "core.celery_config",
             "beat", "--loglevel=debug"],
            env=os.environ # Pass current environment
        )
        logger.info(f"✅ Celery beat started (PID: {self.beat_process.pid})")

        # Verificar
        self._wait_for_workers()

    def _wait_for_workers(self, timeout=120):
        """Verificación robusta con diagnóstico completo"""
        logger.info("🔍 Iniciando diagnóstico completo de workers...")
        start_time = time.time()

        for attempt in range(1, 13):  # 12 intentos (2 minutos total)
            elapsed = time.time() - start_time
            logger.info(f"📊 Intento {attempt}/12 - Tiempo transcurrido: {elapsed:.1f}s")

            try:
                # PRUEBA 1: Comando ping básico
                result = subprocess.run(
                    [sys.executable, "-m", "celery", "-A", "core.celery_config", "inspect", "ping"],
                    capture_output=True, text=True, timeout=15
                )

                logger.info(f"   Status: {result.returncode} | Output: {result.stdout.strip()}")

                if result.returncode == 0 and "pong" in result.stdout.lower():
                    logger.info("✅ WORKERS VERIFICADOS: Respondiendo correctamente")
                    return True

                # PRUEBA 2: Stats detallados si ping falla
                if result.returncode != 0:
                    logger.warning(f"   Ping falló, intentando stats...")
                    stats_result = subprocess.run(
                        [sys.executable, "-m", "celery", "-A", "core.celery_config", "inspect", "stats"],
                        capture_output=True, text=True, timeout=15
                    )
                    logger.info(f"   Stats status: {stats_result.returncode}")

            except subprocess.TimeoutExpired:
                logger.warning(f"   ⏱️ Timeout en verificación")
            except Exception as e:
                logger.warning(f"   ❌ Error en verificación: {str(e)}")

            # Diagnóstico intermedio cada 3 intentos
            if attempt % 3 == 0:
                self._intermediate_diagnosis(attempt)

            time.sleep(10)  # 10 segundos entre intentos

        # DIAGNÓSTICO FINAL COMPLETO
        logger.error("❌ DIAGNÓSTICO FINAL - Workers no responden después de 2 minutos")
        self._comprehensive_diagnosis()
        raise RuntimeError("Celery workers failed comprehensive health check")

    def _intermediate_diagnosis(self, attempt):
        """Diagnóstico intermedio cada 3 intentos"""
        logger.info(f"   🩺 Diagnóstico intermedio (intento {attempt})...")

        # Verificar procesos en sistema
        try:
            if sys.platform == "win32":
                proc_result = subprocess.run(["tasklist"], capture_output=True, text=True)
            else:
                proc_result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

            celery_processes = [line for line in proc_result.stdout.split('\n') if 'celery' in line.lower()]
            logger.info(f"   📋 Procesos Celery encontrados: {len(celery_processes)}")
            for proc in celery_processes[:2]:  # Mostrar primeros 2
                logger.info(f"     → {proc.strip()}")

        except Exception as e:
            logger.warning(f"   ⚠️ No se pudo verificar procesos: {e}")

    def _comprehensive_diagnosis(self):
        """Diagnóstico final exhaustivo"""
        logger.error("🩺 DIAGNÓSTICO EXHAUSTIVO INICIADO:")

        # 1. Verificar conexión Redis
        logger.error("   1. 🔗 Verificando conexión Redis...")
        try:
            import redis
            r = redis.Redis.from_url('redis://default:59UGKSDD5Zh6SyBBpnEZXdu72Z64gd4U@redis-12790.c325.us-east-1-4.ec2.redns.redis-cloud.com:12790')
            r.ping()
            logger.error("      ✅ Redis: CONEXIÓN OK")
        except Exception as e:
            logger.error(f"      ❌ Redis: FALLÓ - {e}")

        # 2. Verificar configuración Celery
        logger.error("   2. ⚙️ Verificando configuración Celery...")
        try:
            config_test = subprocess.run(
                [sys.executable, "-c", "\"from core.celery_config import app; print('Config loaded')\""],
                capture_output=True, text=True, timeout=10, shell=True
            )
            logger.error(f"      ✅ Configuración: {config_test.stdout.strip()}")
        except Exception as e:
            logger.error(f"      ❌ Configuración: FALLÓ - {e}")

        # 3. Verificar procesos finales
        logger.error("   3. 📊 Estado final de procesos...")
        try:
            if sys.platform == "win32":
                final_procs = subprocess.run(["tasklist", "/fi", "imagename eq python.exe"],
                                           capture_output=True, text=True)
            else:
                final_procs = subprocess.run(["ps", "aux"], capture_output=True, text=True)

            celery_count = len([line for line in final_procs.stdout.split('\n') if 'celery' in line.lower()])
            logger.error(f"      📋 Procesos Celery activos: {celery_count}")
        except Exception as e:
            logger.error(f"      ⚠️ No se pudo contar procesos: {e}")

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
        # Ensure hive_manager is defined before attempting to shut it down
        if 'hive_manager' in locals() and hive_manager:
            import asyncio
            asyncio.run(hive_manager.shutdown_system())
        sys.exit(1)
