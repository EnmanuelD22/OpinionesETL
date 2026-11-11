"""Esquema equivalente a DataWareHouse.sql para pruebas y nuevos entornos."""

from sqlalchemy import (Column, Date, ForeignKey, Integer, Numeric, SmallInteger,
                        String, Text)
from sqlalchemy.orm import declarative_base

WarehouseBase = declarative_base()


class DimClasificacion(WarehouseBase):
    __tablename__ = "Dim_Clasificacion"
    IdClasificacion = Column(Integer, primary_key=True, autoincrement=False)
    Tipo = Column(String(30), nullable=False)


class DimCliente(WarehouseBase):
    __tablename__ = "Dim_Cliente"
    IdCliente = Column(Integer, primary_key=True, autoincrement=False)
    Nombre = Column(String(200), nullable=False)
    Email = Column(String(200))


class DimFecha(WarehouseBase):
    __tablename__ = "Dim_Fecha"
    IdFecha = Column(Integer, primary_key=True, autoincrement=False)
    Fecha = Column(Date, nullable=False, unique=True)
    Anio = Column(SmallInteger, nullable=False)
    Trimestre = Column(SmallInteger, nullable=False)
    Mes = Column(SmallInteger, nullable=False)
    NombreMes = Column(String(15), nullable=False)
    AnioMes = Column(String(7), nullable=False)
    Dia = Column(SmallInteger, nullable=False)


class DimFuente(WarehouseBase):
    __tablename__ = "Dim_Fuente"
    IdFuente = Column(Integer, primary_key=True, autoincrement=False)
    Canal = Column(String(50), nullable=False)
    TipoFuente = Column(String(50), nullable=False)


class DimProducto(WarehouseBase):
    __tablename__ = "Dim_Producto"
    IdProducto = Column(Integer, primary_key=True, autoincrement=False)
    Nombre = Column(String(200), nullable=False)
    Categoria = Column(String(200), nullable=False)


class DimTipoOpinion(WarehouseBase):
    __tablename__ = "Dim_TipoOpinion"
    IdTipoOpinion = Column(Integer, primary_key=True, autoincrement=False)
    Nombre = Column(String(50), nullable=False)


class FactOpinion(WarehouseBase):
    __tablename__ = "Fact_Opinion"
    IdOpinion = Column(Integer, primary_key=True, autoincrement=False)
    IdFecha = Column(Integer, ForeignKey("Dim_Fecha.IdFecha"), nullable=False)
    IdCliente = Column(Integer, ForeignKey("Dim_Cliente.IdCliente"), nullable=False)
    IdProducto = Column(Integer, ForeignKey("Dim_Producto.IdProducto"), nullable=False)
    IdFuente = Column(Integer, ForeignKey("Dim_Fuente.IdFuente"), nullable=False)
    IdClasificacion = Column(Integer, ForeignKey("Dim_Clasificacion.IdClasificacion"), nullable=False)
    Puntaje = Column(Numeric(3, 1))
    Comentario = Column(Text)
    IdTipoOpinion = Column(Integer, ForeignKey("Dim_TipoOpinion.IdTipoOpinion"), nullable=False)
