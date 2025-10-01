# Guía de Deploy

## Railway

### Paso 1: Preparar servicios
1. Crear cuenta en Railway.app
2. Conectar repositorio GitHub
3. Agregar servicio Redis en Railway

### Paso 2: Configurar variables
En Railway → Settings → Variables, agregar todas las del `.env.example`:
- GROQ_API_KEY_1, GROQ_API_KEY_2, GROQ_API_KEY_3
- COHERE_API_KEY_1, COHERE_API_KEY_2, COHERE_API_KEY_3
- HUGGINGFACE_API_KEY_1, etc.
- REDIS_URL (automático si usas Redis de Railway)
- SUPABASE_URL
- SUPABASE_KEY

### Paso 3: Deploy
- Start Command: `python main.py`
- Deploy automático al hacer push a main

### Costos estimados
- Hobby: $5-10/mes
- Con Redis incluido: $10-20/mes

## Vercel (Frontend)

1. Conectar repositorio del frontend
2. Configurar variables de entorno
3. Build command: `npm run build` o `next build`
4. Deploy automático
