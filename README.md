# Motor Hive v2.0

Sistema autónomo de generación de contenido con IA y procesamiento distribuido.

## 🚀 Características

- Procesamiento distribuido con Celery + Redis
- Rotación automática de múltiples API keys (3 por proveedor)
- 4 proveedores de IA: Groq, Cohere, HuggingFace, Gemini
- Circuit breaker y rate limiting integrados
- Arquitectura de 3 colas especializadas (scraper, writer, publisher)
- Inicio automático de workers con un solo comando

## 📋 Prerrequisitos

- Python 3.11 o superior
- Redis (Memurai en Windows, Docker en Linux/Mac)
- Git

## 🔧 Instalación

### 1. Clonar repositorio
```bash
git clone https://github.com/zonamovilgamer-crypto/-tecnov3.git
cd -tecnov3
```
### 2. Crear entorno virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```
### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```
### 4. Configurar variables de entorno
```bash
# Copiar template
cp .env.example .env

# Editar .env con tus API keys
# Ver .env.example para enlaces de registro
```
### 5. Iniciar Redis
```bash
# Windows (Memurai)
# Descargar de: https://www.memurai.com/

# Docker
docker run -d -p 6379:6379 redis:alpine
```
### 6. Ejecutar
```bash
python main.py
```
Output esperado:
```
✅ Redis is running and accessible!
✅ Celery worker started
✅ Celery beat started
✅ System fully operational. Press Ctrl+C to stop.
```

## 🏗️ Arquitectura
```
Frontend (Vercel)
      ↓
   FastAPI
      ↓
    Redis (Broker)
      ↓
Celery Workers (4 concurrent)
      ↓
┌──────────┬──────────┬──────────┐
│ Scraper  │  Writer  │Publisher │
│  Queue   │  Queue   │  Queue   │
└──────────┴──────────┴──────────┘
      ↓
  Supabase (PostgreSQL + Storage)
```

## 📝 Variables de entorno
Ver `.env.example` para lista completa y enlaces de registro.
Requeridas:

*   API keys de al menos 1 proveedor de IA (Groq, Cohere, HuggingFace, o Gemini)
*   `REDIS_URL` (default: `localhost:6379`)
*   `SUPABASE_URL` y `SUPABASE_KEY`

## 🚢 Deploy a Producción
### Railway

*   Conectar repositorio en Railway
*   Agregar servicio Redis en Railway
*   Configurar variables de entorno desde `.env.example`
*   Start Command: `python main.py`
*   Deploy automático

### Vercel (Frontend)
*   Conectar repositorio del frontend y configurar variables.

## 📚 Estructura del proyecto
```
-tecnov3/
├── agents/           # Agentes de IA (scraper, writer, publisher)
├── core/            # Configuración central (Celery, logging, circuit breaker)
├── tasks/           # Tareas de Celery (orchestrator)
├── services/        # Servicios externos (scrapers, AI providers)
├── database/        # Integración con Supabase
├── main.py          # Punto de entrada - inicia todo automáticamente
└── .env.example     # Template de variables de entorno
```

## 🤝 Contribuir

*   Fork el proyecto
*   Crear rama: `git checkout -b feature/nueva-funcionalidad`
*   Commit: `git commit -m 'Agregar nueva funcionalidad'`
*   Push: `git push origin feature/nueva-funcionalidad`
*   Abrir Pull Request

## 📄 Licencia
[Especificar licencia]

## 🐛 Reportar problemas
Abrir issue en GitHub con:

*   Descripción del problema
*   Pasos para reproducir
*   Output de error completo
*   Sistema operativo y versión de Python

## 🧹 Limpieza (si migraste de versión anterior)
```bash
# Remover archivos de sistema del repo
git rm --cached celerybeat-schedule celerybeat-schedule-shm celerybeat-schedule-wal
git rm --cached logs/*.log
# git rm --cached dump.rdb # Descomentar si dump.rdb está en el repo
git commit -m "Remove system files"
git push
```
