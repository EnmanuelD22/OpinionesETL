-- Carga masiva de encuestas ya validadas por el flujo Python.
-- Requiere sql/004_Staging.sql. No lee surveys_part1.csv directamente:
-- Python genera un CSV temporal con SOLO las encuestas aceptadas.
-- La ruta debe ser visible para la cuenta del servicio SQL Server.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_CargarEncuestasBulkStaging
    @IdEjecucion uniqueidentifier,
    @RutaArchivo nvarchar(4000)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL OR NULLIF(LTRIM(RTRIM(@RutaArchivo)), N'') IS NULL
        THROW 51030, N'IdEjecucion y RutaArchivo son obligatorios.', 1;

    -- El orden coincide exactamente con el encabezado del CSV preparado.
    -- Las columnas son texto para validar conversiones antes de Stg_Opinion.
    CREATE TABLE #BulkEncuesta (
        IdOrigen nvarchar(max) NULL,
        IdOpinion nvarchar(max) NULL,
        IdCliente nvarchar(max) NULL,
        IdProducto nvarchar(max) NULL,
        Fecha nvarchar(max) NULL,
        Comentario nvarchar(max) NULL,
        IdFuente nvarchar(max) NULL,
        Canal nvarchar(max) NULL,
        Puntaje nvarchar(max) NULL,
        IdClasificacionOriginal nvarchar(max) NULL,
        IdClasificacionPredicha nvarchar(max) NULL,
        IdClasificacion nvarchar(max) NULL
    );

    BEGIN TRY
        BEGIN TRANSACTION;

        DECLARE @Sql nvarchar(max) =
            N'BULK INSERT #BulkEncuesta FROM '''
            + REPLACE(@RutaArchivo, N'''', N'''''')
            + N''' WITH (FORMAT = ''CSV'', CODEPAGE = ''65001'', FIRSTROW = 2, '
            + N'FIELDQUOTE = ''"'', FIELDTERMINATOR = '','', '
            + N'ROWTERMINATOR = ''0x0a'', MAXERRORS = 0);';
        EXEC sys.sp_executesql @Sql;

        SELECT
            NULLIF(LTRIM(RTRIM(IdOrigen)), N'') AS IdOrigen,
            TRY_CONVERT(int, NULLIF(LTRIM(RTRIM(IdOpinion)), N'')) AS IdOpinion,
            TRY_CONVERT(int, NULLIF(LTRIM(RTRIM(IdCliente)), N'')) AS IdCliente,
            TRY_CONVERT(int, NULLIF(LTRIM(RTRIM(IdProducto)), N'')) AS IdProducto,
            TRY_CONVERT(date, NULLIF(LTRIM(RTRIM(Fecha)), N''), 23) AS Fecha,
            NULLIF(LTRIM(RTRIM(Comentario)), N'') AS Comentario,
            TRY_CONVERT(int, NULLIF(LTRIM(RTRIM(IdFuente)), N'')) AS IdFuente,
            NULLIF(LTRIM(RTRIM(Canal)), N'') AS Canal,
            TRY_CONVERT(decimal(3,1), NULLIF(LTRIM(RTRIM(Puntaje)), N'')) AS Puntaje,
            TRY_CONVERT(int, NULLIF(LTRIM(RTRIM(IdClasificacionOriginal)), N''))
                AS IdClasificacionOriginal,
            TRY_CONVERT(int, NULLIF(LTRIM(RTRIM(IdClasificacionPredicha)), N''))
                AS IdClasificacionPredicha,
            TRY_CONVERT(int, NULLIF(LTRIM(RTRIM(IdClasificacion)), N''))
                AS IdClasificacion,
            LEN(IdOrigen) AS LargoIdOrigen,
            LEN(Canal) AS LargoCanal
        INTO #Preparada
        FROM #BulkEncuesta;

        IF EXISTS (
            SELECT 1 FROM #Preparada
            WHERE IdOrigen IS NULL OR LargoIdOrigen > 50
               OR IdOpinion IS NULL OR IdOpinion <= 0
               OR IdCliente IS NULL OR IdProducto IS NULL
               OR Fecha IS NULL OR Comentario IS NULL
               OR IdFuente <> 2 OR IdFuente IS NULL
               OR Canal <> N'Encuestas' OR Canal IS NULL OR LargoCanal > 50
               OR Puntaje NOT BETWEEN 1 AND 5 OR Puntaje IS NULL
               OR IdClasificacionOriginal NOT IN (1, 2, 3)
               OR IdClasificacionOriginal IS NULL
               OR IdClasificacionPredicha IS NOT NULL
               OR IdClasificacion <> IdClasificacionOriginal
               OR IdClasificacion IS NULL
        )
            THROW 51031, N'El CSV preparado contiene una encuesta inválida.', 1;

        IF EXISTS (SELECT 1 FROM #Preparada GROUP BY IdOrigen HAVING COUNT(*) > 1)
           OR EXISTS (SELECT 1 FROM #Preparada GROUP BY IdOpinion HAVING COUNT(*) > 1)
            THROW 51032, N'El CSV preparado contiene identificadores duplicados.', 1;

        DELETE FROM dbo.Stg_Opinion
        WHERE IdEjecucion = @IdEjecucion AND IdTipoOpinion = 1;

        INSERT INTO dbo.Stg_Opinion (
            IdEjecucion, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
            IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
            IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
        )
        SELECT
            @IdEjecucion, 1, IdOrigen, IdOpinion, IdCliente,
            IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
            IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
        FROM #Preparada;

        DECLARE @FilasInsertadas int = @@ROWCOUNT;
        COMMIT TRANSACTION;
        SELECT @FilasInsertadas AS FilasInsertadas;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO
