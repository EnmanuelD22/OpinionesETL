-- Preparación por conjuntos de reseñas relacionales en OpinionesDW.
-- Solo lee OpinionesETL.dbo.Opinion de tipo 2; no modifica la base origen.
-- Ejecutar tras sql/004_Staging.sql. No carga dimensiones ni Fact_Opinion.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_PrepararResenasRelacionales
    @IdEjecucion uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @Leidos int = 0;
    DECLARE @Preparados int = 0;
    DECLARE @Rechazados int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Repetir la misma ejecución reemplaza únicamente las reseñas de ese lote.
        DELETE FROM dbo.Stg_Opinion
        WHERE IdEjecucion = @IdEjecucion AND IdTipoOpinion = 2;

        DELETE FROM dbo.Stg_Rechazo
        WHERE IdEjecucion = @IdEjecucion AND Origen = 'resena';

        -- Materializar las claves antes de unir Comentario varchar(max): el
        -- ROW_NUMBER ordena solo enteros y un IdOrigen corto.
        SELECT o.IdOpinion,
               LTRIM(RTRIM(o.IdOrigen)) AS IdOrigen,
               ROW_NUMBER() OVER (
                   PARTITION BY LTRIM(RTRIM(o.IdOrigen))
                   ORDER BY o.IdOpinion
               ) AS NumeroOrigen
        INTO #ResenaClaves
        FROM OpinionesETL.dbo.Opinion AS o
        WHERE o.IdTipoOpinion = 2;

        CREATE UNIQUE CLUSTERED INDEX IX_ResenaClaves_IdOpinion
            ON #ResenaClaves(IdOpinion);

        SELECT @Leidos = COUNT(*) FROM #ResenaClaves;

        -- Guardar solo clave, origen y motivo. El comentario largo se consulta
        -- para comprobar que no esté vacío, sin incluirlo en ninguna ordenación.
        SELECT k.IdOpinion, k.IdOrigen,
            CASE
                WHEN k.NumeroOrigen > 1 THEN 'registro_duplicado'
                WHEN k.IdOrigen IS NULL OR k.IdOrigen = ''
                    OR k.IdOpinion IS NULL OR k.IdOpinion <= 0
                    THEN 'id_invalido_o_vacio'
                WHEN c.IdCliente IS NULL OR p.IdProducto IS NULL
                    OR cat.IdCategoria IS NULL OR f.IdFuente IS NULL
                    OR f.TipoFuente IS NULL THEN 'integridad_referencial'
                WHEN o.Fecha IS NULL THEN 'fecha_invalida_o_vacia'
                WHEN o.Puntaje IS NULL OR o.Puntaje < 1 OR o.Puntaje > 5
                    THEN 'puntaje_invalido'
                WHEN o.Comentario IS NULL
                    OR LTRIM(RTRIM(o.Comentario)) = ''
                    OR o.Canal IS NULL OR LTRIM(RTRIM(o.Canal)) = ''
                    THEN 'campo_obligatorio_vacio'
                WHEN COALESCE(o.IdClasificacion, a.IdClasificacion)
                    NOT IN (1, 2, 3)
                    OR COALESCE(o.IdClasificacion, a.IdClasificacion) IS NULL
                    THEN 'sin_clasificacion_valida'
                ELSE NULL
            END AS Motivo
        INTO #Validadas
        FROM #ResenaClaves AS k
        JOIN OpinionesETL.dbo.Opinion AS o
            ON o.IdOpinion = k.IdOpinion
        LEFT JOIN OpinionesETL.dbo.AnalisisOpinion AS a
            ON a.IdOpinion = o.IdOpinion
        LEFT JOIN OpinionesETL.dbo.Cliente AS c
            ON c.IdCliente = o.IdCliente
        LEFT JOIN OpinionesETL.dbo.Producto AS p
            ON p.IdProducto = o.IdProducto
        LEFT JOIN OpinionesETL.dbo.Categoria AS cat
            ON cat.IdCategoria = p.IdCategoria
        LEFT JOIN OpinionesETL.dbo.Fuente_Datos AS f
            ON f.IdFuente = o.IdFuente;

        INSERT INTO dbo.Stg_Rechazo
            (IdEjecucion, Origen, IdOrigen, Motivo)
        SELECT @IdEjecucion, 'resena', IdOrigen, Motivo
        FROM #Validadas
        WHERE Motivo IS NOT NULL;
        SET @Rechazados = @@ROWCOUNT;

        INSERT INTO dbo.Stg_Opinion
            (IdEjecucion, IdTipoOpinion, IdOrigen, IdOpinion,
             IdCliente, IdProducto, Fecha, Comentario, IdFuente, Canal,
             Puntaje, IdClasificacionOriginal, IdClasificacionPredicha,
             IdClasificacion)
        SELECT
            @IdEjecucion, 2, v.IdOrigen, v.IdOpinion,
            o.IdCliente, o.IdProducto, o.Fecha,
            LTRIM(RTRIM(o.Comentario)), o.IdFuente,
            LTRIM(RTRIM(o.Canal)),
            CONVERT(decimal(3, 1), o.Puntaje), o.IdClasificacion,
            a.IdClasificacion,
            COALESCE(o.IdClasificacion, a.IdClasificacion)
        FROM #Validadas AS v
        JOIN OpinionesETL.dbo.Opinion AS o
            ON o.IdOpinion = v.IdOpinion
        LEFT JOIN OpinionesETL.dbo.AnalisisOpinion AS a
            ON a.IdOpinion = o.IdOpinion
        WHERE v.Motivo IS NULL;
        SET @Preparados = @@ROWCOUNT;

        COMMIT TRANSACTION;

        SELECT @Leidos AS Leidos,
               @Preparados AS Preparados,
               @Rechazados AS Rechazados;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO
