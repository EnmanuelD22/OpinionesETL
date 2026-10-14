from domain.entities.base import Base
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Float

class Categoria(Base):
    __tablename__ = 'Categoria'
    IdCategoria = Column(Integer, primary_key=True, autoincrement=True)
    Nombre = Column(String(100), nullable=False)