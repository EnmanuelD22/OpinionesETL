from sqlalchemy import create_engine
from config.settings import settings

engine = create_engine(
    settings.connection_string,
    fast_executemany=True,
    echo=False)

def get_connection():
    return engine.connect()