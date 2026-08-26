# Módulo de procesamiento de imágenes — DIMENSIA
# Extrae las dimensiones de la pieza a partir de las fotos de las dos cámaras.
# Requiere: pip install opencv-python numpy

import cv2
import numpy as np
import json
import os

RUTA_CALIBRACION_CAMARAS = os.path.join(os.path.dirname(__file__), "calibracion_camaras.json")
CARPETA_CAPTURAS          = os.path.join(os.path.dirname(__file__), "capturas")


class ProcesadorImagenes:
    """
    Procesa las imágenes de las dos cámaras y extrae las dimensiones de la pieza.
    La cámara superior da el diámetro exterior; la lateral da el largo y el alto.
    """

    def __init__(self):
        # Cargar la calibración de cámaras si existe, sino usar valores por defecto
        if os.path.exists(RUTA_CALIBRACION_CAMARAS):
            with open(RUTA_CALIBRACION_CAMARAS, "r") as f:
                cal = json.load(f)
            print("Calibración de cámaras cargada.")
        else:
            cal = {"px_por_mm_superior": 10.0, "px_por_mm_lateral": 10.0}
            print("Aviso: calibracion_camaras.json no encontrado. Usando valores por defecto.")

        self.px_mm_superior = cal["px_por_mm_superior"]
        self.px_mm_lateral  = cal["px_por_mm_lateral"]

    def _segmentar(self, imagen_grises):
        """
        Aplica umbralización de Otsu para separar la pieza del fondo.
        Otsu elige automáticamente el umbral óptimo según el histograma.
        Devuelve la imagen binaria (blanco = pieza, negro = fondo).
        """
        # THRESH_OTSU calcula el umbral automáticamente; el valor 0 se ignora
        _, binaria = cv2.threshold(
            imagen_grises, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        return binaria

    def _contorno_principal(self, binaria):
        """
        Encuentra todos los contornos en la imagen binaria y devuelve el más grande.
        El más grande corresponde a la pieza (los ruidos son contornos pequeños).
        """
        contornos, _ = cv2.findContours(
            binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contornos:
            return None
        # Ordenar por área y tomar el mayor
        return max(contornos, key=cv2.contourArea)

    def procesar_superior(self, ruta_imagen):
        """
        Procesa la foto de la cámara superior (vista desde arriba).
        Extrae el diámetro exterior usando el círculo mínimo que encierra la pieza.
        Devuelve las medidas en píxeles y en mm.
        """
        imagen = cv2.imread(ruta_imagen)
        if imagen is None:
            raise Exception("No se pudo cargar la imagen: {}".format(ruta_imagen))

        # Convertir a grises para poder umbralizar
        grises = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        binaria = self._segmentar(grises)
        contorno = self._contorno_principal(binaria)

        if contorno is None:
            return {"diametro_exterior_mm": None, "diametro_exterior_px": None}

        # minEnclosingCircle devuelve el círculo mínimo que contiene el contorno
        # El radio * 2 = diámetro exterior de la pieza en la vista superior
        _, radio_px = cv2.minEnclosingCircle(contorno)
        diametro_px = radio_px * 2

        diametro_mm = round(diametro_px / self.px_mm_superior, 1)

        return {
            "diametro_exterior_mm": diametro_mm,
            "diametro_exterior_px": round(diametro_px, 1),
        }

    def procesar_lateral(self, ruta_imagen):
        """
        Procesa la foto de la cámara lateral (vista de costado).
        Extrae el largo y el alto de la pieza usando el rectángulo que encierra el contorno.
        El ancho del rectángulo = largo de la pieza.
        El alto del rectángulo  = altura de la pieza.
        Devuelve las medidas en píxeles y en mm.
        """
        imagen = cv2.imread(ruta_imagen)
        if imagen is None:
            raise Exception("No se pudo cargar la imagen: {}".format(ruta_imagen))

        # Convertir a grises y segmentar
        grises = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        binaria = self._segmentar(grises)
        contorno = self._contorno_principal(binaria)

        if contorno is None:
            return {"largo_mm": None, "largo_px": None, "alto_mm": None, "alto_px": None}

        # boundingRect devuelve (x, y, ancho, alto) del rectángulo alineado con los ejes
        # ancho del rectángulo → largo de la pieza en la vista lateral
        # alto  del rectángulo → altura de la pieza en la vista lateral
        x, y, ancho_px, alto_px = cv2.boundingRect(contorno)

        largo_mm = round(ancho_px / self.px_mm_lateral, 1)
        alto_mm  = round(alto_px  / self.px_mm_lateral, 1)

        return {
            "largo_mm": largo_mm,
            "largo_px": ancho_px,
            "alto_mm":  alto_mm,
            "alto_px":  alto_px,
        }

    def procesar_ciclo_completo(self, capturas):
        """
        Procesa las dos fotos de un mismo ángulo de rotación.
        Recibe {"superior": ruta, "lateral": ruta}.
        Devuelve todas las medidas en un solo dict.
        """
        resultado_superior = self.procesar_superior(capturas["superior"])
        resultado_lateral  = self.procesar_lateral(capturas["lateral"])

        return {
            "diametro_exterior_mm": resultado_superior["diametro_exterior_mm"],
            "diametro_exterior_px": resultado_superior["diametro_exterior_px"],
            "largo_mm":             resultado_lateral["largo_mm"],
            "largo_px":             resultado_lateral["largo_px"],
            "alto_mm":              resultado_lateral["alto_mm"],
            "alto_px":              resultado_lateral["alto_px"],
        }


# ─── Prueba rápida ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    procesador = ProcesadorImagenes()

    # Buscar las últimas capturas disponibles en la carpeta
    if not os.path.exists(CARPETA_CAPTURAS):
        print("No hay capturas disponibles en {}/".format(CARPETA_CAPTURAS))
        exit(1)

    archivos = sorted(os.listdir(CARPETA_CAPTURAS))
    superiores = [f for f in archivos if f.startswith("superior_")]
    laterales  = [f for f in archivos if f.startswith("lateral_")]

    if not superiores or not laterales:
        print("No se encontraron capturas. Corré primero raspberry/camaras.py")
        exit(1)

    # Tomar la última captura de cada tipo
    capturas = {
        "superior": os.path.join(CARPETA_CAPTURAS, superiores[-1]),
        "lateral":  os.path.join(CARPETA_CAPTURAS, laterales[-1]),
    }

    print("Procesando:")
    print("  Superior: {}".format(capturas["superior"]))
    print("  Lateral:  {}".format(capturas["lateral"]))

    medidas = procesador.procesar_ciclo_completo(capturas)

    print("\nResultados:")
    print("  Diámetro exterior: {} mm  ({} px)".format(
        medidas["diametro_exterior_mm"], medidas["diametro_exterior_px"]
    ))
    print("  Largo:  {} mm  ({} px)".format(medidas["largo_mm"], medidas["largo_px"]))
    print("  Alto:   {} mm  ({} px)".format(medidas["alto_mm"],  medidas["alto_px"]))
