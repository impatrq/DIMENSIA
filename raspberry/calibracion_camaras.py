# Calibración de cámaras — DIMENSIA
# Calcula cuántos píxeles equivalen a 1 mm en cada cámara.
# Se corre UNA SOLA VEZ con un objeto de referencia de medidas conocidas.
# Requiere: pip install opencv-python

import cv2
import json
import os

RUTA_CALIBRACION = os.path.join(os.path.dirname(__file__), "calibracion_camaras.json")
CARPETA_CAPTURAS = os.path.join(os.path.dirname(__file__), "capturas")


def medir_referencia_en_imagen(ruta_imagen):
    """
    Detecta el objeto de referencia en la imagen y devuelve su tamaño en píxeles.
    Usa el mismo pipeline de segmentación que procesamiento.py:
    escala de grises → umbral de Otsu → contorno más grande → bounding rect.
    """
    imagen = cv2.imread(ruta_imagen)
    if imagen is None:
        raise Exception("No se pudo cargar la imagen: {}".format(ruta_imagen))

    # Convertir a grises para poder umbralizar
    grises = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

    # Verificar que la imagen tenga suficiente contraste antes de umbralizar.
    # Una desviación estándar baja indica que todos los píxeles tienen valores
    # similares (imagen plana), lo que hace que Otsu no pueda separar el objeto.
    if grises.std() < 15:
        raise Exception(
            "La imagen no tiene suficiente contraste. Verificá "
            "la iluminación y que el objeto esté dentro del cuadro."
        )

    # Otsu determina automáticamente el umbral óptimo según el histograma
    _, binaria = cv2.threshold(grises, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Encontrar todos los contornos externos
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        raise Exception("No se detectó ningún objeto en la imagen.")

    # Tomar el contorno más grande — es el objeto de referencia
    contorno_principal = max(contornos, key=cv2.contourArea)

    # Obtener el rectángulo que encierra el contorno
    # x, y = esquina superior izquierda; ancho y alto en píxeles
    x, y, ancho_px, alto_px = cv2.boundingRect(contorno_principal)

    # Validar que el bounding rect tenga dimensiones válidas
    if ancho_px == 0 or alto_px == 0:
        raise Exception(
            "No se pudo medir el objeto correctamente. Intentá "
            "de nuevo con mejor iluminación."
        )

    # Validar que el objeto ocupe al menos el 1% de la imagen.
    # Un objeto más pequeño probablemente es ruido, no el objeto de referencia.
    area_objeto = ancho_px * alto_px
    area_imagen = imagen.shape[0] * imagen.shape[1]
    if area_objeto < area_imagen * 0.01:
        raise Exception(
            "El objeto detectado es demasiado pequeño. Verificá "
            "que el objeto de referencia esté bien visible y "
            "cerca de la cámara."
        )

    return ancho_px, alto_px


def _capturar_con_camara(indice, ruta_guardado):
    """Abre la cámara, espera confirmación del usuario, captura y guarda la imagen."""
    cam = cv2.VideoCapture(indice)
    if not cam.isOpened():
        raise Exception(
            "No se pudo abrir la cámara con índice {}. "
            "¿Está conectada?".format(indice)
        )

    # Configurar resolución máxima de la Logitech C920e
    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    input("Presioná ENTER para capturar...")

    ret, frame = cam.read()
    cam.release()

    if not ret:
        raise Exception("Error al capturar imagen de la cámara {}.".format(indice))

    cv2.imwrite(ruta_guardado, frame)
    print("Imagen guardada en: {}".format(ruta_guardado))

    return ruta_guardado


def _capturar_y_medir(indice_camara, ruta_guardado):
    """
    Captura una imagen con la cámara indicada y mide el objeto de referencia.
    Si la medición falla, ofrece al usuario reintentar antes de abortar.
    Devuelve (ancho_px, alto_px) del objeto detectado.
    """
    while True:
        try:
            _capturar_con_camara(indice_camara, ruta_guardado)
            return medir_referencia_en_imagen(ruta_guardado)
        except Exception as e:
            print("[ERROR] {}".format(e))
            respuesta = input("¿Querés reintentar? (s/n): ").strip().lower()
            if respuesta != "s":
                raise  # Relanzar la excepción original para cortar el proceso


def calibrar():
    """
    Guía al operario a calibrar las dos cámaras con un objeto de referencia.
    Calcula los píxeles por mm de cada cámara y guarda el resultado en JSON.
    """
    os.makedirs(CARPETA_CAPTURAS, exist_ok=True)

    print("=" * 55)
    print("  CALIBRACIÓN DE CÁMARAS — DIMENSIA")
    print("=" * 55)

    # Pedir el tamaño real del objeto de referencia
    mm_referencia = float(input("¿Cuántos mm mide el objeto de referencia? (ej: 50): "))

    # ─── Cámara superior ──────────────────────────────────────────────────────
    print("\n--- Cámara SUPERIOR ---")
    print("Colocá el objeto de referencia bajo la cámara SUPERIOR")

    ruta_superior = os.path.join(CARPETA_CAPTURAS, "calibracion_superior.jpg")
    ancho_px_sup, _ = _capturar_y_medir(0, ruta_superior)
    px_por_mm_superior = round(ancho_px_sup / mm_referencia, 4)

    print("  Objeto detectado: {} px".format(ancho_px_sup))
    print("  px_por_mm_superior = {} px/mm".format(px_por_mm_superior))

    # ─── Cámara lateral ───────────────────────────────────────────────────────
    print("\n--- Cámara LATERAL ---")
    print("Ahora colocá el objeto bajo la cámara LATERAL")

    ruta_lateral = os.path.join(CARPETA_CAPTURAS, "calibracion_lateral.jpg")
    ancho_px_lat, _ = _capturar_y_medir(1, ruta_lateral)
    px_por_mm_lateral = round(ancho_px_lat / mm_referencia, 4)

    print("  Objeto detectado: {} px".format(ancho_px_lat))
    print("  px_por_mm_lateral = {} px/mm".format(px_por_mm_lateral))

    # ─── Guardar resultado ────────────────────────────────────────────────────
    calibracion = {
        "px_por_mm_superior": px_por_mm_superior,
        "px_por_mm_lateral":  px_por_mm_lateral,
    }

    with open(RUTA_CALIBRACION, "w") as f:
        json.dump(calibracion, f, indent=2)

    print("\nCalibración guardada en calibracion_camaras.json:")
    print("  px_por_mm_superior = {} px/mm".format(px_por_mm_superior))
    print("  px_por_mm_lateral  = {} px/mm".format(px_por_mm_lateral))
    print("\nListo. Las cámaras están calibradas.")


if __name__ == "__main__":
    calibrar()
