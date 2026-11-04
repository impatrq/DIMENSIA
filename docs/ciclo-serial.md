# Ciclo automatizado vía Serial — DIMENSIA

Script: `raspberry/ciclo_serial.py`

## Qué hace

Corre en la Raspberry Pi y coordina la inspección completa de piezas
en modo automatizado, sin intervención manual:

1. Espera la señal `ARRIBA` de la ESP32 (elevador en posición).
2. Repite N pasos de rotación (default 8): envía `PASO`, espera `PASO_OK`,
   espera 0.3 s a que el plato se asiente, captura con ambas cámaras y mide.
3. Calcula la **mediana** de las N mediciones (diámetro, largo, alto).
   Si hay menos de 4 mediciones válidas, el ciclo se cancela.
4. Evalúa contra las referencias y tolerancias de la pieza activa.
5. Envía un único `POST /inspeccion` al backend con la captura más
   representativa (la más cercana a la mediana de diámetro).
6. Envía `FIN APROBADA` o `FIN RECHAZADA` a la ESP32
   **aunque el POST haya fallado** (el POST se reintenta 3 veces;
   si persiste, el payload se guarda en `capturas/pendientes/`).
7. Vuelve al paso 1.

## Protocolo Serial

```
ESP32 → RPi:   ARRIBA | PASO_OK | ERROR <detalle>
RPi   → ESP32: PASO   | FIN APROBADA | FIN RECHAZADA
```

Cualquier otra línea recibida = debug de MicroPython → se ignora.

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

# Prueba en mesa sin hardware serial (simula ARRIBA/PASO_OK con ENTER):
python ciclo_serial.py --sin-serial --sin-enviar

# Ciclo corto (4 pasos en lugar de 8):
python ciclo_serial.py --pasos 4

# Combinaciones:
python ciclo_serial.py --sin-serial --sin-enviar --pasos 4
```

## Opciones

| Opción | Descripción |
|---|---|
| `--sin-serial` | Simula la ESP32 dentro de Python. Cada `PASO` responde automáticamente `PASO_OK`. Pide ENTER para simular `ARRIBA`. |
| `--sin-enviar` | No hace POST al backend. Muestra el payload por pantalla. |
| `--pasos N` | Número de pasos de rotación por ciclo (default: 8). |

## Qué se probó con `--sin-serial --sin-enviar`

- Flujo completo de un ciclo (ARRIBA → N×PASO → mediana → evaluación → FIN).
- `_SerialSimulado` responde `ARRIBA` al primer ENTER y `PASO_OK` a cada `PASO`.
- Tabla de evaluación de dimensiones.
- Lógica de selección de captura más cercana a la mediana.
- Payload impreso sin imágenes.

## Qué NO se probó (requiere hardware real)

- Comunicación serial con la ESP32 física.
- Captura con las cámaras Logitech C920/C920e.
- Ajustes v4l2-ctl (foco, exposición, balance de blancos).
- POST real al backend Flask.
- Reintentos y guardado en `capturas/pendientes/`.

## Simulador de la ESP32

`esp32/simulador_protocolo.py` corre en MicroPython en la ESP32
(sin pines, sin hardware). Implementa el mismo protocolo pero desde
el lado de la ESP32, útil para probar el canal serial real sin el
resto del hardware mecánico.

```
# Copiar a la ESP32 como main.py y conectar por Serial:
python ciclo_serial.py   # (con --sin-serial desactivado)
```
