from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


cfg = settings()
engine = create_engine(cfg.database_url, connect_args={'check_same_thread': False} if cfg.database_url.startswith('sqlite') else {}, pool_pre_ping=True, pool_size=30, max_overflow=10)
if cfg.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=30000')
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
