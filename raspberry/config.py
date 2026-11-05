# Configuración de la Raspberry Pi — DIMENSIA
# Todos los valores pueden sobreescribirse en config_local.py (no versionado).

IP_BACKEND   = "192.168.126.176"
PUERTO_BACKEND = 5000

# ─── Cámaras ─────────────────────────────────────────────────────────────────
# Rutas by-id: estables entre reinicios aunque cambien los índices /dev/videoN.
# Ajustar cuál es superior y cuál lateral según el montaje físico.
# Hoy provisional: C920 (cámara A) = superior, C920e (cámara B) = lateral.
CAM_SUPERIOR = "/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_F69C8BBF-video-index0"
CAM_LATERAL  = "/dev/v4l/by-id/usb-046d_Logi_Webcam_C920e_5F32DA9F-video-index0"

# Ajustes de foco manual y exposición por cámara (a afinar dentro de la caja).
# white_balance_temperature = 4600 K (luz blanca fría, fija para ambas).
FOCO_SUPERIOR        = 40
FOCO_LATERAL         = 40
EXPOSICION_SUPERIOR  = 80    # cámara A (C920); valor medido en banco
EXPOSICION_LATERAL   = 400   # cámara B (C920e); valor medido en banco

# ─── ESP32 ───────────────────────────────────────────────────────────────────
# Puerto by-id de la ESP32 (CH340, ya identificado en la Raspberry Pi).
PUERTO_SERIE = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C2E008291-if00"

# Tiempo máximo esperando la señal ARRIBA de la ESP32 (segundos)
TIMEOUT_ARRIBA_SEG = 60

# Tiempo máximo esperando LISTO tras FIN o tras un aborto en modo --iniciar.
# La ESP32 espera 30 s de silencio antes de bajar sola + hasta 45 s de bajada.
TIMEOUT_LISTO_SEG = 90

# Cuadros que se descartan con grab() antes de cada captura para vaciar el
# buffer interno de la cámara y obtener un frame fresco.
CUADROS_DESCARTADOS = 4

# ─── Override de máquina ──────────────────────────────────────────────────────
# Si existe raspberry/config_local.py, sus valores reemplazan todos los de arriba.
# No versionar config_local.py: está en .gitignore.
# Valores sobreescribibles: IP_BACKEND, CAM_SUPERIOR, CAM_LATERAL,
#   FOCO_SUPERIOR, FOCO_LATERAL, EXPOSICION_SUPERIOR, EXPOSICION_LATERAL,
#   PUERTO_SERIE, TIMEOUT_ARRIBA_SEG, TIMEOUT_LISTO_SEG, CUADROS_DESCARTADOS.
# Ejemplo de config_local.py:
#   IP_BACKEND       = "localhost"
#   CAM_SUPERIOR     = "/dev/video0"
#   FOCO_SUPERIOR    = 55
#   TIMEOUT_LISTO_SEG = 120
try:
    from config_local import *
except ImportError:
    pass

# URL_BACKEND se recalcula después del override para tomar el IP_BACKEND final.
URL_BACKEND = f"http://{IP_BACKEND}:{PUERTO_BACKEND}"
