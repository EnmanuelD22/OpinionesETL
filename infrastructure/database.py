"""Fábrica del motor SQLAlchemy.

Este módulo es infraestructura: es el único lugar donde se construye el
motor a partir de `config.settings`. La capa de aplicación recibe el motor a
través de sus adaptadores y nunca importa este módulo.
"""

#region Imports
from sqlalchemy import create_engine

from config.settings import settings
#endregion


#region Engine
engine = create_engine(
    settings.connection_string,
    echo=False,
    fast_executemany=True,
)


def get_engine():
    """Devuelve el motor configurado para la ejecución actual."""

    return engine
#endregion
