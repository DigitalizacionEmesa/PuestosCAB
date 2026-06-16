# Cambios Implementados - Nombres Personalizados de Columnas

## Resumen
Se ha implementado la funcionalidad de editar nombres personalizados para las columnas en la pantalla de configuración de puestos (`Crearpuesto.html`). Los cambios se guardan en la base de datos y se muestran correctamente en la pantalla de puestos (`PuestoCAB.html`).

---

## 1. Cambios en Crearpuesto.html

### 1.1 Modificar estructura de `columnasElegidas`
**Cambio**: De array de strings a array de objetos
```javascript
// ANTES:
columnasElegidas = ['CODLINEA', 'DESCRIPCIONPIEZA', 'MODELO']

// AHORA:
columnasElegidas = [
  { codigo: 'CODLINEA', nombre: 'CODLINEA' },
  { codigo: 'DESCRIPCIONPIEZA', nombre: 'Descripción de Pieza' },
  { codigo: 'MODELO', nombre: 'Modelo' }
]
```

### 1.2 Función `agregarColumnas`
- Ahora crea objetos con estructura `{codigo, nombre}` 
- El nombre inicial es igual al código/nombre original
- Detecta duplicados por código

### 1.3 Función `editarNombreColumna` (NUEVA)
- Se invoca al hacer clic sobre el nombre de una columna ya agregada
- Abre un `prompt` para que el usuario ingrese el nuevo nombre
- Actualiza el nombre en el objeto correspondiente
- Refresca la visualización
- Soporta conversión de formato string a objeto si es necesario

### 1.4 Función `actualizarColumnasSeleccionadas`
- Actualiza la visualización con nombres editables
- Los nombres son clicables (cursor pointer)
- Convierte automáticamente formato string a objeto para compatibilidad
- Muestra números de orden y botones para reordenar

### 1.5 Función `removerColumna`
- Ahora busca por código en el nuevo formato de objeto
- Mantiene compatibilidad con strings heredados

---

## 2. Cambios en app.py

### 2.1 Endpoint `/api/crear-puesto` (POST)
**Cambios**:
- Ahora procesa `columnasElegidas` como array de objetos O strings
- Extrae `codigo` y `nombre` de cada columna
- Guarda AMBOS campos en la tabla `PuestosColumnas`:
  - `Columna`: código original
  - `Nombre`: nombre personalizado o código si no fue personalizado

```python
INSERT INTO [Digitalizacion].[CAB].[PuestosColumnas]
(ID_Puesto, Columna, Orden, Nombre)
VALUES (?, ?, ?, ?)
```

### 2.2 Endpoint `/api/modificar-puesto` (PUT)
**Cambios idénticos al de crear**, ahora:
- Elimina columnas anteriores
- Inserta nuevas columnas con estructura actualizada
- Guarda nombres personalizados

### 2.3 Endpoint `/api/puesto-columnas/<codigo_puesto>` (GET)
**Cambio más importante - SIMPLIFICACIÓN**:
- **ANTES**: Devolvía solo `Columna` (código original)
- **AHORA**: Devuelve directamente `Nombre` (nombre personalizado o código)

```python
# Query actualizado:
SELECT Nombre  # ← Cambio clave
FROM [Digitalizacion].[CAB].[PuestosColumnas]
WHERE ID_Puesto = ?
ORDER BY ISNULL(Orden, 999), Orden, Nombre
```

**Response**:
```json
{
  "success": true,
  "columnas": ["CODLINEA", "Descripción de Pieza", "Modelo"],  // ← Nombres directamente
  "total": 3,
  "puesto_nombre": "Clinchado",
  "color_pantalla": "#87CEEB",
  "message": "Columnas configuradas para Clinchado"
}
```

### 2.4 Endpoint `/api/puesto-datos/<nombre_puesto>` (GET)
**Cambios**:
- Devuelve columnas como array de objetos con `codigo` y `nombre`
- Usado por Crearpuesto.html al cargar puesto para editar

```python
columnas.append({
    'codigo': columna_codigo,
    'nombre': columna_nombre
})
```

---

## 3. Cambios en PuestoCAB.html

### 3.1 Función `cargarColumnasConfiguradas`
**Simplificación**:
- Ahora `data.columnas` contiene directamente los nombres personalizados
- No necesita mapeo adicional `columnasOriginalesBD = data.columnas`
- Código más limpio y directo

### 3.2 Función `generarHeaderTabla`
**Cambios**:
- Usa directamente `columnasConfiguradas[index]` como nombre para header
- Elimina lógica de mapeo con `obtenerNombreColumna`
- Los headers muestran exactamente lo que se guardó en BD

**Antes**:
```javascript
const nombreOriginalBD = columnasOriginalesBD[index] || columna;
headerText.textContent = obtenerNombreColumna(nombreOriginalBD);
```

**Ahora**:
```javascript
const nombreColumna = columnasConfiguradas[index];
headerText.textContent = nombreColumna;
```

---

## 4. Tabla de Base de Datos

La tabla `[Digitalizacion].[CAB].[PuestosColumnas]` ya tenía el campo `Nombre`, ahora se utiliza de la siguiente manera:

| Campo | Uso |
|-------|-----|
| `ID_PuestoColumna` | PK - Identificador único |
| `ID_Puesto` | FK - Relacionado con Puestos |
| `Columna` | Código original de la columna (ej: "DESCRIPCIONPIEZA") |
| `Nombre` | **NUEVO USO**: Nombre personalizado o código si no se personaliza |
| `Orden` | Posición en la tabla (1, 2, 3...) |
| `FechaModificacion` | Timestamp automático |

---

## 5. Flujo Completo

### 5.1 Creación de Puesto
1. Usuario abre Crearpuesto.html
2. Selecciona columnas → se agregan con `{codigo, nombre}` donde nombre = código
3. Usuario hace clic en columna → `editarNombreColumna` permite cambiar nombre
4. Usuario guarda → API recibe array de objetos `{codigo, nombre}`
5. BD: Se guardan ambos campos en `PuestosColumnas`

### 5.2 Visualización en PuestoCAB.html
1. Se carga `columnasConfiguradas` con valores del campo `Nombre` de BD
2. Headers se generan automáticamente con esos nombres
3. Usuarios ven "Descripción de Pieza" en lugar de "DESCRIPCIONPIEZA"

### 5.3 Edición de Puesto
1. Usuario selecciona puesto en Crearpuesto.html
2. Endpoint `/api/puesto-datos` devuelve columnas como `{codigo, nombre}`
3. Se cargan en `columnasElegidas` en nuevo formato
4. Usuario puede editar nombres nuevamente
5. Al guardar, todo se actualiza correctamente

---

## 6. Compatibilidad

- ✅ Código heredado que usa strings en `columnasElegidas` se convierte automáticamente
- ✅ Campos `Nombre` NULL en BD se reemplazan con el código
- ✅ Puestos existentes sin nombres personalizados funcionan sin cambios
- ✅ No requiere cambios en PuestoCAB.html para datos históricos

---

## 7. Ejemplo de Uso

### Crear Puesto con Nombres Personalizados

**Request POST `/api/crear-puesto`**:
```json
{
  "nombre_puesto": "Clinchado",
  "codigo_puesto": "CLINCAB1",
  "columnas": [
    { "codigo": "CODLINEA", "nombre": "Código de Línea" },
    { "codigo": "DESCRIPCIONPIEZA", "nombre": "Descripción de Pieza" },
    { "codigo": "TIEMPOESTÁNDAR", "nombre": "Tiempo Estándar (min)" }
  ],
  "color_pantalla": "#FFB6C1"
}
```

**BD - Resultado en `PuestosColumnas`**:
| ID_Puesto | Columna | Nombre | Orden |
|-----------|---------|--------|-------|
| 5 | CODLINEA | Código de Línea | 1 |
| 5 | DESCRIPCIONPIEZA | Descripción de Pieza | 2 |
| 5 | TIEMPOESTÁNDAR | Tiempo Estándar (min) | 3 |

**PuestoCAB.html - Headers mostrados**:
```
[Código de Línea] | [Descripción de Pieza] | [Tiempo Estándar (min)] | ...
```

---

## 8. Validaciones

- ✅ Campo `Nombre` se valida como string no vacío
- ✅ No se permiten duplicados de `Columna` en el mismo puesto
- ✅ Orden se mantiene automáticamente
- ✅ Sincronización automática entre frontend y BD

---

## 9. Notas Importantes

1. **El campo `Columna` nunca cambia**: Siempre guarda el código original
2. **El campo `Nombre` es lo que se muestra**: Contiene el nombre personalizado
3. **Sin necesidad de migración**: Registros existentes funcionan sin cambios
4. **Limpieza de código**: Se eliminó lógica de mapeo innecesaria en PuestoCAB.html
5. **Mejor mantenimiento**: Ahora la fuente de verdad es directamente la BD

