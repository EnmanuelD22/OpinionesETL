-- Consultas de solo lectura para validar el diseño antes de implementar.
-- Ejecutar en SSMS contra la misma instancia que contiene ambas bases.
USE [OpinionesETL];
GO

-- 1. Confirmar los identificadores reales de cada tipo.
SELECT IdTipoOpinion, Nombre
FROM dbo.TipoOpinion
ORDER BY IdTipoOpinion;

-- 2. Volumen y referencias faltantes por tipo.
SELECT IdTipoOpinion,
       COUNT(*) AS Total,
       SUM(CASE WHEN IdCliente IS NULL OR IdProducto IS NULL
                     OR IdFuente IS NULL OR o.IdTipoOpinion IS NULL OR Fecha IS NULL
                     OR (o.IdClasificacion IS NULL AND a.IdOpinion IS NULL)
                THEN 1 ELSE 0 END) AS IncompletasParaDW
FROM dbo.Opinion AS o
LEFT JOIN dbo.AnalisisOpinion AS a ON a.IdOpinion = o.IdOpinion
GROUP BY o.IdTipoOpinion
ORDER BY o.IdTipoOpinion;

-- 3. Identificadores de origen repetidos dentro de un tipo.
SELECT IdTipoOpinion, IdOrigen, COUNT(*) AS Repeticiones
FROM dbo.Opinion
WHERE IdOrigen IS NOT NULL
GROUP BY IdTipoOpinion, IdOrigen
HAVING COUNT(*) > 1
ORDER BY Repeticiones DESC, IdTipoOpinion, IdOrigen;

-- 4. Encuestas: verificar si IdOrigen permite asociar cada fila CSV
--    con el IdOpinion relacional que usa actualmente Fact_Opinion.
SELECT COUNT(*) AS EncuestasRelacionales,
       SUM(CASE WHEN IdOrigen IS NULL THEN 1 ELSE 0 END) AS SinIdOrigen,
       SUM(CASE WHEN TRY_CONVERT(int, IdOrigen) IS NOT NULL THEN 1 ELSE 0 END)
           AS ConIdOrigenNumerico
FROM dbo.Opinion
WHERE IdTipoOpinion = 1;

-- 5. La tabla de hechos y su distribución actual.
SELECT IdTipoOpinion, COUNT(*) AS Hechos
FROM [OpinionesDW].dbo.Fact_Opinion
GROUP BY IdTipoOpinion
ORDER BY IdTipoOpinion;
GO
