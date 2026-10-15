"""Entidad de dominio para una fuente de datos."""

#region Imports
from dataclasses import dataclass
from datetime import date
from typing import Optional
#endregion


#region Entity
@dataclass
class FuenteDatos:
    IdFuente: int
    TipoFuente: str
    FechaCarga: Optional[date] = None


# Compatibilidad con el nombre usado por el esquema legado.
Fuente_Datos = FuenteDatos
#endregion
