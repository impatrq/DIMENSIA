# DIMENSIA

Sistema de control de calidad automatizado para piezas de tornería industrial. Mide dimensiones con visión artificial, compara contra tolerancias definidas y registra cada inspección en tiempo real.

## Integrantes

- **Valentino Mendieta** — Backend Flask, base de datos, dashboard web, coordinación
- **Gino Orciani** — Raspberry Pi, OpenCV, cámaras, firmware ESP32
- **Luciano Algozzino** — Estructura física, electrónica
- **Joaquin Korylkiewicz** — Estructura física, electrónica

## Arquitectura del sistema

ESP32-S3 (elevador + servos + pantalla) → UART → Raspberry Pi 4 (OpenCV + cámaras) → HTTP → Backend Flask → Dashboard web

El sistema eleva la pieza con un motor NEMA17 y husillo T8 hasta la zona de medición (sellada de la luz externa), la rota con un servo mientras dos cámaras la fotografían desde distintos ángulos, procesa las imágenes con OpenCV para obtener las dimensiones en milímetros, compara contra tolerancias cargadas por tipo de pieza, y clasifica el resultado con una plataforma basculante y un brazo empujador. Ver el detalle completo en [`docs/arquitectura.md`](docs/arquitectura.md).

## Componentes

| Componente | Tecnología |
|---|---|
| Cámaras | 2x Logitech C920e (superior y lateral) |
| Elevador | Motor NEMA17 + husillo T8 + 2 finales de carrera |
| Rotación del plato | Servo MG996R 360° (control por tiempo) |
| Clasificación | Servo SG90 (plataforma basculante) + servo MG996R 180° (brazo empujador) |
| Seguridad de carga | Compuerta con microswitch |
| Microcontrolador | ESP32-S3 (con pantalla) |
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
| POST | /inspeccion | Recibe una inspección desde la Raspberry Pi (incluye capturas de cámara opcionales) |
| GET | /inspecciones | Devuelve el historial de inspecciones |
| GET | /exportar | Genera y descarga el historial en CSV |
| GET | /capturas/\<id\> | Devuelve las URLs de las capturas disponibles de una inspección |
| GET | /capturas/\<id\>/\<tipo\>.jpg | Sirve el archivo de imagen (superior o lateral) |
| POST | /piezas | Crea un nuevo tipo de pieza |
| GET | /piezas | Devuelve los tipos de piezas registradas |
| PUT | /piezas/\<id\> | Actualiza una pieza existente |
| POST | /pieza_activa | Registra la pieza seleccionada para el ciclo actual |
| GET | /pieza_activa | Devuelve la pieza activa |
| POST | /operario_activo | Registra el operario de turno |
| GET | /operario_activo | Devuelve el operario activo |
| POST | /calibracion | Guarda los factores px/mm de las cámaras |
| GET | /calibracion | Devuelve la última calibración guardada |
| GET | /calibraciones | Devuelve las últimas 5 calibraciones |
| POST | /sensores | Recibe el estado del elevador (finales de carrera + puerta) |
| GET | /sensores | Devuelve el estado actual del elevador |
| POST | /estado_ciclo | Recibe el estado actual de la máquina de estados |
| GET | /estado_ciclo | Devuelve el estado actual del ciclo |
| POST | /alerta_hardware | Registra una alerta de falla de hardware |
| GET | /alerta_hardware | Devuelve la alerta de hardware activa |
| POST | /alerta_hardware/resolver | Marca la alerta de hardware como resuelta |
| POST | /captura | Recibe el progreso de capturas del ciclo actual |
| GET | /captura | Devuelve el estado de capturas del ciclo |
| POST | /plato | Recibe el estado del plato giratorio |
| GET | /plato | Devuelve el estado actual del plato |
| POST | /servos | Recibe el estado de los 3 servos (rotación, empujador, plataforma) |
| GET | /servos | Devuelve el estado actual de los servos |

Documentación técnica completa en [`docs/`](docs/): [arquitectura](docs/arquitectura.md) y [API del backend](docs/api-backend.md).

## EET N° 7 — IMPA TRQ — 2026
