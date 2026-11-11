# Ciclo automatizado vía Serial — DIMENSIA

Script: `raspberry/ciclo_serial.py`

## Qué hace

Corre en la Raspberry Pi y coordina la inspección completa de piezas
en modo automatizado, sin intervención manual:

1. **(Modo `--iniciar`)** Espera ENTER del operario, envía `INICIAR` a la ESP32.
2. Limpia el buffer serial y espera la señal `ARRIBA` de la ESP32.
3. Consulta `/pieza_activa` para actualizar la pieza del ciclo (si cambió en el dashboard, lo avisa).
4. Repite N pasos de rotación (default 8): limpia buffer, envía `PASO`, espera `PASO_OK`,
   espera 0.3 s a que el plato se asiente, captura frames frescos con ambas cámaras y mide.
   El ángulo de cada captura corresponde a la posición después del giro.
5. Calcula la **mediana** de las N mediciones (diámetro, largo, alto).
6. Evalúa contra las referencias de la pieza activa.
   Si hay menos de 4 mediciones o no se puede evaluar ninguna dimensión,
   el resultado es `RECHAZADA` y se registra igual en el backend.
7. Envía `FIN APROBADA` o `FIN RECHAZADA` a la ESP32 **inmediatamente**,
   antes del POST, para no superar el timeout de silencio de la ESP32 (30 s).
8. Envía un único `POST /inspeccion` **siempre** (incluso ciclos inválidos)
   con la captura más representativa (la más cercana a la mediana de diámetro).
   El POST se reintenta 3 veces; si persiste, el payload se guarda en `capturas/pendientes/`.
   El POST puede tardar ~17 s (3 reintentos + 1 s entre cada uno).
9. Borra los JPG del ciclo que no sean la captura representativa
   (usar `--conservar-capturas` para conservarlos todos).
10. **(Modo `--iniciar`)** Espera `LISTO` de la ESP32 (elevador terminó de bajar,
    listo para otro `INICIAR`). Timeout: `TIMEOUT_LISTO_SEG = 60 s`.
    Si no llega `LISTO`, avisa y continúa igual.
11. Vuelve al paso 1.

## Protocolo Serial

```
ESP32 → RPi:   ARRIBA | PASO_OK | ERROR <detalle> | LISTO
RPi   → ESP32: INICIAR | PASO | FIN APROBADA | FIN RECHAZADA
```

Cualquier otra línea recibida = debug de MicroPython → se ignora.
Con `--debug-serial` todas las líneas se imprimen con prefijo `[ESP32] `.

### Timeouts de la ESP32

| Evento | Timeout | Acción ESP32 |
|---|---|---|
| Tiempo para llegar al tope | 45 s | `ERROR TIMEOUT_SUBIDA` |
| Silencio sin recibir `PASO` (plato arriba) | 60 s | `ERROR TIMEOUT_RPI` |
| Silencio total mientras está arriba | 30 s | `ERROR TIMEOUT_SILENCIO` |

Por eso **FIN se envía antes del POST**: el POST con 3 reintentos y 1 s entre cada uno
puede tardar hasta ~17 s, lo que consumiría más de la mitad del timeout de silencio.

### Abortos en modo `--iniciar`

Cuando un ciclo aborta por `ERROR` de la ESP32 o por timeout de `PASO_OK`,
la ESP32 baja el elevador sola y envía `LISTO` al terminar.
En modo `--iniciar`, el script espera ese `LISTO` **también en los abortos**
(casos b y c del bucle de pasos) antes de volver al prompt de ENTER.
Así se evita que un `INICIAR` llegue con la ESP32 todavía ocupada bajando,
o que un `ERROR TIMEOUT_RPI` tardío contamine el ciclo siguiente.

No se espera `LISTO` cuando falla `_esperar_arriba`: en ese caso la ESP32
puede no haber arrancado todavía y esperar sería un bloqueo innecesario.

### Señal LISTO

`LISTO` la emite la ESP32 cuando el elevador terminó de bajar después de recibir `FIN`.
Indica que la máquina acepta otro `INICIAR`. Solo relevante en modo `--iniciar`.
La ESP32 reenvía `ARRIBA` cada 2 s hasta recibir el primer `PASO`.

## Configuración por máquina (`config_local.py`)

`raspberry/config_local.py` no está versionado (`.gitignore`). Si existe,
sus valores reemplazan a los de `config.py` **antes** de que se calcule
`URL_BACKEND`, así que cualquier constante puede sobreescribirse sin tocar
el archivo versionado.

Valores típicos para ajustar por instalación:

| Variable | Descripción | Ejemplo |
|---|---|---|
| `IP_BACKEND` | IP de la notebook donde corre el backend Flask | `"192.168.1.42"` |
| `CAM_SUPERIOR` | Ruta de dispositivo de la cámara superior | `"/dev/video0"` |
| `CAM_LATERAL` | Ruta de dispositivo de la cámara lateral | `"/dev/video2"` |
| `FOCO_SUPERIOR` | Foco manual de la cámara superior (0–255) | `55` |
| `FOCO_LATERAL` | Foco manual de la cámara lateral (0–255) | `50` |
| `EXPOSICION_SUPERIOR` | Tiempo de exposición cámara superior | `100` |
| `EXPOSICION_LATERAL` | Tiempo de exposición cámara lateral | `350` |
| `GANANCIA_SUPERIOR` | Ganancia de la cámara superior (0 = no aplicar) | `50` |
| `GANANCIA_LATERAL` | Ganancia de la cámara lateral (0 = no aplicar) | `50` |
| `PUERTO_SERIE` | Puerto serial de la ESP32 | `"/dev/ttyUSB0"` |
| `TIMEOUT_ARRIBA_SEG` | Timeout esperando `ARRIBA` (s) | `90` |
| `TIMEOUT_LISTO_SEG` | Timeout esperando `LISTO` tras FIN o aborto (s) | `120` |
| `CUADROS_DESCARTADOS` | Cuadros descartados antes de cada captura | `6` |

Ejemplo mínimo de `config_local.py`:

```python
IP_BACKEND        = "192.168.1.42"
FOCO_SUPERIOR     = 55
EXPOSICION_LATERAL = 350
```

## Robustez del arranque

### Instancia única (`fcntl.flock`)

Al iniciar, `ciclo_serial.py` toma un lock exclusivo sobre `/tmp/ciclo_serial.lock`.
Si ya hay otra instancia corriendo (por ejemplo, una sesión SSH que se cortó y dejó el
proceso vivo), el nuevo intento imprime el PID del proceso que tiene el lock y sale:

```
[ERROR] Ya hay una instancia de ciclo_serial.py corriendo (PID 1234).
        Para cerrarla: kill 1234
```

El lock se libera automáticamente cuando el proceso termina, incluso ante `kill` o
`Ctrl+C`, porque el kernel cierra el descriptor al salir. No hace falta limpiarlo a mano.

### Reintentos de apertura de cámara

Si `cv2.VideoCapture` no puede abrir un dispositivo, `_abrir_camara` reintenta
3 veces con 2 s de espera entre cada intento. Si todos fallan, imprime qué proceso
tiene el dispositivo ocupado usando `fuser -v` sobre la ruta real del dispositivo
(resolviendo el symlink by-id). Si `fuser` no está instalado, omite ese diagnóstico
sin fallar.

### Ganancia por cámara

`GANANCIA_SUPERIOR` y `GANANCIA_LATERAL` (default `0`) controlan el control `gain`
de v4l2. Con `0` no se envía el control. Ajustar en `config_local.py` si las imágenes
son demasiado oscuras a pesar de haber ajustado la exposición.

## Requisitos previos

```bash
# Calibrar las cámaras (una sola vez):
python calibracion_camaras.py --camara superior --indice 0 --mm 50
python calibracion_camaras.py --camara lateral  --indice 1 --mm 50

# Seleccionar pieza activa desde el dashboard o vía:
curl -X POST http://localhost:5000/pieza_activa -H "Content-Type: application/json" \
     -d '{"pieza": "Niple NPT 1/2\""}'
```

## Uso

```bash
# Producción (ESP32 conectada, backend corriendo):
python ciclo_serial.py

# Producción con ciclo disparado por operario (ENTER + INICIAR + esperar LISTO):
python ciclo_serial.py --iniciar

# Ver todo lo que llega por serial:
python ciclo_serial.py --debug-serial

# Prueba en mesa sin hardware serial (simula ARRIBA/PASO_OK con ENTER):
python ciclo_serial.py --sin-serial --sin-enviar

# Prueba en mesa con modo --iniciar (INICIAR responde ARRIBA sin ENTER adicional):
python ciclo_serial.py --sin-serial --sin-enviar --iniciar

# Ciclo corto (4 pasos en lugar de 8):
python ciclo_serial.py --pasos 4

# Combinaciones:
python ciclo_serial.py --sin-serial --sin-enviar --pasos 4
```

## Opciones

| Opción | Descripción |
|---|---|
| `--iniciar` | Pide ENTER al operario, envía `INICIAR` a la ESP32 y espera `LISTO` al final de cada ciclo. Sin esta opción la ESP32 dispara el ciclo con el botón físico (D4). |
| `--debug-serial` | Imprime cada línea recibida de la ESP32 con prefijo `[ESP32] `, incluyendo las ignoradas. |
| `--sin-serial` | Simula la ESP32 dentro de Python. Con `--iniciar`: `INICIAR` responde `ARRIBA` automáticamente y `FIN` encola `LISTO`. Sin `--iniciar`: pide ENTER para simular `ARRIBA`. |
| `--sin-enviar` | No hace POST al backend. Muestra el payload por pantalla. |
| `--pasos N` | Número de pasos de rotación por ciclo (default: 8). |
| `--conservar-capturas` | No borra los JPG del ciclo tras el POST. Útil para depuración. |

## Qué se probó (lógica, sin hardware)

- Flujo completo de un ciclo (ARRIBA → N×PASO → mediana → evaluación → FIN).
- `_SerialSimulado.reset_input_buffer()` (no-op verificado).
- Ciclo inválido (< 4 diámetros) → POST RECHAZADA + FIN RECHAZADA.
- Ciclo sin dimensiones evaluables → POST RECHAZADA + FIN RECHAZADA.
- Tabla de evaluación de dimensiones.
- Consulta de pieza activa por ciclo y detección de cambios.
- Fallback a pieza anterior si el backend no responde.
- Lógica de selección de captura más cercana a la mediana.
- Payload impreso sin imágenes con `--sin-enviar`.
- `--conservar-capturas` suprime el borrado de JPG.
- Ángulo calculado como `(n+1) × angulo_paso` (posición después del giro).

## Qué NO se probó (requiere hardware real)

- Comunicación serial con la ESP32 física.
- `ser.reset_input_buffer()` sobre un puerto real.
- Señales `INICIAR` y `LISTO` con la ESP32 real.
- Captura con las cámaras Logitech C920/C920e.
- `_leer_cuadro_fresco` / `CUADROS_DESCARTADOS` con V4L2 real.
- `CAP_PROP_BUFFERSIZE = 1` (depende del backend de OpenCV).
- Ajustes v4l2-ctl: FileNotFoundError y returncode != 0.
- POST real al backend Flask.
- Reintentos y guardado en `capturas/pendientes/`.
- Borrado real de JPG en `_limpiar_capturas`.

## Simulador de la ESP32

`esp32/simulador_protocolo.py` corre en MicroPython en la ESP32
(sin pines, sin hardware). Implementa el protocolo desde el lado
ESP32, útil para probar el canal serial real sin el hardware mecánico.

**ARRIBA se repite cada 2 s hasta que llega el primer PASO.**
La Raspberry ignora los duplicados: `reset_input_buffer()` al inicio
de cada ciclo limpia la cola, y `_esperar_arriba()` descarta todo lo
que no sea la cadena literal `ARRIBA`.

Implementación no bloqueante: `select.poll` sobre `sys.stdin` con
timeout de 100 ms. Si no llegan datos, comprueba si pasaron 2 s desde
el último `ARRIBA` y lo reenvía. Una vez recibido el primer PASO, el
resto del ciclo usa `readline()` bloqueante (la Raspberry responde rápido).

```bash
# Copiar a la ESP32 como main.py y conectar por Serial:
python ciclo_serial.py   # (con --sin-serial desactivado)
```
