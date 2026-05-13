import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import urllib.parse

_pool = None

def init_db(database_url: str):
    global _pool
    # Parse the URL to support both postgres:// and postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
    _pool = pool.ThreadedConnectionPool(1, 20, database_url)
    
    # Initialize schema
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS portfolios (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS holdings (
                    id SERIAL PRIMARY KEY,
                    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
                    ticker VARCHAR(50) NOT NULL,
                    shares FLOAT NOT NULL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
                    message TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Add user_id column to portfolios if it doesn't exist (migration)
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'portfolios' AND column_name = 'user_id'
                    ) THEN
                        ALTER TABLE portfolios ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
                    END IF;
                END $$;
            """)
        conn.commit()
    finally:
        put_db_connection(conn)

def get_db_connection():
    if _pool is None:
        raise RuntimeError("Database not initialized. Call init_db first.")
    return _pool.getconn()

def put_db_connection(conn):
    if _pool is not None and conn is not None:
        _pool.putconn(conn)
