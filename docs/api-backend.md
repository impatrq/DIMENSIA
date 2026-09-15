# API del backend — DIMENSIA

Documentación de los endpoints expuestos por el backend Flask (`app.py`). Todos los endpoints devuelven JSON (salvo donde se indique lo contrario) y corren por defecto en `http://<IP_notebook>:5000`.

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
  "numero_serie": "DIM-20260828-001",
  "captura_superior": "<base64 de la imagen JPG>",
  "captura_lateral": "<base64 de la imagen JPG>"
}
```

Si `resultado` es `"RECHAZADA"`, el backend calcula automáticamente el campo `motivo_rechazo` comparando las dimensiones recibidas contra la referencia y tolerancia cargada para esa pieza.

Los campos `captura_superior` y `captura_lateral` son opcionales (strings en base64 de una imagen JPG). Si se envían, el backend las decodifica y guarda como archivos en la carpeta `capturas/`, registrando la referencia en la base de datos.

**Respuesta:**
```json
{ "estado": "ok", "mensaje": "Inspeccion guardada" }
```

### `GET /inspecciones`
Devuelve el historial completo de inspecciones registradas, ordenadas de la más reciente a la más antigua.

### `GET /exportar`
Genera y descarga un archivo CSV con el historial completo de inspecciones. Usa `;` como separador y la línea `sep=;` al inicio para compatibilidad con Excel en español.

## Capturas de cámara

### `GET /capturas/<inspeccion_id>`
Devuelve las URLs relativas de las imágenes disponibles para una inspección.

**Respuesta de ejemplo:**
```json
{ "superior": "/capturas/1/superior.jpg", "lateral": "/capturas/1/lateral.jpg" }
```

Si una captura no existe para esa inspección, su valor es `null`.

### `GET /capturas/<inspeccion_id>/<tipo>.jpg`
Sirve el archivo de imagen real. `tipo` debe ser `superior` o `lateral`; cualquier otro valor devuelve 404. Si el archivo no existe, también devuelve 404.

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

### `POST /pieza_activa`
Registra la pieza seleccionada para el turno/ciclo actual. El operario la elige desde el dashboard (sección "Tipos de piezas") antes de iniciar el ciclo físico.

**Body de ejemplo:**
```json
{ "pieza": "Niple NPT 1/2\"" }
```

### `GET /pieza_activa`
Devuelve la pieza actualmente activa. La Raspberry Pi la consulta antes de esperar el inicio del ciclo (botón físico), para saber contra qué referencia y tolerancias va a medir.

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
Devuelve las últimas 5 calibraciones registradas, ordenadas de la más reciente a la más antigua.

## Estado del sistema (elevador)

### `POST /sensores` / `GET /sensores`
Recibe y devuelve el estado del elevador: final de carrera superior, final de carrera inferior y si la puerta de carga está cerrada.

**Formato:**
```json
{
  "final_carrera_superior": false,
  "final_carrera_inferior": true,
  "puerta_cerrada": true
}
```

*(Reemplaza el formato anterior de sensores de presencia S1/S2/S3, correspondiente a la arquitectura con cinta transportadora ya descontinuada.)*

### `POST /estado_ciclo` / `GET /estado_ciclo`
Recibe y devuelve el estado actual de la máquina de estados del ciclo de inspección.

**Valores permitidos:** `IDLE`, `SUBIENDO`, `MIDIENDO`, `PROCESANDO`, `DECISION`, `BAJANDO`, `INCLINANDO_PLATAFORMA`, `EMPUJANDO`, `CLASIFICADO`.

Si se envía un valor fuera de esta lista, el POST devuelve 400 con un mensaje de error.

### `POST /alerta_hardware`
Registra una alerta de falla de hardware (por ejemplo, timeout del elevador al subir).

**Body de ejemplo:**
```json
{ "tipo": "elevador", "mensaje": "Falla al subir" }
```

### `GET /alerta_hardware`
Devuelve el estado de la alerta actual: `activa` (bool), `tipo`, `mensaje` y `fecha`. Si nunca se registró ninguna alerta, `activa` es `false` y el resto `null`.

### `POST /alerta_hardware/resolver`
Marca la alerta actual como resuelta (`activa: false`), sin borrar el `tipo`, `mensaje` ni `fecha` del último registro.

## Servos

### `POST /servos` / `GET /servos`
Recibe y devuelve el estado de los 3 servos del sistema de elevación y clasificación:

**Formato:**
```json
{
  "rotacion":   { "activo": true, "nombre": "Rotacion del plato" },
  "empujador":  { "activo": false, "nombre": "Brazo empujador" },
  "plataforma": { "posicion": "izquierda", "nombre": "Plataforma clasificadora" }
}
```

- `rotacion` y `empujador` aceptan booleanos o strings (`"activo"`/`"reposo"`).
- `plataforma` acepta el string `"centro"`, `"izquierda"` o `"derecha"`; cualquier otro valor se ignora sin romper el request.

*(Reemplaza el formato anterior de servo1/servo2/servo3 correspondiente a la arquitectura con cinta transportadora.)*

## Captura y plato (informativos para el dashboard)

### `POST /captura` / `GET /captura`
Recibe y devuelve el progreso de capturas del ciclo actual.

### `POST /plato` / `GET /plato`
Recibe y devuelve el estado del plato giratorio: si está girando y el ángulo actual (donde aplique). Es informativo para el dashboard — el control real de la rotación se hace por comunicación Serial directa entre la Raspberry Pi y la ESP32.

## Operario

### `POST /operario_activo`
Registra el operario que está de turno.

### `GET /operario_activo`
Devuelve el operario actualmente activo. Si una inspección llega sin datos de operario, el backend completa automáticamente `operario` y `legajo` con el operario activo registrado.

## Notas técnicas

- Todas las fechas se guardan y devuelven en horario de Argentina (UTC-3), mediante el helper `fecha_arg()` en `database.py`.
- La base de datos es SQLite (`dimensia.db`), sin persistencia distribuida — corre localmente junto al backend.
- El backend usa CORS habilitado para permitir que el dashboard (servido en otro puerto) consuma la API sin restricciones.
- Las imágenes de capturas se guardan como archivos en el filesystem del backend (carpeta `capturas/`), no en la base de datos — solo se guarda la ruta.
