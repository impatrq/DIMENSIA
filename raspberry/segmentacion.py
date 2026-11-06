# Segmentación de piezas — DIMENSIA
# Función compartida entre calibracion_camaras.py y procesamiento.py.
# IMPORTANTE: si se modifica detectar_contorno_pieza, verificar que el
# comportamiento siga siendo correcto en los dos archivos que la importan.

import cv2
import numpy as np


# ── API pública ───────────────────────────────────────────────────────────────

def detectar_contorno_pieza(imagen_grises):
    """
    Detecta el contorno de la pieza en la imagen en grises, con soporte
    para las dos polaridades posibles:
      - objeto claro sobre fondo oscuro  (ej: pieza iluminada, fondo negro)
      - objeto oscuro sobre fondo claro  (ej: tubo negro sobre hoja blanca)

    Algoritmo:
    1. Umbral de Otsu sobre la imagen en grises.
    2. Probar la máscara original y la invertida.
    3. Para cada máscara, descartar contornos que tocan el borde o cubren > 90 %.
    4. Elegir el contorno de mayor área entre los que quedan.

    Devuelve (contorno, descripcion_polaridad).
    Lanza Exception si no se encuentra ningún contorno válido.
    """
    alto, ancho = imagen_grises.shape[:2]
    area_imagen = alto * ancho

    _, binaria = cv2.threshold(imagen_grises, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    mejor_contorno  = None
    mejor_area      = 0
    mejor_polaridad = ""

    for mascara, etiqueta in [
        (binaria,                  "Objeto claro sobre fondo oscuro"),
        (cv2.bitwise_not(binaria), "Objeto oscuro sobre fondo claro"),
    ]:
        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contornos:
            x, y, w, h = cv2.boundingRect(c)
            if x == 0 or y == 0 or (x + w) >= ancho or (y + h) >= alto:
                continue
            if cv2.contourArea(c) >= area_imagen * 0.90:
                continue
            area = cv2.contourArea(c)
            if area > mejor_area:
                mejor_area      = area
                mejor_contorno  = c
                mejor_polaridad = etiqueta

    if mejor_contorno is None:
        raise Exception(
            "No se encontró un objeto completo dentro de la imagen. "
            "Centrá la pieza y verificá que no toque los bordes del cuadro."
        )

    return mejor_contorno, mejor_polaridad


def detectar_contorno_lateral(imagen_color, fondo=None, roi=None):
    """
    Detección mejorada para la cámara lateral.

    Prioridad de métodos:
    1. Si hay fondo de referencia (imagen BGR): diferencia absoluta + Otsu.
    2. Sin fondo: umbral Otsu sobre el canal de saturación HSV dentro del ROI.
       El niple oxidado tiene S~105 frente a S~28 de la pared gris.
    3. Fallback: detectar_contorno_pieza en grises (método original).

    En los métodos 1 y 2 se selecciona el mayor contorno que:
      - No toca el borde de la IMAGEN completa.
      - Tiene proporción alto/ancho > 1.2 (pieza parada es más alta que ancha).
      - Tiene área > 500 px².

    Devuelve (contorno, descripcion) igual que detectar_contorno_pieza.
    Lanza Exception si no se encuentra ningún contorno válido.
    """
    alto, ancho = imagen_color.shape[:2]

    # ── Método 1: fondo de referencia ─────────────────────────────────────────
    if fondo is not None:
        mascara = _segmentar_por_diferencia(imagen_color, fondo)
        contorno = _mejor_contorno_lateral(mascara, ancho, alto)
        if contorno is not None:
            return contorno, "Diferencia con fondo de referencia (lateral)"

    # ── Método 2: saturación HSV en ROI ───────────────────────────────────────
    hsv = cv2.cvtColor(imagen_color, cv2.COLOR_BGR2HSV)
    S   = hsv[:, :, 1]

    if roi is not None:
        rx, ry, rw, rh = roi
        roi_S = S[ry:ry + rh, rx:rx + rw]
    else:
        rx, ry = 0, 0
        roi_S  = S

    # Otsu sobre el canal S del ROI: separa la pieza oxidada (S~105) del fondo (S~28)
    _, mask_roi = cv2.threshold(roi_S, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_OPEN, kern)
    mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_CLOSE, kern, iterations=2)

    mascara_full = np.zeros((alto, ancho), dtype=np.uint8)
    mascara_full[ry:ry + (roi_S.shape[0]), rx:rx + (roi_S.shape[1])] = mask_roi

    contorno = _mejor_contorno_lateral(mascara_full, ancho, alto)
    if contorno is not None:
        return contorno, "Saturación HSV en ROI (lateral)"

    # ── Método 3: fallback Otsu en grises ─────────────────────────────────────
    grises = cv2.cvtColor(imagen_color, cv2.COLOR_BGR2GRAY)
    return detectar_contorno_pieza(grises)


def detectar_circulo_superior(imagen_color, radio_min=60, radio_max=130, fondo=None):
    """
    Detecta el anillo del niple en la vista superior mediante HoughCircles.

    Aplica CLAHE sobre la saturación HSV (el anillo oxidado tiene S~110 contra
    S~0-10 del plato negro) y sobre el canal gris, y prueba una cascada de
    parámetros de Hough. Si hay fondo de referencia usa la diferencia como canal
    adicional.

    Devuelve (cx, cy, radio_px) o None si no se detecta ningún círculo.
    """
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))

    # Preparar canales a probar (en orden de preferencia)
    hsv  = cv2.cvtColor(imagen_color, cv2.COLOR_BGR2HSV)
    S    = hsv[:, :, 1]
    gray = cv2.cvtColor(imagen_color, cv2.COLOR_BGR2GRAY)

    sat_eq  = clahe.apply(S)
    gray_eq = clahe.apply(gray)

    canales = [("CLAHE-saturación", sat_eq), ("CLAHE-gris", gray_eq)]

    if fondo is not None:
        diff = cv2.absdiff(imagen_color, fondo)
        diff_g = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        diff_eq = clahe.apply(diff_g)
        canales.insert(0, ("CLAHE-diferencia-fondo", diff_eq))

    # Cascada de parámetros: de más estricto a más permisivo.
    # dp=1.5 reduce falsos positivos en imágenes muy oscuras.
    cascada = [
        (1.5, 50, 20),
        (1.5, 40, 15),
        (1.5, 30, 12),
    ]

    for nombre, canal in canales:
        blur = cv2.GaussianBlur(canal, (9, 9), 2)
        for dp, p1, p2 in cascada:
            circulos = cv2.HoughCircles(
                blur, cv2.HOUGH_GRADIENT,
                dp=dp, minDist=50,
                param1=p1, param2=p2,
                minRadius=radio_min, maxRadius=radio_max,
            )
            if circulos is not None:
                cx, cy, r = circulos[0][0]
                return int(round(cx)), int(round(cy)), float(r)

    return None


# ── Helpers privados ──────────────────────────────────────────────────────────

def _segmentar_por_diferencia(imagen_color, fondo_color):
    """
    Calcula la diferencia absoluta imagen-fondo y devuelve una máscara binaria.
    Aplica blur gaussiano antes de umbralizar con Otsu y morfología para limpiar.
    """
    diff   = cv2.absdiff(imagen_color, fondo_color)
    diff_g = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    diff_g = cv2.GaussianBlur(diff_g, (5, 5), 0)
    _, mascara = cv2.threshold(diff_g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kern, iterations=2)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kern)
    return mascara


def _mejor_contorno_lateral(mascara, ancho, alto):
    """
    Entre todos los contornos de la máscara, devuelve el mayor que:
      - No toca el borde de la imagen.
      - Tiene proporción alto/ancho > 1.2 (pieza parada).
      - Tiene área > 500 px².
    Devuelve None si ninguno pasa los filtros.
    """
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mejor_area = 0
    mejor      = None
    for c in contornos:
        x, y, w, h = cv2.boundingRect(c)
        if x == 0 or y == 0 or (x + w) >= ancho or (y + h) >= alto:
            continue
        area = cv2.contourArea(c)
        if area < 500:
            continue
        if h / max(w, 1) < 1.2:
            continue
        if area > mejor_area:
            mejor_area = area
            mejor = c
    return mejor
