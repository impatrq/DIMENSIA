# DIMENSIA

Sistema de control de calidad automatizado para piezas de tornería industrial. Mide dimensiones con sensores laser, compara contra tolerancias definidas y registra cada inspección en tiempo real.

## Integrantes

- **Valentino Mendieta** — Backend Flask, base de datos, dashboard web, Raspberry Pi
- **Gino Orciani** — Firmware ESP32, sensores VL53L4CD, comunicación UART

## Arquitectura del sistema

ESP32 (sensores) → UART → Raspberry Pi 4 → HTTP → Backend Flask → Dashboard web

## Componentes

| Componente | Tecnología |
|---|---|
| Sensores | 5x VL53L4CD (medición diferencial) |
| Microcontrolador | ESP32 |
| Procesamiento | Raspberry Pi 4 |
| Backend | Python / Flask / SQLite |
| Dashboard | HTML / CSS / JavaScript |

## Cómo correr el proyecto

### Backend

cd dimensia-backend
pip install flask flask-cors
python app.py
Servidor corriendo en http://127.0.0.1:5000

### Dashboard

cd dimensia-dashboard
python -m http.server 8000
Abrir en el navegador: http://127.0.0.1:8000

## Endpoints del backend

| Método | Endpoint | Descripción |
|---|---|---|
| GET | / | Verifica que el servidor funciona |
| POST | /inspeccion | Recibe una inspección desde la Raspberry Pi |
| GET | /inspecciones | Devuelve el historial de inspecciones |
| POST | /piezas | Guarda un nuevo tipo de pieza |
| GET | /piezas | Devuelve los tipos de piezas registradas |
| POST | /operario_activo | Registra el operario de turno |
| GET | /operario_activo | Devuelve el operario activo |
| POST | /calibracion | Guarda los valores de calibración de los sensores |
| GET | /calibracion | Devuelve la última calibración guardada |
| POST | /sensores | Recibe las lecturas brutas de los 5 sensores |
| GET | /sensores | Devuelve las lecturas actuales de los 5 sensores |

## EET N° 7 — IMPA TRQ — 2026
