-- Paso 5.7: carga de Fact_Opinion desde un lote selectivo ya validado.
-- Ejecutar después de las seis dimensiones. No lee los CSV históricos.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_CargarFactOpinion
    @IdEjecucion uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL
        THROW 51701, 'IdEjecucion es obligatorio.', 1;

    DECLARE @Leidos int = 0;
    DECLARE @Insertados int = 0;
    DECLARE @Actualizados int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (
            SELECT 1 FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
            WHERE s.IdEjecucion = @IdEjecucion AND s.Estado <> 'VALIDADO'
        )
            THROW 51702, 'El lote contiene opiniones no validadas.', 1;

        -- Materializar solo claves y valores cortos. Comentario varchar(max)
        -- permanece en staging y se une al INSERT/UPDATE final.
        SELECT s.IdOpinion,
               s.IdTipoOpinion,
               CONVERT(int, CONVERT(char(8), s.Fecha, 112)) AS IdFecha,
               s.Fecha,
               s.IdCliente,
               s.IdProducto,
               s.IdFuente,
               LTRIM(RTRIM(s.Canal)) AS Canal,
               s.IdClasificacion,
               s.Puntaje
        INTO #Hechos
        FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
        WHERE s.IdEjecucion = @IdEjecucion;
        SELECT @Leidos = COUNT(*) FROM #Hechos;
        IF @Leidos = 0
            THROW 51703, 'El lote no contiene opiniones preparadas.', 1;

        -- Comprobar expresamente las seis claves dimensionales y el canal.
        IF EXISTS (
            SELECT 1
            FROM #Hechos AS h
            LEFT JOIN dbo.Dim_Fecha AS df WITH (HOLDLOCK) ON df.IdFecha = h.IdFecha
            LEFT JOIN dbo.Dim_Cliente AS dc WITH (HOLDLOCK) ON dc.IdCliente = h.IdCliente
            LEFT JOIN dbo.Dim_Producto AS dp WITH (HOLDLOCK) ON dp.IdProducto = h.IdProducto
            LEFT JOIN dbo.Dim_Fuente AS du WITH (HOLDLOCK) ON du.IdFuente = h.IdFuente
            LEFT JOIN dbo.Dim_Clasificacion AS dcl WITH (HOLDLOCK)
              ON dcl.IdClasificacion = h.IdClasificacion
            LEFT JOIN dbo.Dim_TipoOpinion AS dt WITH (HOLDLOCK)
              ON dt.IdTipoOpinion = h.IdTipoOpinion
            WHERE df.IdFecha IS NULL OR df.Fecha <> h.Fecha
               OR dc.IdCliente IS NULL OR dp.IdProducto IS NULL
               OR du.IdFuente IS NULL OR dcl.IdClasificacion IS NULL
               OR dt.IdTipoOpinion IS NULL
               OR CONVERT(varbinary(50), du.Canal) <>
                  CONVERT(varbinary(50), h.Canal)
        )
            THROW 51704, 'Faltan claves dimensionales o el canal no coincide.', 1;

        IF EXISTS (
            SELECT 1
            FROM #Hechos AS h
            JOIN dbo.Fact_Opinion AS f WITH (UPDLOCK, HOLDLOCK)
              ON f.IdOpinion = h.IdOpinion
            WHERE f.IdTipoOpinion <> h.IdTipoOpinion
        )
            THROW 51705, 'IdOpinion ya pertenece a otro tipo de opinion.', 1;

        UPDATE f
           SET f.IdFecha = h.IdFecha,
               f.IdCliente = h.IdCliente,
               f.IdProducto = h.IdProducto,
               f.IdFuente = h.IdFuente,
               f.IdClasificacion = h.IdClasificacion,
               f.Puntaje = h.Puntaje,
               f.Comentario = s.Comentario
        FROM dbo.Fact_Opinion AS f
        JOIN #Hechos AS h ON h.IdOpinion = f.IdOpinion
        JOIN dbo.Stg_Opinion AS s
          ON s.IdEjecucion = @IdEjecucion
         AND s.IdOpinion = h.IdOpinion
        WHERE f.IdFecha <> h.IdFecha
           OR f.IdCliente <> h.IdCliente
           OR f.IdProducto <> h.IdProducto
           OR f.IdFuente <> h.IdFuente
           OR f.IdClasificacion <> h.IdClasificacion
           OR f.IdTipoOpinion <> h.IdTipoOpinion
           OR f.Puntaje <> h.Puntaje
           OR (f.Puntaje IS NULL AND h.Puntaje IS NOT NULL)
           OR (f.Puntaje IS NOT NULL AND h.Puntaje IS NULL)
           OR f.Comentario IS NULL
           OR CONVERT(varbinary(max), f.Comentario) <>
              CONVERT(varbinary(max), s.Comentario);
        SET @Actualizados = @@ROWCOUNT;

        INSERT INTO dbo.Fact_Opinion (
            IdOpinion, IdFecha, IdCliente, IdProducto, IdFuente,
            IdClasificacion, Puntaje, Comentario, IdTipoOpinion
        )
        SELECT h.IdOpinion, h.IdFecha, h.IdCliente, h.IdProducto,
               h.IdFuente, h.IdClasificacion, h.Puntaje, s.Comentario,
               h.IdTipoOpinion
        FROM #Hechos AS h
        JOIN dbo.Stg_Opinion AS s
          ON s.IdEjecucion = @IdEjecucion
         AND s.IdOpinion = h.IdOpinion
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.Fact_Opinion AS f WITH (UPDLOCK, HOLDLOCK)
            WHERE f.IdOpinion = h.IdOpinion
        )
        OPTION (MAX_GRANT_PERCENT = 1);
        SET @Insertados = @@ROWCOUNT;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;

    SELECT @Leidos AS Leidos,
           @Insertados AS Insertados,
           @Actualizados AS Actualizados,
           @Leidos - @Insertados - @Actualizados AS SinCambios;
END;
GO
