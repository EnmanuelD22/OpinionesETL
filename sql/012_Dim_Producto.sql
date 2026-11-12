-- Paso 5.4: carga selectiva de Dim_Producto desde un lote validado.
-- Staging aporta las claves; Producto y Categoria aportan los atributos.
USE [OpinionesDW];
GO

CREATE OR ALTER PROCEDURE dbo.usp_CargarDimProducto
    @IdEjecucion uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @IdEjecucion IS NULL
        THROW 51401, 'IdEjecucion es obligatorio.', 1;

    DECLARE @Leidas int = 0;
    DECLARE @Actualizadas int = 0;
    DECLARE @Insertadas int = 0;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (
            SELECT 1
            FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
            LEFT JOIN OpinionesETL.dbo.Producto AS p WITH (HOLDLOCK)
              ON p.IdProducto = s.IdProducto
            LEFT JOIN OpinionesETL.dbo.Categoria AS cat WITH (HOLDLOCK)
              ON cat.IdCategoria = p.IdCategoria
            WHERE s.IdEjecucion = @IdEjecucion
              AND (p.IdProducto IS NULL OR cat.IdCategoria IS NULL
                   OR NULLIF(LTRIM(RTRIM(p.Nombre)), '') IS NULL
                   OR NULLIF(LTRIM(RTRIM(cat.Nombre)), '') IS NULL
                   OR DATALENGTH(LTRIM(RTRIM(p.Nombre))) > 200
                   OR DATALENGTH(LTRIM(RTRIM(cat.Nombre))) > 200)
        )
            THROW 51402, 'El lote contiene un producto o categoria sin catalogo o nombre valido.', 1;

        SELECT DISTINCT p.IdProducto,
               LTRIM(RTRIM(p.Nombre)) AS Nombre,
               LTRIM(RTRIM(cat.Nombre)) AS Categoria
        INTO #Productos
        FROM dbo.Stg_Opinion AS s WITH (HOLDLOCK)
        JOIN OpinionesETL.dbo.Producto AS p WITH (HOLDLOCK)
          ON p.IdProducto = s.IdProducto
        JOIN OpinionesETL.dbo.Categoria AS cat WITH (HOLDLOCK)
          ON cat.IdCategoria = p.IdCategoria
        WHERE s.IdEjecucion = @IdEjecucion;
        SELECT @Leidas = COUNT(*) FROM #Productos;

        UPDATE d
           SET d.Nombre = p.Nombre,
               d.Categoria = p.Categoria
        FROM dbo.Dim_Producto AS d
        JOIN #Productos AS p ON p.IdProducto = d.IdProducto
        WHERE CONVERT(varbinary(200), d.Nombre) <> CONVERT(varbinary(200), p.Nombre)
           OR CONVERT(varbinary(200), d.Categoria) <> CONVERT(varbinary(200), p.Categoria);
        SET @Actualizadas = @@ROWCOUNT;

        INSERT INTO dbo.Dim_Producto (IdProducto, Nombre, Categoria)
        SELECT p.IdProducto, p.Nombre, p.Categoria
        FROM #Productos AS p
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.Dim_Producto AS d WITH (UPDLOCK, HOLDLOCK)
            WHERE d.IdProducto = p.IdProducto
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
