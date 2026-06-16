# Implementación: Nombres Personalizados de Columnas en Puestos CAB

## Descripción General
Se ha implementado la funcionalidad de editar los nombres de las columnas en Crearpuesto.html. Los nombres personalizados se guardan en el campo `Nombre` de la tabla `PuestosColumnas` y se muestran como cabeceras en la pantalla PuestoCAB.html.

## Cambios Realizados

### 1. Frontend - Crearpuesto.html

#### 1.1 Modificación de estructura de datos
- **Antes**: `columnasElegidas` era un array de strings con códigos: `['CODLINEA', 'GFH']`
- **Ahora**: Es un array de objetos con código y nombre: `[{codigo: 'CODLINEA', nombre: 'Código Línea'}, ...]`

#### 1.2 Función `agregarColumnas()`
- Convierte los strings a objetos con estructura `{codigo: codigoColumna, nombre: nombreColumna}`
- El nombre inicial es igual al código original de la columna

#### 1.3 Función `actualizarColumnasSeleccionadas()`
- Muestra las columnas como tags azules con nombres editables
- Cada nombre es clickeable (cursor pointer)
- Mantiene compatibilidad con formato antiguo (strings) convirtiéndolos automáticamente

#### 1.4 Nueva función `editarNombreColumna(index)`
- Se invoca con un click sobre el nombre de la columna
- Abre un prompt para que el usuario ingrese el nuevo nombre
- Actualiza el objeto en `columnasElegidas[index]`
- Recarga la visualización de columnas

#### 1.5 Función `removerColumna(codigoColumna)`
- Actualizada para trabajar con la nueva estructura de objetos
- Filtra por `codigo` del objeto en lugar de string

### 2. Backend - app.py

#### 2.1 Endpoint `/api/crear-puesto` (POST)
- Al insertar en `PuestosColumnas`, ahora guarda ambos campos:
  - `Columna`: código original de la columna (ej: 'DESCRIPCIONPIEZA')
  - `Nombre`: nombre personalizado (ej: 'Descripción de Pieza')
- Maneja compatibilidad con formato anterior (strings)

```python
cursor.execute("""
    INSERT INTO [Digitalizacion].[CAB].[PuestosColumnas] 
    (ID_Puesto, Columna, Orden, Nombre)
    VALUES (?, ?, ?, ?)
""", (nuevo_id, columna_codigo, index + 1, columna_nombre))
```

#### 2.2 Endpoint `/api/modificar-puesto` (PUT)
- Similar a crear-puesto
- Elimina las columnas antiguas y reinsertas con los nuevos nombres

#### 2.3 Endpoint `/api/puesto-datos/<nombre_puesto>` (GET)
- Devuelve columnas como objetos con `codigo` y `nombre`
- Permite cargar puestos en modo edición manteniendo nombres personalizados

```python
columnas.append({
    'codigo': columna_codigo,
    'nombre': columna_nombre
})
```

#### 2.4 Endpoint `/api/puesto-columnas/<codigo_puesto>` (GET) - SIMPLIFICADO
- **Cambio principal**: Devuelve directamente el campo `Nombre` en lugar del campo `Columna`
- `Nombre` puede ser:
  - El nombre personalizado si el usuario lo editó
  - El código original de la columna si no se editó

```python
cursor.execute("""
    SELECT Nombre
    FROM [Digitalizacion].[CAB].[PuestosColumnas]
    WHERE ID_Puesto = ?
    ORDER BY ISNULL(Orden, 999), Orden, Nombre
""", (id_puesto,))

columnas = [row[0] for row in resultados if row[0]]
```

### 3. Frontend - PuestoCAB.html

- Recibe directamente los nombres personalizados del endpoint `/api/puesto-columnas/<codigo_puesto>`
- Los nombres se muestran como cabeceras de la tabla
- Si el usuario editó el nombre: se muestra el personalizado
- Si no: se muestra el código original

## Flujo de Funcionamiento

### Crear Nuevo Puesto
1. Usuario agrega columnas en Crearpuesto.html
2. Sistema crea objetos `{codigo, nombre}` automáticamente
3. Usuario hace click en una columna para editar su nombre
4. Nombre se actualiza en el array `columnasElegidas`
5. Al guardar, se envía array de objetos al endpoint `/api/crear-puesto`
6. Endpoint inserta en BD:
   - `Columna`: código original
   - `Nombre`: nombre personalizado

### Modificar Puesto Existente
1. Usuario selecciona puesto existente
2. Endpoint `/api/puesto-datos/<nombre_puesto>` devuelve objetos con códigos y nombres
3. Se cargan en modo edición con nombres personalizados
4. Usuario puede editar más nombres haciendo click
5. Al guardar, se actualiza la BD

### Ver Puesto en PuestoCAB.html
1. Se carga el puesto con parámetro URL
2. Endpoint `/api/puesto-columnas/<codigo_puesto>` devuelve array de nombres
3. Los nombres aparecen como cabeceras de tabla

## Estructura de BD

### Tabla: `[Digitalizacion].[CAB].[PuestosColumnas]`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| ID_PuestoColumna | INT | Clave primaria |
| ID_Puesto | INT | FK a tabla Puestos |
| Columna | NVARCHAR | Código original de la columna |
| Nombre | NVARCHAR | Nombre personalizado (nuevo) |
| Orden | INT | Orden de visualización |
| FechaModificacion | DATETIME | Fecha última modificación |

### Ejemplo de datos

| ID_Puesto | Columna | Nombre | Orden |
|-----------|---------|--------|-------|
| 1 | NumeroPedido | Número de Pedido | 1 |
| 1 | DESCRIPCIONPIEZA | Descripción | 2 |
| 1 | TiempoTotal | Tiempo Total (min) | 3 |

## Compatibilidad

- ✅ Funciona con puestos antiguos (guarda automáticamente campo `Nombre` igual a `Columna`)
- ✅ Mantiene compatibilidad con código antiguo que devolvía solo strings
- ✅ Si campo `Nombre` es NULL, usa valor de `Columna`

## Testing

Para probar la funcionalidad:

1. **Crear Puesto Nuevo**
   - Ir a Crearpuesto.html
   - Crear nuevo puesto
   - Agregar columnas
   - Hacer click en nombres para personalizarlos
   - Guardar y verificar en BD

2. **Modificar Puesto**
   - Seleccionar puesto existente
   - Editar nombres de columnas
   - Guardar cambios

3. **Ver en PuestoCAB.html**
   - Ir a pantalla de puesto
   - Verificar que cabeceras muestren nombres personalizados

## Notas Importantes

- El campo `Columna` sigue siendo el identificador único de la columna en el sistema
- El campo `Nombre` es solo para visualización
- Los cambios son retroactivos: puestos antiguos funcionarán mostrando el código como nombre
