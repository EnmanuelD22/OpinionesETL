import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

# Conexion a la base de datos
SERVIDOR = os.getenv("SQL_SERVER", r"EnmanuelDiaz")
DATA_BASE = os.getenv("SQL_DATABASE", "OpinionesETL")
ODBC_DRIVER = os.getenv("ODBC_DRIVER", "ODBC Driver 17 for SQL Server")

CONEXION_STRING = URL.create(
    "mssql+pyodbc",
    host=SERVIDOR,
    database=DATA_BASE,
    query={
        "driver": ODBC_DRIVER,
        "Trusted_Connection": "yes",
        "TrustServerCertificate": "yes"
    },
)

engine = create_engine(CONEXION_STRING, echo=False, fast_executemany=True)