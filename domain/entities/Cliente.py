"""Entidad de dominio para un cliente."""

#region Imports
from dataclasses import dataclass
from typing import Optional
#endregion


#region Entity
@dataclass
class Cliente:
    IdCliente: int
    Nombre: str
    email: Optional[str] = None
#endregion
