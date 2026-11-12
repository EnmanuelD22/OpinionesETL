-- Paso 5.6: carga selectiva de fechas usadas por un lote de staging.
-- Los nombres de mes son fijos y no dependen de SET LANGUAGE.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_CargarDimFecha
    @IdEjecucion uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL
        THROW 51601, 'IdEjecucion es obligatorio.', 1;

    DECLARE @Leidas int = 0;
    DECLARE @Insertadas int = 0;
    DECLARE @Actualizadas int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (
            SELECT 1 FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
            WHERE s.IdEjecucion = @IdEjecucion AND s.Fecha IS NULL
        )
            THROW 51602, 'El lote contiene una fecha vacia.', 1;

        SELECT DISTINCT
            CONVERT(int, CONVERT(char(8), s.Fecha, 112)) AS IdFecha,
            s.Fecha,
            CONVERT(smallint, DATEPART(year, s.Fecha)) AS Anio,
            CONVERT(tinyint, (DATEPART(month, s.Fecha) - 1) / 3 + 1) AS Trimestre,
            CONVERT(tinyint, DATEPART(month, s.Fecha)) AS Mes,
            CONVERT(varchar(15), CASE DATEPART(month, s.Fecha)
                WHEN 1 THEN 'enero' WHEN 2 THEN 'febrero'
                WHEN 3 THEN 'marzo' WHEN 4 THEN 'abril'
                WHEN 5 THEN 'mayo' WHEN 6 THEN 'junio'
                WHEN 7 THEN 'julio' WHEN 8 THEN 'agosto'
                WHEN 9 THEN 'septiembre' WHEN 10 THEN 'octubre'
                WHEN 11 THEN 'noviembre' WHEN 12 THEN 'diciembre'
            END) AS NombreMes,
            CONVERT(char(7), s.Fecha, 23) AS AnioMes,
            CONVERT(tinyint, DATEPART(day, s.Fecha)) AS Dia
        INTO #Fechas
        FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
        WHERE s.IdEjecucion = @IdEjecucion;
        SELECT @Leidas = COUNT(*) FROM #Fechas;

        IF EXISTS (
            SELECT 1
            FROM #Fechas AS f
            JOIN dbo.Dim_Fecha AS d WITH (UPDLOCK, HOLDLOCK)
              ON d.IdFecha = f.IdFecha
            WHERE d.Fecha <> f.Fecha
        ) OR EXISTS (
            SELECT 1
            FROM #Fechas AS f
            JOIN dbo.Dim_Fecha AS d WITH (UPDLOCK, HOLDLOCK)
              ON d.Fecha = f.Fecha
            WHERE d.IdFecha <> f.IdFecha
        )
            THROW 51603, 'Una fecha del lote tiene una clave distinta en Dim_Fecha.', 1;

        UPDATE d
           SET d.Anio = f.Anio,
               d.Trimestre = f.Trimestre,
               d.Mes = f.Mes,
               d.NombreMes = f.NombreMes,
               d.AnioMes = f.AnioMes,
               d.Dia = f.Dia
        FROM dbo.Dim_Fecha AS d
        JOIN #Fechas AS f ON f.IdFecha = d.IdFecha
        WHERE d.Anio <> f.Anio
           OR d.Trimestre <> f.Trimestre
           OR d.Mes <> f.Mes
           OR CONVERT(varbinary(15), d.NombreMes) <>
              CONVERT(varbinary(15), f.NombreMes)
           OR CONVERT(varbinary(7), d.AnioMes) <>
              CONVERT(varbinary(7), f.AnioMes)
           OR d.Dia <> f.Dia;
        SET @Actualizadas = @@ROWCOUNT;

        INSERT INTO dbo.Dim_Fecha (
            IdFecha, Fecha, Anio, Trimestre, Mes, NombreMes, AnioMes, Dia
        )
        SELECT f.IdFecha, f.Fecha, f.Anio, f.Trimestre, f.Mes,
               f.NombreMes, f.AnioMes, f.Dia
        FROM #Fechas AS f
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.Dim_Fecha AS d WITH (UPDLOCK, HOLDLOCK)
            WHERE d.IdFecha = f.IdFecha
        );
        SET @Insertadas = @@ROWCOUNT;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;

    SELECT @Leidas AS ClavesLote,
           @Insertadas AS Insertadas,
           @Actualizadas AS Actualizadas;
END;
GO
