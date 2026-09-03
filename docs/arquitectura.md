# Arquitectura del sistema DIMENSIA

## Descripción general

DIMENSIA es una estación automatizada de control dimensional para piezas de tornería industrial de geometría variable (5-15cm). El operario carga la pieza manualmente en un único punto físico; el sistema la eleva, mide sus dimensiones mediante visión artificial, decide si aprueba o rechaza, y la clasifica automáticamente en uno de dos compartimentos de salida.

## Diagrama de flujo

ESP32-S3 (control de actuadores + pantalla)
        |
        | UART
        v
Raspberry Pi 4 (OpenCV + camaras + logica de decision)
        |
        | HTTP (POST /inspeccion, /sensores, /estado_ciclo, /servos, /captura)
        v
Backend Flask + SQLite (notebook)
        |
        | HTTP (GET /inspecciones, /calibracion, /estado_ciclo, etc.)
        v
Dashboard web (HTML/CSS/JavaScript)

## Estructura física

Gabinete de MDF sobre 4 patas de caño soldadas (15cm de altura). Se divide en dos zonas:
- **Compartimento de electrónica**, aislado con puerta propia.
- **Zona de elevador y clasificación**, abiertas entre sí para permitir que la pieza pase físicamente de una etapa a la otra.

## Componentes

### 1. Elevador
Un motor **NEMA17** conectado por acople flexible a un husillo **T8** (varilla roscada), fijo en sus puntas por bujes roscados M8 — gira sobre su propio eje sin trasladarse. La tuerca T8, atornillada al carro, sube y baja por la rosca porque el carro no puede girar: 2 varillas guía y 2 rodamientos LM8UU (en manguitos de 24mm) lo mantienen recto. **2 finales de carrera** (superior e inferior) definen las posiciones de parada — no se cuentan pasos, se espera el contacto físico del switch. El motor se controla mediante un driver **TMC2208** por señales STEP/DIR.

### 2. Rotación y plato
Un **servo MG996R de rotación continua (360°)**, montado sobre el carro y apoyado en un rodamiento tipo lazy susan, gira el plato. A diferencia de un motor paso a paso, **este servo no tiene feedback de ángulo** — el control es por tiempo (se le indica cuánto tiempo girar para aproximar cada parada, por ejemplo 8 paradas por vuelta completa). El plato (200mm de diámetro) no tiene guía física de centrado, solo una marca visual; el operario apoya la pieza a ojo cerca del centro.

### 3. Sellado y control de luz
Al llegar arriba, el plato comprime una junta de goma que sella la caja de medición contra la luz externa — solo el plato entra a esa zona, el resto del mecanismo queda afuera. Esto resuelve la dependencia de las condiciones de iluminación ambiente que se había señalado como limitación en versiones anteriores del diseño.

### 4. Seguridad de carga
Una compuerta de carga con bisagra tiene su propio **microswitch**. El ciclo no puede arrancar si el switch no confirma que la puerta está cerrada — es la primera condición de la máquina de estados.

### 5. Sensado por visión artificial
- **Cámara superior fija:** toma 1 foto por ciclo, usada para medir diámetro exterior y otras dimensiones visibles desde arriba.
- **Cámara lateral con retroiluminación:** rota junto con el plato y toma 1 foto en cada parada de rotación (por ejemplo, cada 45° — 8 fotos por vuelta), midiendo el largo y el alto por silueta (threshold binario). Esto cubre todas las caras de la pieza, incluso con geometría irregular.

Cada medición en píxeles se convierte a milímetros dentro de `procesamiento.py`, dividiendo por el factor de calibración correspondiente (`px_por_mm_superior` o `px_por_mm_lateral`), calculado una única vez por cámara mediante `calibracion_camaras.py`. Los valores en mm de las 8 capturas se promedian para reducir el error de medición puntual — el mismo principio de reducción de ruido que se usaba en la arquitectura anterior basada en sensores ToF.

Las 2 cámaras (Logitech C920e) se conectan a la Raspberry Pi mediante un acoplador USB doble de panel.

### 6. Decisión
La Raspberry Pi compara las medidas promediadas contra la referencia y tolerancia cargada para el tipo de pieza (`alto_ref`, `ancho_ref`, `largo_ref` y sus tolerancias), determinando el resultado: **ACEPTADA** o **RECHAZADA**. Si es rechazada, además se calcula qué dimensión específica quedó fuera de tolerancia (ver sección "Trazabilidad del motivo de rechazo").

### 7. Clasificación
1. El plato baja hasta el final de carrera inferior.
2. Un **servo SG90** inclina una **plataforma basculante** hacia el lado correspondiente al resultado (izquierda = aceptadas, derecha = rechazadas) — el camino de salida se define *antes* de mover la pieza.
3. Un **servo MG996R de 180°** con brazo reforzado (190mm) empuja la pieza fuera del plato. Este movimiento es siempre igual, sin importar el resultado — no requiere lógica condicional.
4. La pieza cae por gravedad, pasa por la plataforma ya inclinada, y rueda a uno de los 2 canales de salida, terminando en un compartimento transparente con puerta propia y cierre magnético.

### 8. Electrónica y alimentación
El sistema usa **3 rieles de alimentación separados**, con GND común:
- **12V:** motor NEMA17 y LEDs de iluminación.
- **5V dedicado:** exclusivo para la Raspberry Pi.
- **6V:** los 3 servos (rotación, empujador, plataforma) y el ESP32.

Esta separación evita que los picos de corriente de los servos al activarse simultáneamente puedan resetear la Raspberry Pi (brownout).

El **ESP32-S3** tiene una pantalla propia que muestra el estado y los resultados del ciclo, y se comunica con la Raspberry Pi por **UART**.

## Resumen de entradas y salidas para control

| Tipo | Cantidad | Detalle |
|---|---|---|
| Entradas digitales (GPIO) | 3 | Final de carrera superior, final de carrera inferior, switch de puerta cerrada |
| Salidas PWM (servos) | 3 | Rotación (360°, control por tiempo), empujador (180°, posicional), plataforma (SG90, posicional) |
| Control de motor | 1 | Driver TMC2208 → NEMA17 (elevador), por STEP/DIR |
| Cámaras USB | 2 | Superior (1 foto por ciclo) y lateral (1 foto por cada parada de rotación) |

## Máquina de estados del ciclo

IDLE (puerta cerrada)
→ SUBIENDO (hasta final de carrera superior)
→ MIDIENDO (camara superior + N fotos laterales con rotacion por tiempo)
→ PROCESANDO (OpenCV + calculo de mm)
→ DECISION (aceptada/rechazada)
→ BAJANDO (hasta final de carrera inferior)
→ INCLINANDO_PLATAFORMA (segun resultado, servo SG90)
→ EMPUJANDO (servo MG996R 180°, siempre igual)
→ CLASIFICADO
→ IDLE


El backend expone este estado mediante el endpoint `GET /estado_ciclo`, y el dashboard lo muestra en tiempo real en el panel "Estado del sistema" de la pantalla Inspección en vivo.

## Trazabilidad del motivo de rechazo

Además de registrar si una pieza fue aprobada o rechazada, el sistema guarda el detalle de qué dimensión específica (`alto`, `ancho`, `largo`, o una combinación) quedó fuera de tolerancia. Este cálculo lo realiza el backend al recibir cada inspección, comparando los valores medidos contra la referencia y tolerancia de la pieza. Esta trazabilidad granular permite un diagnóstico más preciso de fallas en el proceso de fabricación.

## Simulación sin hardware

Para pruebas y demostraciones sin depender del hardware físico completo, el proyecto incluye:
- `raspberry/demo.py`: simula una sesión completa de inspecciones con datos generados dentro y fuera de tolerancia. Incluye un buffer local (`pendientes.jsonl`) que guarda las inspecciones que no se pudieron enviar al backend por fallas de conexión, y las reintenta automáticamente en la siguiente ejecución.
- `raspberry/verificar_sistema.py`: chequea que el backend esté disponible, que haya piezas cargadas y que exista la calibración antes de una demo.
- `raspberry/inicializar_db.py`: carga piezas de ejemplo en el backend si la base de datos está vacía.
- `raspberry/config.py`: centraliza la IP del backend para no tener que modificar el código cada vez que cambia la red.
- `raspberry/calibracion_camaras.py`: obtiene el factor px/mm de cada cámara a partir de un objeto de referencia con medida conocida.

## Notas sobre la migración de arquitectura

El sistema pasó por dos migraciones principales:

1. **De sensores ToF a visión artificial:** originalmente la medición se hacía con 5 sensores VL53L4CD por diferencia de distancia. Se reemplazó por un sistema de 2 cámaras con OpenCV, que ofrece mayor precisión y flexibilidad para piezas de geometría variable, sin sumar costo de hardware (las cámaras ya estaban disponibles).

2. **De sensores de presencia a elevador mecánico:** el diseño intermedio usaba 3 sensores de presencia (S1, S2, S3) sobre una cinta transportadora para detectar la posición de la pieza. El diseño final reemplazó la cinta por un elevador de carga única con husillo, controlado por finales de carrera físicos en vez de sensores de proximidad — esto simplificó el sistema de sensado a solo 3 entradas digitales (2 finales de carrera + 1 switch de puerta).

## Limitaciones conocidas y trabajo futuro

- **Manejo de errores en la comunicación Raspberry Pi - Backend:** *(resuelto)* se implementó un buffer local en `demo.py` que guarda las inspecciones no enviadas y las reintenta automáticamente al recuperar la conexión.
- **Control del servo de rotación sin feedback de ángulo:** al no tener realimentación de posición, el tiempo de giro para cada parada debe calibrarse experimentalmente y puede requerir ajuste si cambia la carga mecánica o la tensión de alimentación.
- **Recalibración de cámaras:** el procedimiento es manual, vía `calibracion_camaras.py` y el endpoint `/calibracion`. El dashboard muestra un indicador de vigencia (menos de 24hs) pero no dispara una alerta activa si está vencida.
- **Alineación de la pieza durante la rotación:** al no haber guía física de centrado en el plato, el campo de visión de la cámara lateral debe tener margen suficiente para tolerar que la pieza no esté perfectamente centrada.
- **Trazabilidad por ángulo de captura:** actualmente se guarda qué dimensión falló, pero no en qué ángulo específico de los 8 se detectó la falla — una mejora futura podría sumar ese detalle para diagnósticos más finos.

## Repositorio y ramas

- **`main`**: rama principal, código estable.
- **`Backend`**: desarrollo del backend Flask (Valentino).
- **`dashboard`**: desarrollo del dashboard web (Valentino).
- **`feature/vision-camaras`**: desarrollo del sistema de calibración y medición con cámaras (Gino) — mergeada a `main`.
- **`feature/simulacion`**: scripts de simulación para demos sin hardware (Gino) — mergeada a `main`.
