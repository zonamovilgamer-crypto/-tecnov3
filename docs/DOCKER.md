# Dockerization Guide for Hive

This document provides instructions for building, running, and managing the "Hive" project using Docker and Docker Compose, both for development and production environments.

## Table of Contents
1.  [Prerequisites](#1-prerequisites)
2.  [Project Structure](#2-project-structure)
3.  [Building Docker Images](#3-building-docker-images)
4.  [Running in Development](#4-running-in-development)
5.  [Running in Production](#5-running-in-production)
6.  [Useful Docker Commands](#6-useful-docker-commands)
7.  [Troubleshooting](#7-troubleshooting)
8.  [Deployment to Railway](#8-deployment-to-railway)

---

## 1. Prerequisites
Before you begin, ensure you have the following installed:
*   **Docker Desktop:** Includes Docker Engine, Docker CLI, Docker Compose.
    *   [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
*   **Git:** For cloning the repository.

---

## 2. Project Structure
The Docker-related files are organized as follows:
```
F:\motor v2.0.1\
├── Dockerfile                  # Multi-stage Dockerfile for optimized images
├── docker-compose.yml          # Production Docker Compose configuration
├── docker-compose.dev.yml      # Development-specific Docker Compose overrides
├── .dockerignore               # Specifies files/directories to ignore when building images
└── docker/
    └── scripts/
        ├── entrypoint.sh       # Entrypoint script for Docker containers
        ├── wait-for-it.sh      # Utility to wait for services to be available
        └── healthcheck.sh      # Script for Celery worker health checks
```

---

## 3. Building Docker Images
To build the Docker images for your services, navigate to the root of your project and run:

```bash
docker-compose build
```
This command will build the images defined in `Dockerfile` for `celery-worker` and `celery-beat` services.

---

## 4. Running in Development
For development, you'll use `docker-compose.yml` combined with `docker-compose.dev.yml` to enable features like hot-reloading and detailed logging.

To start the services in development mode:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```
This will bring up Redis, Celery Worker, and Celery Beat. Changes to your Python code will trigger automatic reloads in the containers.

To stop development services:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml down
```

---

## 5. Running in Production
For production, you'll typically run services in detached mode (`-d`) and rely solely on `docker-compose.yml`.

To start the services in production mode:

```bash
docker-compose up -d
```
This will run the services in the background.

To stop production services:

```bash
docker-compose down
```

---

## 6. Useful Docker Commands

*   **View logs for a specific service:**
    ```bash
    docker-compose logs -f celery-worker
    docker-compose logs -f celery-beat
    docker-compose logs -f redis
    ```
*   **Execute a command inside a running container:**
    ```bash
    docker-compose exec celery-worker bash
    docker-compose exec redis redis-cli
    ```
*   **View running containers:**
    ```bash
    docker-compose ps
    ```
*   **Stop and remove all services, networks, and volumes:**
    ```bash
    docker-compose down --volumes --remove-orphans
    ```

---

## 7. Troubleshooting

*   **`ModuleNotFoundError` inside Docker:**
    *   Ensure all dependencies are listed in `requirements.txt`.
    *   Verify `COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages` in `Dockerfile` is correct.
    *   Rebuild images: `docker-compose build --no-cache`
*   **Services not starting (e.g., Redis not ready):**
    *   Check Redis logs: `docker-compose logs -f redis`
    *   Ensure `wait-for-it.sh` is correctly configured in `entrypoint.sh` and has execute permissions (`chmod +x docker/scripts/*.sh`).
*   **Celery workers not connecting:**
    *   Verify `REDIS_URL` in `.env` is correct and accessible from within the Docker network (should be `redis://redis:6379/0`).
    *   Check Celery worker logs for connection errors.
*   **Playwright browser issues:**
    *   Ensure `playwright install --with-deps chromium` runs successfully in the builder stage.
    *   Verify `PLAYWRIGHT_BROWSERS_PATH` environment variable is set correctly in the `Dockerfile`.

---

## 8. Deployment to Railway
Railway automatically detects `Dockerfile` and `docker-compose.yml` files.

1.  **Connect your GitHub repository** to Railway.
2.  **Configure Environment Variables:** Ensure all necessary variables from your `.env` file (e.g., `REDIS_URL`, `SUPABASE_URL`, `API_KEYS`, `LOG_LEVEL`, `CIRCUIT_BREAKER_ENABLED`, `RATE_LIMIT` settings) are set in Railway's environment variables for your project. Railway will automatically provide a `REDIS_URL` if you add a Redis service.
3.  **Add Redis Service:** In your Railway project, add a new Redis service. Railway will automatically inject its connection string into your environment variables. Update your `REDIS_URL` in `.env` (or directly in Railway) to match the provided internal Redis URL if you're not using an external one.
4.  **Deploy:** Railway will automatically build and deploy your services based on `Dockerfile` and `docker-compose.yml`. You might need to adjust the `command` for `celery-worker` and `celery-beat` in `docker-compose.yml` if Railway's default entrypoint interferes, or ensure your `entrypoint.sh` handles it.

**Important Note for Celery Beat on Railway:**
Railway typically runs a single main service. For Celery Beat, you might need to configure it as a separate service in `docker-compose.yml` and ensure its command is correctly set to run the beat scheduler. Railway's persistent volumes can be used for `celerybeat-schedule` if needed.
