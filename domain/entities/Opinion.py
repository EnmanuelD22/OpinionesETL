from sqlalchemy import Column, Integer, String, Date, ForeignKey, Float
from domain.entities.base import Base


class Opinion(Base):
    __tablename__ = 'Opinion'
    IdOpinion = Column(Integer, primary_key=True, autoincrement=True)
    IdOrigen = Column(String(50)) 
    Canal = Column(String(50)) 
    Fecha = Column(Date)
    Comentario = Column(String)
    Puntaje = Column(Float) 
    IdCliente = Column(Integer, ForeignKey('Cliente.IdCliente'))
    IdProducto = Column(Integer, ForeignKey('Producto.IdProducto'))
    IdClasificacion = Column(Integer, ForeignKey('Clasificacion.IdClasificacion'))
    IdFuente = Column(Integer, ForeignKey('Fuente_Datos.IdFuente'))
    
