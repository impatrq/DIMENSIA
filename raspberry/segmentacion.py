# Segmentación de piezas — DIMENSIA
# Función compartida entre calibracion_camaras.py y procesamiento.py.
# IMPORTANTE: si se modifica esta lógica, verificar que el comportamiento
# siga siendo correcto en los dos archivos que la importan.

import cv2


def detectar_contorno_pieza(imagen_grises):
    """
    Detecta el contorno de la pieza en la imagen en grises, con soporte
    para las dos polaridades posibles:
      - objeto claro sobre fondo oscuro  (ej: pieza iluminada, fondo negro)
      - objeto oscuro sobre fondo claro  (ej: tubo negro sobre hoja blanca,
                                          silueta sobre retroiluminación)

    Algoritmo:
    1. Umbral de Otsu sobre la imagen en grises.
    2. Probar la máscara original y la invertida (cv2.bitwise_not).
    3. Para cada máscara, encontrar contornos externos y descartar:
         - los que tocan el borde de la imagen (probablemente el fondo)
         - los que cubren más del 90 % del área (filtro de respaldo)
    4. Elegir el contorno de mayor área entre los que quedan de ambas máscaras.

    Devuelve (contorno, descripcion_polaridad).
    Lanza Exception si no se encuentra ningún contorno válido.
    """
    alto, ancho = imagen_grises.shape[:2]
    area_imagen = alto * ancho

    # Umbral de Otsu: el valor 0 se ignora, THRESH_OTSU calcula el umbral real
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

            # Descartar contornos que tocan el borde de la imagen:
            # un contorno que llega al borde es casi siempre el fondo, no la pieza.
            if x == 0 or y == 0 or (x + w) >= ancho or (y + h) >= alto:
                continue

            # Descartar contornos que cubren más del 90 % del área (filtro de respaldo)
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
