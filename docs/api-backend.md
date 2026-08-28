# API del backend — DIMENSIA

Documentación de los endpoints expuestos por el backend Flask (`app.py`). Todos los endpoints devuelven JSON y corren por defecto en `http://<IP_notebook>:5000`.

## Inspecciones

### `POST /inspeccion`
Registra una nueva inspección, generalmente enviada por la Raspberry Pi al finalizar la medición de una pieza.

**Body de ejemplo:**
```json
{
  "pieza": "Niple NPT 1/2\"",
  "alto": 21.3,
  "ancho": 26.7,
  "largo": 58.0,
  "resultado": "APROBADA",
  "operario": "Juan Perez",
  "legajo": "1042",
  "numero_serie": "DIM-20260828-001"
}
```

Si `resultado` es `"RECHAZADA"`, el backend calcula automáticamente el campo `motivo_rechazo` comparando las dimensiones recibidas contra la referencia y tolerancia cargada para esa pieza, y lo guarda junto al registro.

**Respuesta:**
```json
{ "estado": "ok", "mensaje": "Inspeccion guardada" }
```

### `GET /inspecciones`
Devuelve el historial completo de inspecciones registradas, ordenadas de la más reciente a la más antigua.

**Respuesta (ejemplo, un registro):**
```json
{
  "id": 2,
  "pieza": "Niple NPT 1/2\"",
  "numero_serie": "DIM-20260828-001",
  "alto": 21.3,
  "ancho": 26.7,
  "largo": 58.0,
  "resultado": "APROBADA",
  "motivo_rechazo": null,
  "fecha": "2026-08-28 09:23:58",
  "operario": "Juan Perez",
  "legajo": "1042"
}
```

### `GET /exportar`
Genera y descarga un archivo CSV con el historial completo de inspecciones. Usa `;` como separador y la línea `sep=;` al inicio para compatibilidad con Excel en español.

## Piezas

### `POST /piezas`
Crea un nuevo tipo de pieza con sus valores de referencia y tolerancia.

**Body de ejemplo:**
```json
{
  "nombre": "Niple NPT 1/2\"",
  "norma": "ASME B16.11",
  "alto_ref": 21.3, "alto_tol": 0.5,
  "ancho_ref": 26.7, "ancho_tol": 0.5,
  "largo_ref": 58.0, "largo_tol": 1.0
}
```

### `GET /piezas`
Devuelve todas las piezas registradas, ordenadas por nombre.

## Calibración

### `POST /calibracion`
Guarda un nuevo registro de calibración de las cámaras.

**Body de ejemplo:**
```json
{ "px_por_mm_superior": 4.32, "px_por_mm_lateral": 4.28 }
```

### `GET /calibracion`
Devuelve el último registro de calibración guardado.

### `GET /calibraciones`
Devuelve las últimas 5 calibraciones registradas, ordenadas de la más reciente a la más antigua. Usado por el panel de calibración del dashboard para mostrar historial, consistencia entre cámaras y vigencia.

## Estado en tiempo real

### `POST /sensores` / `GET /sensores`
Recibe y devuelve el estado de los 3 sensores de presencia (S1, S2, S3).

### `POST /plato` / `GET /plato`
Recibe y devuelve el estado del plato giratorio: si está girando, el ángulo actual y las capturas completadas del ciclo.

### `POST /captura` / `GET /captura`
Recibe y devuelve el progreso de capturas del ciclo actual (de 0 a 8).

### `POST /servos` / `GET /servos`
Recibe y devuelve el estado de los 3 servos (empuje al plato, salida aprobada, rechazador). Acepta tanto booleanos (`true`/`false`) como strings (`"activo"`/`"reposo"`) para el estado de cada servo.

## Operario

### `POST /operario_activo`
Registra el operario que está de turno.

### `GET /operario_activo`
Devuelve el operario actualmente activo. Si una inspección llega sin datos de operario, el backend completa automáticamente `operario` y `legajo` con el operario activo registrado.

## Notas técnicas

- Todas las fechas se guardan y devuelven en horario de Argentina (UTC-3), mediante el helper `fecha_arg()` en `database.py`.
- La base de datos es SQLite (`dimensia.db`), sin persistencia distribuida — corre localmente junto al backend.
- El backend usa CORS habilitado para permitir que el dashboard (servido en otro puerto) consuma la API sin restricciones.
