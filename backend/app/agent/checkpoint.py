from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row

from app.config import get_settings


@contextmanager
def open_checkpointer() -> Iterator[PostgresSaver]:
    settings = get_settings()
    connection = psycopg.connect(
        settings.checkpoint_database_url,
        autocommit=True,
        row_factory=dict_row,
    )
    serializer = JsonPlusSerializer(allowed_msgpack_modules=())
    try:
        yield PostgresSaver(connection, serde=serializer)
    finally:
        connection.close()


def setup_checkpointer() -> None:
    with open_checkpointer() as checkpointer:
        checkpointer.setup()
