from supabase import create_client, Client
from config.motor_config import get_motor_config

config = get_motor_config()

def get_supabase_client() -> Client:
    """Retorna cliente inicializado de Supabase"""
    return create_client(
        config.SUPABASE_URL,
        config.SUPABASE_KEY
    )

# Instancia global
supabase = get_supabase_client()
