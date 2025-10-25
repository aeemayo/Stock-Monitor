from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base

_engine = None
_Session = None

def init_db(database_url: str):
    global _engine, _Session
    _engine = create_engine(database_url, connect_args={"check_same_thread": False})
    _Session = scoped_session(sessionmaker(bind=_engine))
    Base.metadata.create_all(_engine)

def get_session():
    if _Session is None:
        raise RuntimeError("Database not initialized. Call init_db first.")
    return _Session()
