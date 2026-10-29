"""Entidad de dominio para una opinión."""

#region Imports
from dataclasses import dataclass
from datetime import date
from typing import Optional
#endregion


#region Entity
@dataclass
class Opinion:
    """Opinión independiente de la tecnología de persistencia."""

    IdCliente: int
    IdProducto: int
    Fecha: date
    Comentario: str
    IdFuente: int
    IdClasificacion: Optional[int] = None
    Puntaje: Optional[float] = None
    Canal: Optional[str] = None
    IdOrigen: Optional[str] = None
    IdTipoOpinion: Optional[int] = None
    IdOpinion: Optional[int] = None
#endregion
    
