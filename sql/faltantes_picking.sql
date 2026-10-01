/*
    Historial de faltantes de Picking.
    Ejecutar con permisos DDL en las bases Digitalizacion y Datalake.
    La tabla guarda una fila por episodio: al desmarcar se cierra esa fila;
    al volver a marcar se inserta un nuevo episodio.
*/

USE [Digitalizacion];
GO

IF OBJECT_ID(N'[CAB].[faltantes_picking]', N'U') IS NULL
BEGIN
    CREATE TABLE [CAB].[faltantes_picking] (
        [ID_FALTANTE] BIGINT IDENTITY(1,1) NOT NULL
            CONSTRAINT [PK_faltantes_picking] PRIMARY KEY,
        [ID_PICKING] BIGINT NOT NULL,
        [NUMEROPEDIDO] NVARCHAR(50) NOT NULL,
        [CODIGOPICKING] NVARCHAR(100) NULL,
        [MOTIVO_FALTANTE] NVARCHAR(500) NULL,
        [MARCADO_EN] DATETIME2(0) NOT NULL
            CONSTRAINT [DF_faltantes_picking_MARCADO_EN] DEFAULT (SYSDATETIME()),
        [MARCADO_POR] NVARCHAR(100) NOT NULL,
        [DESMARCADO_EN] DATETIME2(0) NULL,
        [DESMARCADO_POR] NVARCHAR(100) NULL,
        CONSTRAINT [CK_faltantes_picking_cierre] CHECK (
            ([DESMARCADO_EN] IS NULL AND [DESMARCADO_POR] IS NULL)
            OR ([DESMARCADO_EN] IS NOT NULL AND [DESMARCADO_POR] IS NOT NULL)
        )
    );

    CREATE UNIQUE INDEX [UX_faltantes_picking_activo]
        ON [CAB].[faltantes_picking] ([ID_PICKING])
        WHERE [DESMARCADO_EN] IS NULL;

    CREATE INDEX [IX_faltantes_picking_pedido_historial]
        ON [CAB].[faltantes_picking] ([NUMEROPEDIDO], [MARCADO_EN] DESC);
END;
GO

/* Adaptar también las instalaciones que ya tienen el historial de Picking. */
IF COL_LENGTH(N'CAB.faltantes_picking', N'MOTIVO_FALTANTE') IS NULL
BEGIN
    ALTER TABLE [CAB].[faltantes_picking]
        ADD [MOTIVO_FALTANTE] NVARCHAR(500) NULL;
END;
GO

/* Cierra episodios activos que ya estaban leídos antes de instalar el trigger. */
UPDATE fp
SET [DESMARCADO_EN] = SYSDATETIME(),
    [DESMARCADO_POR] = N'AUTOMATICO_LEIDO'
FROM [Digitalizacion].[CAB].[faltantes_picking] fp
INNER JOIN [Datalake].[dbo].[GPE_PEDIDOS_PRODUCTOS_PICKING_TRIGGER_CONTROL_CAMBIOS] p
    ON p.[id] = fp.[ID_PICKING]
WHERE fp.[DESMARCADO_EN] IS NULL
  AND ISNULL(p.[LEIDO], 0) = 1;
GO

USE [Datalake];
GO

CREATE OR ALTER TRIGGER [dbo].[TR_GPE_PICKING_CerrarFaltanteLeido]
ON [dbo].[GPE_PEDIDOS_PRODUCTOS_PICKING_TRIGGER_CONTROL_CAMBIOS]
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE fp
    SET [DESMARCADO_EN] = SYSDATETIME(),
        [DESMARCADO_POR] = N'AUTOMATICO_LEIDO'
    FROM [Digitalizacion].[CAB].[faltantes_picking] fp
    INNER JOIN inserted i ON i.[id] = fp.[ID_PICKING]
    WHERE fp.[DESMARCADO_EN] IS NULL
      AND ISNULL(i.[LEIDO], 0) = 1;
END;
GO
