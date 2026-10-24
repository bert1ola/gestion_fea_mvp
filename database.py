import os
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

_pool = None

def get_pool():
    """Crea el pool de conexiones una sola vez por proceso."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="gestion_fea_pool",
            pool_size=5,
            pool_reset_session=True,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "gestion_fea"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
    return _pool

def get_connection():
    """Entrega una conexión del pool; debe cerrarse con conn.close()."""
    return get_pool().get_connection()
