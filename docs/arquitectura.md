# Arquitectura del sistema DIMENSIA

## Descripción general

DIMENSIA es un sistema automatizado de control de calidad dimensional para piezas de tornería industrial. Una pieza avanza por una cinta transportadora, es medida mediante visión artificial con dos cámaras, y el sistema decide automáticamente si aprobarla o rechazarla según tolerancias predefinidas.

## Diagrama de flujo

ESP32 (sensores + servos)
        |
        | UART / GPIO
        v
Raspberry Pi 4 (OpenCV + camaras)
        |
        | HTTP (POST /inspeccion, /sensores, /plato, /servos, /captura)
        v
Backend Flask + SQLite (notebook)
        |
        | HTTP (GET /inspecciones, /calibracion, etc.)
        v
Dashboard web (HTML/CSS/JavaScript)


## Componentes

### 1. ESP32
Controla los actuadores físicos y sensores de presencia:
- **3 sensores VL53L4CD (S1, S2, S3):** detectan la posición de la pieza en la cinta y el plato giratorio. En la arquitectura actual solo cumplen función de presencia (no miden dimensiones).
- **Servo 1:** empuja la pieza desde la cinta hacia el plato giratorio.
- **Servo 2:** libera la pieza aprobada hacia la salida.
- **Servo 3:** desvía la pieza rechazada.
- **Plato giratorio:** rota la pieza en incrementos de 45° para que las cámaras capturen 8 ángulos distintos.

### 2. Raspberry Pi 4
Es el cerebro del procesamiento de imagen:
- Controla las 2 cámaras Logitech C920e (una superior, una lateral).
- Corre los scripts de captura y procesamiento con **OpenCV**.
- Convierte las medidas de píxeles a milímetros usando el factor de calibración (`px_por_mm_superior`, `px_por_mm_lateral`).
- Compara las dimensiones medidas contra los valores de referencia y tolerancias de cada tipo de pieza.
- Envía el resultado final al backend vía HTTP.

### 3. Backend (Flask + SQLite)
Corre en la notebook y centraliza todos los datos del sistema:
- Recibe las inspecciones, calibraciones y estados de sensores/servos desde la Raspberry Pi.
- Persiste todo en una base de datos SQLite (`dimensia.db`).
- Expone una API REST que consume el dashboard.
- Ver el detalle completo de endpoints en [`api-backend.md`](./api-backend.md).

### 4. Dashboard (HTML/CSS/JavaScript)
Interfaz web para el operario y para supervisión:
- **Dashboard principal:** estadísticas del turno, rendimiento por tipo de pieza, alerta de racha de rechazos.
- **Inspección en vivo:** estado en tiempo real de sensores, plato, servos y calibración.
- **Tipos de piezas:** alta y consulta de piezas con sus tolerancias, generación de QR.
- **Historial:** listado completo de inspecciones con filtros (tipo, estado, fecha, número de serie) y exportación a CSV.
- **Reportes:** resumen agregado por tipo de pieza (total, aprobadas, rechazadas, tasa de aprobación).

## Flujo de una inspección completa

1. La pieza ingresa a la cinta transportadora.
2. El sensor S1 detecta la presencia de la pieza.
3. El Servo 1 empuja la pieza hacia el plato giratorio.
4. Los sensores S2 y S3 confirman que la pieza está centrada y lista para rotar.
5. El plato gira en 8 pasos de 45°, y en cada paso las cámaras capturan una imagen.
6. La Raspberry Pi procesa las 8 imágenes con OpenCV, obtiene las dimensiones en píxeles y las convierte a milímetros con el factor de calibración vigente.
7. El sistema compara las dimensiones contra la referencia y tolerancia de la pieza cargada.
8. Según el resultado, se activa el Servo 2 (aprobada) o el Servo 3 (rechazada).
9. La Raspberry Pi envía el registro completo de la inspección al backend (`POST /inspeccion`).
10. El backend guarda el registro en la base de datos.
11. El dashboard consulta periódicamente el backend y actualiza la vista en tiempo real.

## Notas sobre la migración de arquitectura

El sistema originalmente medía las piezas con 5 sensores VL53L4CD por diferencia de distancia (sensores S1, S2, S2', S3, S3'). Esa arquitectura fue reemplazada por el sistema actual de visión artificial con cámaras, que ofrece mayor precisión y flexibilidad para distintos tipos de pieza. Los 3 sensores que quedan (S1, S2, S3) cumplen ahora solo función de detección de presencia y posicionamiento, no de medición.

## Simulación sin hardware

Para pruebas y demostraciones sin depender del hardware físico completo, el proyecto incluye:
- `raspberry/demo.py`: simula una sesión completa de inspecciones con datos generados aleatoriamente dentro y fuera de tolerancia.
- `raspberry/verificar_sistema.py`: chequea que el backend esté disponible, que haya piezas cargadas y que exista la calibración antes de una demo.
- `raspberry/inicializar_db.py`: carga piezas de ejemplo en el backend si la base de datos está vacía.
- `raspberry/config.py`: centraliza la IP del backend para no tener que modificar el código cada vez que cambia la red.

## Limitaciones conocidas y trabajo futuro

Durante la revisión de esta arquitectura, Joaquín Korylkiewicz señaló varios puntos que quedan documentados como limitaciones conocidas o decisiones pendientes, más que como fallas del diseño actual:

- **Manejo de errores en la comunicación Raspberry Pi - Backend:** actualmente si el `POST /inspeccion` falla (por ejemplo, caída de Wi-Fi o del backend), la inspección se pierde. No hay un buffer local en la Raspberry Pi que guarde y reintente el envío. Es una mejora pendiente para dar mayor robustez al sistema en la demo final.

- **Timeout de posicionamiento:** el paso en que los sensores S2 y S3 confirman que la pieza está centrada no tiene definido un timeout ni un estado de error si la pieza no logra posicionarse correctamente. Falta definir un estado de `error_posicionamiento` con reintento o expulsión automática.

- **Recalibración de cámaras:** el procedimiento de calibración (`px_por_mm_superior`, `px_por_mm_lateral`) es manual, vía el endpoint `/calibracion`. No hay una rutina automática que alerte si la última calibración es antigua o si las cámaras se desplazaron. El dashboard sí muestra un indicador de vigencia (menos de 24hs) en el panel de calibración, pero no dispara una alerta activa.

- **Condiciones de iluminación:** el sistema de visión artificial depende del contraste y la silueta de la pieza contra el fondo. No está documentado si el diseño final contempla un gabinete cerrado o una fuente de luz controlada para minimizar la variación de luz ambiente.

- **Backend como punto único de falla:** el backend corre en una notebook, lo que es adecuado para la demo pero representa un punto único de falla — si la notebook se cuelga, cae todo el sistema. Sumado a la falta de buffer local (ver primer punto), esto significa que una caída de la notebook implica pérdida de datos, no solo de visualización.

- **Trazabilidad del motivo de rechazo:** actualmente el historial guarda el resultado final (aprobada/rechazada) pero no el detalle de qué dimensión específica quedó fuera de tolerancia ni en qué ángulo de captura. Agregar esto mejoraría la capacidad de diagnóstico y los reportes técnicos.

- **Concurrencia:** el sistema está diseñado para procesar una pieza por vez en la cinta. No hay manejo de cola para múltiples piezas simultáneas.

- **Alimentación eléctrica:** no está documentado en esta arquitectura el esquema de alimentación de los servos y el ESP32 (fuente separada o compartida), lo cual es relevante para evitar brownouts si se activan varios servos al mismo tiempo.

Estos puntos no implican un cambio en el diseño general del sistema, pero son aspectos a resolver o documentar antes de la muestra final de noviembre.

## Repositorio y ramas

- **`main`**: rama principal, código estable.
- **`Backend`**: desarrollo del backend Flask (Valentino).
- **`dashboard`**: desarrollo del dashboard web (Valentino).
- **`feature/vision-camaras`**: desarrollo del sistema de calibración y medición con cámaras (Gino).
- **`feature/simulacion`**: scripts de simulación para demos sin hardware (Gino).
