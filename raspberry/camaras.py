# Módulo de cámaras — Raspberry Pi 4
# Maneja las dos cámaras Logitech C920e conectadas por USB.
# Requiere: pip install opencv-python

import cv2
import os
from datetime import datetime

CAMARA_SUPERIOR = 0   # índice de la cámara superior (primer USB)
CAMARA_LATERAL  = 1   # índice de la cámara lateral  (segundo USB)
CARPETA_CAPTURAS = os.path.join(os.path.dirname(__file__), "capturas")


class GestorCamaras:
    """Abre las dos cámaras USB y permite tomar capturas por ángulo de rotación."""

    def __init__(self):
        # Crear la carpeta de capturas si no existe
        os.makedirs(CARPETA_CAPTURAS, exist_ok=True)

        # Abrir la cámara superior
        self.cam_superior = cv2.VideoCapture(CAMARA_SUPERIOR)
        if not self.cam_superior.isOpened():
            raise Exception(
                "No se pudo abrir la cámara superior (índice {}). "
                "¿Está conectada la Logitech C920e?".format(CAMARA_SUPERIOR)
            )

        # Abrir la cámara lateral
        self.cam_lateral = cv2.VideoCapture(CAMARA_LATERAL)
        if not self.cam_lateral.isOpened():
            self.cam_superior.release()
            raise Exception(
                "No se pudo abrir la cámara lateral (índice {}). "
                "¿Está conectada la segunda Logitech C920e?".format(CAMARA_LATERAL)
            )

        # Configurar resolución 1920x1080 en ambas cámaras
        for cam in (self.cam_superior, self.cam_lateral):
            cam.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    def capturar(self, angulo):
        """
        Toma una foto con cada cámara y las guarda en la carpeta capturas/.
        Recibe el ángulo actual de la rotación (0, 45, 90 ... 315).
        Devuelve un dict con las rutas de los dos archivos guardados.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        nombre_superior = "superior_ang{}_{}.jpg".format(angulo, timestamp)
        nombre_lateral  = "lateral_ang{}_{}.jpg".format(angulo, timestamp)

        ruta_superior = os.path.join(CARPETA_CAPTURAS, nombre_superior)
        ruta_lateral  = os.path.join(CARPETA_CAPTURAS, nombre_lateral)

        # Capturar y guardar cámara superior
        ret, frame = self.cam_superior.read()
        if not ret:
            raise Exception("Error al capturar imagen de la cámara superior.")
        cv2.imwrite(ruta_superior, frame)

        # Capturar y guardar cámara lateral
        ret, frame = self.cam_lateral.read()
        if not ret:
            raise Exception("Error al capturar imagen de la cámara lateral.")
        cv2.imwrite(ruta_lateral, frame)

        return {"superior": ruta_superior, "lateral": ruta_lateral}

    def cerrar(self):
        """Libera las dos cámaras."""
        self.cam_superior.release()
        self.cam_lateral.release()


# ─── Prueba rápida ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    camaras = GestorCamaras()

    # Simular una vuelta completa: 8 ángulos de 45° en 45°
    angulos = [0, 45, 90, 135, 180, 225, 270, 315]

    print("Capturando vuelta completa ({} ángulos)...\n".format(len(angulos)))

    for angulo in angulos:
        rutas = camaras.capturar(angulo)
        print("{}°  →  superior: {}".format(angulo, rutas["superior"]))
        print("       lateral:  {}".format(rutas["lateral"]))

    camaras.cerrar()
    print("\nListo. {} capturas guardadas en {}/".format(len(angulos) * 2, CARPETA_CAPTURAS))
