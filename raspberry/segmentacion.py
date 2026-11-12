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
    1. Si hay fondo de referencia (imagen BGR): diferencia adaptativa + morfología
       vertical + convex hull relleno + trim de sombra y columnas laterales.
       Captura roscas tenues (similar tono que el fondo) y recorta la sombra de
       contacto en la base.
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
        mascara, diff_b, umbral = _segmentar_por_diferencia(imagen_color, fondo)
        contorno = _mejor_contorno_lateral(mascara, ancho, alto)
        if contorno is not None:
            # Convex hull relleno → tapa huecos internos (rugosidades, roscas)
            hull = cv2.convexHull(contorno)
            hull_mask = np.zeros((alto, ancho), dtype=np.uint8)
            cv2.fillPoly(hull_mask, [hull], 255)
            # Trim: recorta filas inferiores con sombra débil y columnas laterales ruidosas
            hull_mask = _recortar_bordes(hull_mask, diff_b, umbral)
            cs, _ = cv2.findContours(hull_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contorno_final = max(cs, key=cv2.contourArea) if cs else contorno
            return contorno_final, "Diferencia con fondo de referencia (lateral)"

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
    Diferencia absoluta imagen-fondo con umbral adaptativo y morfología vertical.

    Mejoras respecto a la versión con Otsu fijo:
    1. Umbral adaptativo: p90 del borde + 1 std, en lugar de Otsu global. Captura
       zonas tenues (roscas con brillo similar al fondo) sin activar el fondo limpio.
    2. Cierre vertical 5×41: conecta los anillos de rosca con el cuerpo del niple
       llenando los valles entre hilos adyacentes.
    3. Cierre + apertura con kernel elíptico 7×7 para limpieza general.

    Devuelve (mascara, diff_b, umbral) para que el llamador pueda usar diff_b en
    _recortar_bordes sin recalcular la diferencia.
    """
    diff   = cv2.absdiff(imagen_color, fondo_color)
    diff_g = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    diff_b = cv2.GaussianBlur(diff_g, (5, 5), 0)

    alto, ancho = diff_b.shape

    # Umbral adaptativo basado en el ruido del borde de la imagen
    borde = 30
    bordes = np.concatenate([
        diff_b[:borde, :].ravel(), diff_b[-borde:, :].ravel(),
        diff_b[:, :borde].ravel(), diff_b[:, -borde:].ravel(),
    ])
    noise_p90 = float(np.percentile(bordes, 90))
    noise_std  = float(bordes.std())
    umbral = max(noise_p90 + noise_std, 10.0)

    mascara = (diff_b > umbral).astype(np.uint8) * 255

    # Cierre vertical agresivo: 5 px ancho × 41 px alto
    kern_v = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 41))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kern_v)

    # Cierre + apertura con elipse para limpiar ruido general
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kern, iterations=2)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kern)

    return mascara, diff_b, umbral


def _recortar_bordes(hull_mask, diff_b, umbral, dmin_fila=0.75, dmin_col=0.25):
    """
    Recorta filas inferiores y columnas laterales de la máscara donde la diferencia
    original es débil (sombra de contacto o ruido morfológico de borde).

    - Filas: escanea de abajo hacia arriba hasta la primera fila con ≥ dmin_fila
      de píxeles activos en el rango horizontal de la pieza.
    - Columnas: escanea de afuera hacia adentro (izq y der) hasta la primera columna
      con ≥ dmin_col de píxeles activos en el rango vertical de la pieza.
    """
    filas_on = np.where(hull_mask.any(axis=1))[0]
    if not len(filas_on):
        return hull_mask
    y_top, y_bot = int(filas_on[0]), int(filas_on[-1])

    cols_on = np.where(hull_mask[y_top:y_bot + 1].any(axis=0))[0]
    if not len(cols_on):
        return hull_mask
    x0, x1 = int(cols_on[0]), int(cols_on[-1])

    out = hull_mask.copy()

    # Trim filas inferiores (sombra de contacto)
    for fila in range(y_bot, y_top - 1, -1):
        franja = diff_b[fila, x0:x1 + 1]
        den = float((franja > umbral).sum()) / max(len(franja), 1)
        if den < dmin_fila:
            out[fila, :] = 0
        else:
            break

    # Recalcular límites verticales tras el trim de filas
    filas2 = np.where(out.any(axis=1))[0]
    if not len(filas2):
        return out
    y_top2, y_bot2 = int(filas2[0]), int(filas2[-1])

    # Trim columnas izquierdas (ruido morfológico de borde)
    for col in range(x0, x1):
        franja = diff_b[y_top2:y_bot2 + 1, col]
        den = float((franja > umbral).sum()) / max(len(franja), 1)
        if den < dmin_col:
            out[:, col] = 0
        else:
            break

    # Trim columnas derechas
    for col in range(x1, x0 - 1, -1):
        franja = diff_b[y_top2:y_bot2 + 1, col]
        den = float((franja > umbral).sum()) / max(len(franja), 1)
        if den < dmin_col:
            out[:, col] = 0
        else:
            break

    return out


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
