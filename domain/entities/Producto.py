from sqlalchemy import Column, Integer, String, Date, ForeignKey, Float
from domain.entities.base import Base

class Producto(Base):
    __tablename__ = 'Producto'
    IdProducto = Column(Integer, primary_key=True, autoincrement=False)
    Nombre = Column(String(100), nullable=False)
    IdCategoria = Column(Integer, ForeignKey("Categoria.IdCategoria"))