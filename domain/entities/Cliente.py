from sqlalchemy import Column, Integer, String, Date, ForeignKey, Float
from domain.entities.base import Base

class Cliente(Base):
    __tablename__ = 'Cliente'
    IdCliente = Column(Integer, primary_key=True, autoincrement=False)
    Nombre = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True, unique=True)