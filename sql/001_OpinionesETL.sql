-- Ejecutar después de BaseRelacional.sql, conectado a la instancia de SQL Server.
USE [OpinionesETL];
GO

IF OBJECT_ID(N'dbo.AnalisisOpinion', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.AnalisisOpinion (
        IdOpinion int NOT NULL PRIMARY KEY,
        IdClasificacion int NOT NULL,
        Confianza float NOT NULL,
        ModeloVersion varchar(50) NOT NULL,
        CONSTRAINT FK_Analisis_Opinion FOREIGN KEY (IdOpinion) REFERENCES dbo.Opinion(IdOpinion),
        CONSTRAINT FK_Analisis_Clasificacion FOREIGN KEY (IdClasificacion) REFERENCES dbo.Clasificacion(IdClasificacion)
    );
END;
GO

-- La etiqueta original y la predicción se mantienen separadas.
CREATE OR ALTER VIEW dbo.vw_AnalisisGeneralOpiniones AS
SELECT o.IdOpinion, o.IdOrigen, o.Fecha, o.Comentario, o.Puntaje, o.Canal,
       c.Nombre AS NombreCliente, p.IdProducto, p.Nombre AS NombreProducto,
       cat.Nombre AS CategoriaProducto,
       origen.Tipo AS ClasificacionOriginal,
       pred.Tipo AS ClasificacionPredicha,
       COALESCE(origen.Tipo, pred.Tipo) AS ClasificacionOpinion,
       f.TipoFuente AS OrigenDatos
FROM dbo.Opinion AS o
LEFT JOIN dbo.Cliente AS c ON c.IdCliente = o.IdCliente
LEFT JOIN dbo.Producto AS p ON p.IdProducto = o.IdProducto
LEFT JOIN dbo.Categoria AS cat ON cat.IdCategoria = p.IdCategoria
LEFT JOIN dbo.Clasificacion AS origen ON origen.IdClasificacion = o.IdClasificacion
LEFT JOIN dbo.AnalisisOpinion AS a ON a.IdOpinion = o.IdOpinion
LEFT JOIN dbo.Clasificacion AS pred ON pred.IdClasificacion = a.IdClasificacion
LEFT JOIN dbo.Fuente_Datos AS f ON f.IdFuente = o.IdFuente;
GO

CREATE OR ALTER VIEW dbo.vw_ResumenPuntajePorProducto AS
SELECT p.IdProducto, p.Nombre AS Producto, cat.Nombre AS Categoria,
       COUNT(o.IdOpinion) AS TotalOpiniones,
       ROUND(AVG(o.Puntaje), 2) AS PuntajePromedio
FROM dbo.Producto AS p
LEFT JOIN dbo.Categoria AS cat ON cat.IdCategoria = p.IdCategoria
LEFT JOIN dbo.Opinion AS o ON o.IdProducto = p.IdProducto
GROUP BY p.IdProducto, p.Nombre, cat.Nombre;
GO

-- Satisfacción = positivas / opiniones clasificadas; neutras cuentan en el denominador.
CREATE OR ALTER VIEW dbo.vw_SatisfaccionPorProductoMes AS
SELECT p.IdProducto, p.Nombre AS Producto,
       YEAR(o.Fecha) AS Anio, MONTH(o.Fecha) AS Mes,
       COUNT(*) AS TotalOpiniones,
       SUM(CASE WHEN COALESCE(o.IdClasificacion, a.IdClasificacion) = 1 THEN 1 ELSE 0 END) AS Positivas,
       SUM(CASE WHEN COALESCE(o.IdClasificacion, a.IdClasificacion) IS NOT NULL THEN 1 ELSE 0 END) AS Clasificadas,
       CAST(100.0 * SUM(CASE WHEN COALESCE(o.IdClasificacion, a.IdClasificacion) = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN COALESCE(o.IdClasificacion, a.IdClasificacion) IS NOT NULL THEN 1 ELSE 0 END), 0)
            AS decimal(5,2)) AS PorcentajeSatisfaccion
FROM dbo.Opinion AS o
JOIN dbo.Producto AS p ON p.IdProducto = o.IdProducto
LEFT JOIN dbo.AnalisisOpinion AS a ON a.IdOpinion = o.IdOpinion
GROUP BY p.IdProducto, p.Nombre, YEAR(o.Fecha), MONTH(o.Fecha);
GO

CREATE OR ALTER PROCEDURE dbo.sp_BuscarOpinionesNegativas
    @NombreCategoria varchar(100)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT o.Fecha, c.Nombre AS Cliente, c.email AS Correo,
           p.Nombre AS Producto, o.Comentario, o.Puntaje
    FROM dbo.Opinion AS o
    JOIN dbo.Cliente AS c ON c.IdCliente = o.IdCliente
    JOIN dbo.Producto AS p ON p.IdProducto = o.IdProducto
    JOIN dbo.Categoria AS cat ON cat.IdCategoria = p.IdCategoria
    LEFT JOIN dbo.AnalisisOpinion AS a ON a.IdOpinion = o.IdOpinion
    WHERE cat.Nombre = @NombreCategoria
      AND COALESCE(o.IdClasificacion, a.IdClasificacion) = 2
    ORDER BY o.Puntaje ASC, o.Fecha DESC;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Opinion_Canal_Origen' AND object_id = OBJECT_ID('dbo.Opinion'))
    CREATE INDEX IX_Opinion_Canal_Origen ON dbo.Opinion(Canal, IdOrigen);
GO
