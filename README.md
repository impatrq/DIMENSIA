# DIMENSIA

Sistema de control de calidad automatizado para piezas de tornería industrial. Mide dimensiones con visión artificial, compara contra tolerancias definidas y registra cada inspección en tiempo real.

## Integrantes

- **Valentino Mendieta** — Backend Flask, base de datos, dashboard web, control ESP32
- **Gino Orciani** — Raspberry Pi, OpenCV, cámaras, scripts de simulación
- **Luciano Algozzino** — Estructura física, electrónica
- **Joaquin Korylkiewicz** — Estructura física, cinta transportadora

## Arquitectura del sistema

ESP32 (sensores + servos) → Raspberry Pi 4 (OpenCV + cámaras) → HTTP → Backend Flask → Dashboard web

## Componentes

| Componente | Tecnología |
|---|---|
| Cámaras | 2x Logitech C920e (superior y lateral) |
| Sensores de presencia | 3x VL53L4CD (S1, S2, S3) |
| Microcontrolador | ESP32 |
| Procesamiento | Raspberry Pi 4 |
| Backend | Python / Flask / SQLite |
| Dashboard | HTML / CSS / JavaScript |

## Cómo correr el proyecto

### Backend

```bash
cd dimensia-backend
pip install flask flask-cors
python app.py
```

Servidor corriendo en http://127.0.0.1:5000

### Dashboard

```bash
cd dimensia-dashboard
python -m http.server 8000
```

Abrir en el navegador: http://127.0.0.1:8000

## Endpoints del backend

| Método | Endpoint | Descripción |
|---|---|---|
| GET | / | Verifica que el servidor funciona |
| POST | /inspeccion | Recibe una inspección desde la Raspberry Pi |
| GET | /inspecciones | Devuelve el historial de inspecciones |
| GET | /exportar | Genera y descarga el historial en CSV |
| POST | /piezas | Guarda un nuevo tipo de pieza |
| GET | /piezas | Devuelve los tipos de piezas registradas |
| POST | /operario_activo | Registra el operario de turno |
| GET | /operario_activo | Devuelve el operario activo |
| POST | /calibracion | Guarda los factores px/mm de las cámaras |
| GET | /calibracion | Devuelve la última calibración guardada |
| GET | /calibraciones | Devuelve las últimas 5 calibraciones |
| POST | /sensores | Recibe el estado de los sensores de presencia S1, S2, S3 |
| GET | /sensores | Devuelve el estado actual de los sensores |
| POST | /captura | Recibe el progreso de capturas del ciclo actual |
| GET | /captura | Devuelve el estado de capturas del ciclo |
| POST | /plato | Recibe el estado del plato giratorio |
| GET | /plato | Devuelve el estado actual del plato |
| POST | /servos | Recibe el estado de los 3 servos |
| GET | /servos | Devuelve el estado actual de los servos |

## EET N° 7 — IMPA TRQ — 2026
