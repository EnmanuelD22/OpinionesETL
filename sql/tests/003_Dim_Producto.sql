-- Prueba selectiva de Dim_Producto con una opinión; se revierte al terminar.
USE [OpinionesDW];
GO
SET XACT_ABORT ON;
DECLARE @LotePrueba uniqueidentifier = NEWID();
DECLARE @Producto int;

BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.Stg_Opinion (
        IdEjecucion, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    )
    SELECT TOP (1)
        @LotePrueba, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    FROM dbo.Stg_Opinion
    ORDER BY IdOpinion;
    IF @@ROWCOUNT <> 1
        THROW 51411, 'No hay una opinion preparada para la prueba.', 1;

    SELECT @Producto = IdProducto
    FROM dbo.Stg_Opinion WHERE IdEjecucion = @LotePrueba;

    EXEC dbo.usp_CargarDimProducto @IdEjecucion = @LotePrueba;
    IF NOT EXISTS (
        SELECT 1 FROM dbo.Dim_Producto WHERE IdProducto = @Producto
    )
        THROW 51412, 'El producto del lote no quedo cubierto.', 1;
    EXEC dbo.usp_CargarDimProducto @IdEjecucion = @LotePrueba;

    ROLLBACK TRANSACTION;
    SELECT 'OK: un producto cubierto y segunda ejecucion sin duplicado' AS Resultado;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
