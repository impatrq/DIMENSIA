# Calibración de cámaras — DIMENSIA
# Calcula cuántos píxeles equivalen a 1 mm en cada cámara.
# Se corre UNA SOLA VEZ con un objeto de referencia de medidas conocidas.
# Uso:
#   python calibracion_camaras.py                        → calibrar ambas cámaras
#   python calibracion_camaras.py --camara superior      → solo la superior (índice 0)
#   python calibracion_camaras.py --camara lateral       → solo la lateral  (índice 1)
#   python calibracion_camaras.py --camara superior --indice 2 --mm 50
# Requiere: pip install opencv-python

import argparse
import cv2
import json
import os
import sys

from segmentacion import detectar_contorno_pieza

RUTA_CALIBRACION   = os.path.join(os.path.dirname(__file__), "calibracion_camaras.json")
CARPETA_CAPTURAS   = os.path.join(os.path.dirname(__file__), "capturas")
VALOR_DEFAULT_CALIB = 10.0   # valor puesto cuando la otra cámara aún no fue calibrada


def medir_referencia_en_imagen(ruta_imagen, camara):
    """
    Detecta el objeto de referencia en la imagen y devuelve su tamaño en píxeles.
    Usa el mismo pipeline que procesamiento.py y la misma medida por cámara:
      superior → diámetro del círculo mínimo (igual que procesar_superior)
      lateral  → ancho del rectángulo         (igual que procesar_lateral)
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

    # Detectar el contorno de la pieza con soporte para las dos polaridades
    # (objeto oscuro sobre fondo claro y objeto claro sobre fondo oscuro)
    contorno_principal, polaridad = detectar_contorno_pieza(grises)
    print(polaridad)

    # area_imagen lo necesitan las validaciones de tamaño más abajo
    area_imagen = imagen.shape[0] * imagen.shape[1]

    # El rectángulo envolvente se usa siempre: para la imagen de control y el límite 60 %.
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
    if area_objeto < area_imagen * 0.01:
        raise Exception(
            "El objeto detectado es demasiado pequeño. Verificá "
            "que el objeto de referencia esté bien visible y "
            "cerca de la cámara."
        )

    # Calcular la medida en píxeles que se usa para px_por_mm según la cámara,
    # para que coincida exactamente con lo que hace procesamiento.py en cada caso.
    if camara == "superior":
        # procesar_superior() usa el diámetro del círculo mínimo, no el rectángulo
        _, radio_px = cv2.minEnclosingCircle(contorno_principal)
        medida_px   = round(radio_px * 2)
        desc_medida = "diámetro del círculo mínimo"
    else:  # lateral
        # procesar_lateral() usa el ancho del rectángulo envolvente
        medida_px   = ancho_px
        desc_medida = "ancho del rectángulo"

    # Guardar imagen de control con el rectángulo detectado dibujado en rojo.
    # El nombre es el mismo que la imagen original con "_deteccion" agregado antes de la extensión.
    base, ext = os.path.splitext(ruta_imagen)
    ruta_deteccion = base + "_deteccion" + ext
    imagen_control = imagen.copy()
    cv2.rectangle(imagen_control, (x, y), (x + ancho_px, y + alto_px), (0, 0, 255), 3)
    cv2.imwrite(ruta_deteccion, imagen_control)

    # Informar el tamaño detectado y qué medida se usó para la calibración
    ancho_imagen = imagen.shape[1]
    alto_imagen  = imagen.shape[0]
    porcentaje_ancho = round(medida_px * 100 / ancho_imagen)
    print("Objeto detectado: {} px ({} % del ancho de la imagen) — {}".format(
        medida_px, porcentaje_ancho, desc_medida))

    # Si el rectángulo ocupa más del 60 % del ancho o del alto es probable que
    # Otsu haya detectado el fondo u otro elemento grande en lugar del objeto de referencia.
    if ancho_px > ancho_imagen * 0.60 or alto_px > alto_imagen * 0.60:
        raise Exception(
            "El objeto detectado ocupa demasiado de la imagen: probablemente "
            "se está midiendo el fondo. Usá un fondo liso y que contraste, "
            "sin manos ni otros objetos en el cuadro."
        )

    return medida_px, alto_px, ruta_deteccion


def _capturar_con_camara(indice, ruta_guardado):
    """Abre la cámara, muestra el índice y la resolución real, espera confirmación del usuario,
    captura y guarda la imagen."""
    cam = cv2.VideoCapture(indice)
    if not cam.isOpened():
        raise Exception(
            "No se pudo abrir la cámara con índice {}. "
            "¿Está conectada?".format(indice)
        )

    # Solicitar resolución máxima de la Logitech C920e
    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    # Imprimir el índice y la resolución REAL que aceptó la cámara antes de capturar,
    # porque algunas cámaras no aceptan 1920×1080 y devuelven otra resolución.
    ancho_real = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto_real  = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("  Índice de cámara: {}  |  Resolución real: {}×{}".format(
        indice, ancho_real, alto_real))

    # Descartar 30 cuadros para dar tiempo al autofocus y a la exposición automática.
    # Sin este calentamiento la imagen puede salir borrosa o sobreexpuesta.
    # 30 cuadros ≈ 2 segundos a 15 fps (el tiempo real depende del fps de la cámara).
    print("Ajustando enfoque...")
    for _ in range(30):
        cam.read()

    input("Presioná ENTER para capturar...")

    # Descartar 10 cuadros más tras el ENTER para asegurarse de no capturar
    # un cuadro viejo del buffer ni uno tomado mientras el enfoque se reajusta
    # por el movimiento del objeto o el cambio de escena al preparar la toma.
    for _ in range(10):
        cam.read()

    ret, frame = cam.read()
    cam.release()

    if not ret:
        raise Exception("Error al capturar imagen de la cámara {}.".format(indice))

    cv2.imwrite(ruta_guardado, frame)
    print("Imagen guardada en: {}".format(ruta_guardado))

    # Calcular la nitidez de la imagen como la varianza del Laplaciano.
    # Un valor alto indica bordes definidos (imagen nítida); uno bajo indica desenfoque.
    # El umbral de 100 es orientativo y puede ajustarse con pruebas reales.
    gris_captura = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    nitidez = cv2.Laplacian(gris_captura, cv2.CV_64F).var()
    print("Nitidez: {:.1f} (orientativo)".format(nitidez))
    if nitidez < 100:
        print("[AVISO] La imagen puede estar desenfocada. "
              "Alejá la cámara del objeto o esperá a que enfoque.")

    return ruta_guardado


def _capturar_y_medir(indice_camara, ruta_guardado, camara):
    """
    Captura una imagen con la cámara indicada y mide el objeto de referencia.
    camara: "superior" o "lateral" — determina qué medida se usa para px_por_mm.
    Después de detectar, muestra la ruta de la imagen de control y pide confirmación
    visual antes de aceptar el resultado.
    Si la medición falla o el operario rechaza la detección, ofrece reintentar.
    Devuelve (medida_px, alto_px) del objeto detectado.
    """
    while True:
        # Capturar y medir; si algo falla, ofrecer reintentar
        try:
            _capturar_con_camara(indice_camara, ruta_guardado)
            medida_px, alto_px, ruta_deteccion = medir_referencia_en_imagen(ruta_guardado, camara)
        except Exception as e:
            print("[ERROR] {}".format(e))
            respuesta = input("¿Querés reintentar? (s/n): ").strip().lower()
            if respuesta != "s":
                print("Calibración cancelada.")
                sys.exit(1)
            continue

        # Pedir confirmación visual antes de aceptar el resultado.
        # La imagen de control tiene el rectángulo dibujado para que el operario
        # pueda verificar que rodea solo el objeto de referencia y no el fondo.
        print("  Imagen de control guardada en: {}".format(ruta_deteccion))
        confirmacion = input(
            "Revisá la imagen de control. ¿El rectángulo rodea solo el objeto? (s/n): "
        ).strip().lower()
        if confirmacion != "s":
            # El operario indica que la detección es incorrecta: volver a capturar
            continue

        return medida_px, alto_px


def _pedir_mm_referencia(mm_cli):
    """
    Si mm_cli ya viene como float del argumento --mm, validarlo y devolverlo.
    Si no, pedirlo interactivamente con la misma validación de siempre.
    """
    if mm_cli is not None:
        if mm_cli <= 0:
            raise ValueError("El valor de --mm tiene que ser mayor a 0.")
        return mm_cli

    # Pedir interactivamente con validación de número mayor a cero
    while True:
        texto = input("¿Cuántos mm mide el objeto de referencia? (ej: 50): ")
        try:
            mm = float(texto)
        except ValueError:
            print("[ERROR] Ingresá un número válido.")
            continue
        if mm <= 0:
            print("[ERROR] El valor tiene que ser mayor a 0.")
            continue
        return mm


def _leer_calibracion_existente():
    """
    Intenta leer el archivo de calibración existente.
    Devuelve (dict, None) si se leyó bien o si no existe,
    o (None, mensaje_error) si existe pero no es un JSON válido.
    """
    if not os.path.exists(RUTA_CALIBRACION):
        return {}, None
    try:
        with open(RUTA_CALIBRACION, "r") as f:
            return json.load(f), None
    except (json.JSONDecodeError, ValueError) as e:
        return None, str(e)


def _guardar_clave(clave, valor):
    """
    Actualiza una sola clave en calibracion_camaras.json conservando la otra.
    - Si el archivo no existe: crea ambas claves; la otra queda en VALOR_DEFAULT_CALIB con aviso.
    - Si el archivo existe pero no es JSON válido: imprime el error y pide confirmación antes
      de sobreescribir.
    - Si el archivo existe y es válido: actualiza solo la clave indicada.
    """
    datos, error = _leer_calibracion_existente()

    if datos is None:
        # Archivo corrupto: pedir confirmación antes de sobreescribir
        print("[ERROR] El archivo calibracion_camaras.json existe pero no es JSON válido: {}".format(error))
        respuesta = input("¿Sobreescribir de todos modos? (s/n): ").strip().lower()
        if respuesta != "s":
            print("Guardado cancelado.")
            return
        datos = {}

    otra_clave = (
        "px_por_mm_lateral"   if clave == "px_por_mm_superior"
        else "px_por_mm_superior"
    )

    datos[clave] = valor

    # Si la clave opuesta falta, ponerla en el valor por defecto y avisar
    if otra_clave not in datos:
        datos[otra_clave] = VALOR_DEFAULT_CALIB
        print("[AVISO] {} sigue en el valor por defecto {}: falta calibrarla".format(
            otra_clave, VALOR_DEFAULT_CALIB))

    with open(RUTA_CALIBRACION, "w") as f:
        json.dump(datos, f, indent=2)


def _guardar_ambas(px_por_mm_superior, px_por_mm_lateral):
    """
    Guarda las dos claves a la vez (modo --camara ambas).
    Si el archivo existe pero no es JSON válido, pide confirmación antes de sobreescribir.
    """
    _, error = _leer_calibracion_existente()
    if error is not None:
        print("[ERROR] El archivo calibracion_camaras.json existe pero no es JSON válido: {}".format(error))
        respuesta = input("¿Sobreescribir de todos modos? (s/n): ").strip().lower()
        if respuesta != "s":
            print("Guardado cancelado.")
            return

    calibracion = {
        "px_por_mm_superior": px_por_mm_superior,
        "px_por_mm_lateral":  px_por_mm_lateral,
    }
    with open(RUTA_CALIBRACION, "w") as f:
        json.dump(calibracion, f, indent=2)


def calibrar():
    """
    Punto de entrada principal. Parsea argumentos y delega en el flujo
    correspondiente según --camara.
    """
    parser = argparse.ArgumentParser(description="Calibración de cámaras — DIMENSIA")
    parser.add_argument(
        "--camara",
        choices=["superior", "lateral", "ambas"],
        default="ambas",
        help="Qué cámara calibrar (default: ambas)",
    )
    parser.add_argument(
        "--indice",
        type=int,
        default=None,
        help="Índice OpenCV de la cámara. Solo se usa con --camara superior o lateral.",
    )
    parser.add_argument(
        "--mm",
        type=float,
        default=None,
        help="Tamaño real del objeto de referencia en mm (opcional; si no se pasa, se pregunta).",
    )
    args = parser.parse_args()

    os.makedirs(CARPETA_CAPTURAS, exist_ok=True)

    print("=" * 55)
    print("  CALIBRACIÓN DE CÁMARAS — DIMENSIA")
    print("=" * 55)

    mm_referencia = _pedir_mm_referencia(args.mm)

    if args.camara == "superior":
        indice = args.indice if args.indice is not None else 0
        print("\n--- Cámara SUPERIOR (índice {}) ---".format(indice))
        print("Colocá el objeto de referencia bajo la cámara SUPERIOR")
        ruta = os.path.join(CARPETA_CAPTURAS, "calibracion_superior.jpg")
        medida_px, _ = _capturar_y_medir(indice, ruta, "superior")
        px_por_mm = round(medida_px / mm_referencia, 4)
        print("  px_por_mm_superior = {} px/mm".format(px_por_mm))
        _guardar_clave("px_por_mm_superior", px_por_mm)
        print("\nCalibración guardada en calibracion_camaras.json.")

    elif args.camara == "lateral":
        indice = args.indice if args.indice is not None else 1
        print("\n--- Cámara LATERAL (índice {}) ---".format(indice))
        print("Ahora colocá el objeto bajo la cámara LATERAL")
        ruta = os.path.join(CARPETA_CAPTURAS, "calibracion_lateral.jpg")
        medida_px, _ = _capturar_y_medir(indice, ruta, "lateral")
        px_por_mm = round(medida_px / mm_referencia, 4)
        print("  px_por_mm_lateral = {} px/mm".format(px_por_mm))
        _guardar_clave("px_por_mm_lateral", px_por_mm)
        print("\nCalibración guardada en calibracion_camaras.json.")

    else:  # ambas — comportamiento igual al original
        # ─── Cámara superior ──────────────────────────────────────────────────
        print("\n--- Cámara SUPERIOR ---")
        print("Colocá el objeto de referencia bajo la cámara SUPERIOR")
        ruta_superior = os.path.join(CARPETA_CAPTURAS, "calibracion_superior.jpg")
        medida_px_sup, _ = _capturar_y_medir(0, ruta_superior, "superior")
        px_por_mm_superior = round(medida_px_sup / mm_referencia, 4)
        print("  px_por_mm_superior = {} px/mm".format(px_por_mm_superior))

        # ─── Cámara lateral ───────────────────────────────────────────────────
        print("\n--- Cámara LATERAL ---")
        print("Ahora colocá el objeto bajo la cámara LATERAL")
        ruta_lateral = os.path.join(CARPETA_CAPTURAS, "calibracion_lateral.jpg")
        medida_px_lat, _ = _capturar_y_medir(1, ruta_lateral, "lateral")
        px_por_mm_lateral = round(medida_px_lat / mm_referencia, 4)
        print("  px_por_mm_lateral = {} px/mm".format(px_por_mm_lateral))

        # ─── Guardar resultado ────────────────────────────────────────────────
        _guardar_ambas(px_por_mm_superior, px_por_mm_lateral)
        print("\nCalibración guardada en calibracion_camaras.json:")
        print("  px_por_mm_superior = {} px/mm".format(px_por_mm_superior))
        print("  px_por_mm_lateral  = {} px/mm".format(px_por_mm_lateral))
        print("\nListo. Las cámaras están calibradas.")


if __name__ == "__main__":
    calibrar()
