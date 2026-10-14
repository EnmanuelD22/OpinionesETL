from sqlalchemy import Column, Integer, String, Date, ForeignKey, Float
from domain.entities.base import Base
False
class Clasificacion(Base):
    __tablename__ = 'Clasificacion'
    IdClasificacion = Column(Integer, primary_key=True, autoincrement=False)
    Tipo = Column(String(100), nullable=False)