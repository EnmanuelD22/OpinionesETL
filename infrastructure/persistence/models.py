"""Modelos relacionales del esquema de OpinionesETL.

Estos modelos no son las entidades del dominio. Solo describen la forma que
necesita SQL Server para crear tablas y resolver claves foráneas.
"""

#region Imports
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String

from infrastructure.persistence.base import Base
#endregion


#region Relational models
class CategoriaModel(Base):
    __tablename__ = "Categoria"

    IdCategoria = Column(Integer, primary_key=True, autoincrement=True)
    Nombre = Column(String(100), nullable=False)


class ClasificacionModel(Base):
    __tablename__ = "Clasificacion"

    IdClasificacion = Column(Integer, primary_key=True, autoincrement=False)
    Tipo = Column(String(100), nullable=False)


class FuenteDatosModel(Base):
    __tablename__ = "Fuente_Datos"

    IdFuente = Column(Integer, primary_key=True, autoincrement=False)
    TipoFuente = Column(String(50))
    FechaCarga = Column(Date)


class ClienteModel(Base):
    __tablename__ = "Cliente"

    IdCliente = Column(Integer, primary_key=True, autoincrement=False)
    Nombre = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True, unique=True)


class ProductoModel(Base):
    __tablename__ = "Producto"

    IdProducto = Column(Integer, primary_key=True, autoincrement=False)
    Nombre = Column(String(100), nullable=False)
    IdCategoria = Column(Integer, ForeignKey("Categoria.IdCategoria"))


class OpinionModel(Base):
    __tablename__ = "Opinion"

    IdOpinion = Column(Integer, primary_key=True, autoincrement=True)
    IdOrigen = Column(String(50))
    Canal = Column(String(50))
    Fecha = Column(Date)
    Comentario = Column(String)
    Puntaje = Column(Float)
    IdCliente = Column(Integer, ForeignKey("Cliente.IdCliente"))
    IdProducto = Column(Integer, ForeignKey("Producto.IdProducto"))
    IdClasificacion = Column(Integer, ForeignKey("Clasificacion.IdClasificacion"))
    IdFuente = Column(Integer, ForeignKey("Fuente_Datos.IdFuente"))
#endregion
