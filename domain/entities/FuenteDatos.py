from sqlalchemy import Column, Integer, String, Date, ForeignKey, Float
from domain.entities.base import Base

class FuenteDatos(Base):
    __tablename__ = 'Fuente_Datos'
    IdFuente = Column(Integer, primary_key=True, autoincrement=False)
    TipoFuente = Column(String(50))
    FechaCarga = Column(Date)