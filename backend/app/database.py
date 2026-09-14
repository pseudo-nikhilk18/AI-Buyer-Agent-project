from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)


def check_database_connection(database_engine: Engine = engine) -> None:
    with database_engine.connect() as connection:
        connection.execute(text("SELECT 1"))
