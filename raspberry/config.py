# Configuracion local de la Raspberry Pi
# Cambiar IP_BACKEND cuando cambie la IP de la notebook (verificar con ipconfig)

IP_BACKEND = "192.168.126.176"
PUERTO_BACKEND = 5000
URL_BACKEND = f"http://{IP_BACKEND}:{PUERTO_BACKEND}"

# ─── Override de máquina ──────────────────────────────────────────────────────
# Si existe raspberry/config_local.py, sus valores reemplazan los de arriba.
# No versionar config_local.py: está en .gitignore.
# Ejemplo de config_local.py:
#   IP_BACKEND = "localhost"
try:
    from config_local import *
    URL_BACKEND = f"http://{IP_BACKEND}:{PUERTO_BACKEND}"
except ImportError:
    pass

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
