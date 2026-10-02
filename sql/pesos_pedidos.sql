/* Peso único por pedido para Picking CAB.
   Ejecutar en SQL Server sobre Digitalizacion antes de habilitar la edición.
   Es repetible y conserva los pesos ya registrados. */
USE [Digitalizacion];
GO

SET XACT_ABORT ON;
GO

IF SCHEMA_ID(N'CAB') IS NULL
    EXEC(N'CREATE SCHEMA [CAB] AUTHORIZATION [dbo];');
GO

IF OBJECT_ID(N'[CAB].[PesosPedidos]', N'U') IS NULL
BEGIN
    CREATE TABLE [CAB].[PesosPedidos] (
        [Pedido] NVARCHAR(50) NOT NULL,
        [PesoKg] DECIMAL(12,3) NULL,
        [FechaModificacion] DATETIME2(0) NOT NULL
            CONSTRAINT [DF_CAB_PesosPedidos_FechaModificacion] DEFAULT (SYSDATETIME()),
        [ModificadoPor] NVARCHAR(100) NOT NULL,
        CONSTRAINT [PK_CAB_PesosPedidos] PRIMARY KEY ([Pedido]),
        CONSTRAINT [CK_CAB_PesosPedidos_PesoKg]
            CHECK ([PesoKg] IS NULL OR [PesoKg] >= 0)
    );
END;
GO
