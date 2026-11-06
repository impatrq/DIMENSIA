# Configuración de la Raspberry Pi — DIMENSIA
# Todos los valores pueden sobreescribirse en config_local.py (no versionado).

import os

IP_BACKEND     = "192.168.126.176"
PUERTO_BACKEND = 5000

# ─── Cámaras ─────────────────────────────────────────────────────────────────
CAM_SUPERIOR = "/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_F69C8BBF-video-index0"
CAM_LATERAL  = "/dev/v4l/by-id/usb-046d_Logi_Webcam_C920e_5F32DA9F-video-index0"

FOCO_SUPERIOR        = 40
FOCO_LATERAL         = 40
EXPOSICION_SUPERIOR  = 80    # cámara A (C920); valor medido en banco
EXPOSICION_LATERAL   = 400   # cámara B (C920e); valor medido en banco

# ─── Fondos de referencia para segmentación ───────────────────────────────────
# Fotos de la caja vacía (mismas condiciones que producción).
# Si existen, segmentacion.py hace diferencia absoluta imagen-fondo.
# No versionados: están en .gitignore.
_DIR = os.path.dirname(__file__)
FONDO_SUPERIOR = os.path.join(_DIR, "fondo_superior.jpg")
FONDO_LATERAL  = os.path.join(_DIR, "fondo_lateral.jpg")

# ─── Segmentación lateral ─────────────────────────────────────────────────────
# ROI dentro del cual se busca la pieza con saturación HSV (x, y, w, h).
# Ajustar según la posición real de la pieza en la caja.
ROI_LATERAL = (850, 230, 300, 430)

# ─── HoughCircles para la vista superior ──────────────────────────────────────
# Rango de radio en píxeles para detectar el anillo del niple.
HOUGH_RADIO_MIN = 60
HOUGH_RADIO_MAX = 130

# ─── ESP32 ───────────────────────────────────────────────────────────────────
PUERTO_SERIE = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C2E008291-if00"
TIMEOUT_ARRIBA_SEG = 60
TIMEOUT_LISTO_SEG  = 90

# Cuadros descartados con grab() antes de cada captura
CUADROS_DESCARTADOS = 4

# ─── Override de máquina ──────────────────────────────────────────────────────
# Si existe raspberry/config_local.py, sus valores reemplazan todos los de arriba.
# No versionar config_local.py: está en .gitignore.
# Valores típicos a ajustar: IP_BACKEND, CAM_SUPERIOR, CAM_LATERAL,
#   FOCO_SUPERIOR, FOCO_LATERAL, EXPOSICION_SUPERIOR, EXPOSICION_LATERAL,
#   PUERTO_SERIE, TIMEOUT_ARRIBA_SEG, TIMEOUT_LISTO_SEG, CUADROS_DESCARTADOS,
#   ROI_LATERAL, HOUGH_RADIO_MIN, HOUGH_RADIO_MAX.
try:
    from config_local import *
except ImportError:
    pass

# URL_BACKEND se calcula después del override para tomar el IP_BACKEND final.
URL_BACKEND = f"http://{IP_BACKEND}:{PUERTO_BACKEND}"
