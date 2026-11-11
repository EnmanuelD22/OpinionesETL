-- Ejecutar después de DataWareHouse.sql.
USE [OpinionesDW];
GO

CREATE OR ALTER VIEW dbo.vw_KPIProductoMes AS
SELECT p.IdProducto, p.Nombre AS Producto, p.Categoria,
       f.Anio, f.Mes, f.AnioMes,
       COUNT(*) AS TotalOpiniones,
       SUM(CASE WHEN o.IdClasificacion = 1 THEN 1 ELSE 0 END) AS Positivas,
       SUM(CASE WHEN o.IdClasificacion = 2 THEN 1 ELSE 0 END) AS Negativas,
       SUM(CASE WHEN o.IdClasificacion = 3 THEN 1 ELSE 0 END) AS Neutras,
       CAST(100.0 * SUM(CASE WHEN o.IdClasificacion = 1 THEN 1 ELSE 0 END) / COUNT(*) AS decimal(5,2)) AS PorcentajeSatisfaccion,
       CAST(AVG(o.Puntaje) AS decimal(3,2)) AS PuntajePromedio
FROM dbo.Fact_Opinion AS o
JOIN dbo.Dim_Producto AS p ON p.IdProducto = o.IdProducto
JOIN dbo.Dim_Fecha AS f ON f.IdFecha = o.IdFecha
GROUP BY p.IdProducto, p.Nombre, p.Categoria, f.Anio, f.Mes, f.AnioMes;
GO

-- Una fila por opinión: permite filtros por producto, fecha, canal y tipo.
CREATE OR ALTER VIEW dbo.vw_OpinionesDetalle AS
SELECT o.IdOpinion, d.Fecha, d.Anio, d.AnioMes,
       p.IdProducto, p.Nombre AS Producto, p.Categoria,
       fu.IdFuente, fu.Canal, fu.TipoFuente,
       cl.Tipo AS Clasificacion, t.Nombre AS TipoOpinion,
       o.Puntaje, o.Comentario
FROM dbo.Fact_Opinion AS o
JOIN dbo.Dim_Fecha AS d ON d.IdFecha = o.IdFecha
JOIN dbo.Dim_Producto AS p ON p.IdProducto = o.IdProducto
JOIN dbo.Dim_Fuente AS fu ON fu.IdFuente = o.IdFuente
JOIN dbo.Dim_Clasificacion AS cl ON cl.IdClasificacion = o.IdClasificacion
JOIN dbo.Dim_TipoOpinion AS t ON t.IdTipoOpinion = o.IdTipoOpinion;
GO

-- Panorama global de opiniones efectivamente cargadas en el DW.
CREATE OR ALTER VIEW dbo.vw_KPIGeneral AS
SELECT COUNT(*) AS TotalOpiniones,
       SUM(CASE WHEN IdClasificacion = 1 THEN 1 ELSE 0 END) AS Positivas,
       SUM(CASE WHEN IdClasificacion = 2 THEN 1 ELSE 0 END) AS Negativas,
       SUM(CASE WHEN IdClasificacion = 3 THEN 1 ELSE 0 END) AS Neutras,
       CAST(100.0 * SUM(CASE WHEN IdClasificacion = 1 THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0) AS decimal(5,2)) AS PorcentajeSatisfaccion,
       CAST(AVG(Puntaje) AS decimal(3,2)) AS PuntajePromedio
FROM dbo.Fact_Opinion;
GO

CREATE OR ALTER VIEW dbo.vw_ClasificacionPorCanal AS
SELECT f.IdFuente, f.Canal, t.Nombre AS TipoOpinion,
       c.Tipo AS Clasificacion, COUNT(*) AS TotalOpiniones
FROM dbo.Fact_Opinion AS o
JOIN dbo.Dim_Fuente AS f ON f.IdFuente = o.IdFuente
JOIN dbo.Dim_TipoOpinion AS t ON t.IdTipoOpinion = o.IdTipoOpinion
JOIN dbo.Dim_Clasificacion AS c ON c.IdClasificacion = o.IdClasificacion
GROUP BY f.IdFuente, f.Canal, t.Nombre, c.Tipo;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Fact_Producto_Fecha' AND object_id = OBJECT_ID('dbo.Fact_Opinion'))
    CREATE INDEX IX_Fact_Producto_Fecha ON dbo.Fact_Opinion(IdProducto, IdFecha) INCLUDE (IdClasificacion, Puntaje);
GO
