# Calibración de px/mm con los detectores reales de producción — DIMENSIA
# Usa detectar_circulo_superior y detectar_contorno_lateral de segmentacion.py,
# los mismos que usa procesamiento.py, así la calibración es consistente.
#
# Uso:
#   python calibrar_caja.py --alto-mm 57 --ancho-mm 34
#   python calibrar_caja.py --alto-mm 57 --ancho-mm 34 --guardar

import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

# Asegurar que el directorio del script está en el path para importar config y segmentacion
sys.path.insert(0, os.path.dirname(__file__))
import config
from segmentacion import detectar_circulo_superior, detectar_contorno_lateral

CARPETA_CAPTURAS = os.path.join(os.path.dirname(__file__), "capturas")
CARPETA_PRUEBAS  = os.path.expanduser("~/pruebas")
RUTA_JSON        = os.path.join(os.path.dirname(__file__), "calibracion_camaras.json")


def _ultima_captura(patron):
    """Devuelve la ruta del archivo más nuevo que coincide con el patrón glob."""
    archivos = sorted(glob.glob(patron))
    if not archivos:
        return None
    return archivos[-1]


def _cargar_fondo(ruta):
    """Carga la imagen de fondo si existe; devuelve None si no."""
    if os.path.exists(ruta):
        img = cv2.imread(ruta)
        if img is not None:
            return img
    return None


def _guardar_control(ruta_salida, imagen):
    """Guarda una imagen de control en ~/pruebas/, creando la carpeta si hace falta."""
    os.makedirs(CARPETA_PRUEBAS, exist_ok=True)
    cv2.imwrite(ruta_salida, imagen)
    print("  → imagen de control: {}".format(ruta_salida))


def calibrar_superior(ruta_img, ancho_mm):
    """
    Detecta el anillo del niple con detectar_circulo_superior.
    Devuelve (diametro_px, px_por_mm) o lanza Exception.
    """
    imagen = cv2.imread(ruta_img)
    if imagen is None:
        raise Exception("No se pudo leer: {}".format(ruta_img))

    fondo = _cargar_fondo(config.FONDO_SUPERIOR)
    resultado = detectar_circulo_superior(
        imagen,
        radio_min=config.HOUGH_RADIO_MIN,
        radio_max=config.HOUGH_RADIO_MAX,
        fondo=fondo,
    )
    if resultado is None:
        raise Exception("detectar_circulo_superior no encontró ningún círculo.")

    cx, cy, radio_px = resultado
    diametro_px = radio_px * 2
    px_por_mm   = diametro_px / ancho_mm

    # Imagen de control: círculo detectado sobre la imagen original
    ctrl = imagen.copy()
    cv2.circle(ctrl, (cx, cy), int(round(radio_px)), (0, 255, 0), 2)
    cv2.circle(ctrl, (cx, cy), 3, (0, 0, 255), -1)
    cv2.putText(ctrl, "d={:.1f}px  {:.2f}px/mm".format(diametro_px, px_por_mm),
                (cx - 100, cy - int(radio_px) - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    nombre_ctrl = os.path.join(
        CARPETA_PRUEBAS,
        os.path.splitext(os.path.basename(ruta_img))[0] + "_deteccion.jpg",
    )
    _guardar_control(nombre_ctrl, ctrl)

    return diametro_px, px_por_mm


def calibrar_lateral(ruta_img, ancho_mm, alto_mm):
    """
    Detecta el bbox del niple con detectar_contorno_lateral.
    Devuelve (ancho_px, alto_px, px_mm_ancho, px_mm_alto) o lanza Exception.
    """
    imagen = cv2.imread(ruta_img)
    if imagen is None:
        raise Exception("No se pudo leer: {}".format(ruta_img))

    fondo = _cargar_fondo(config.FONDO_LATERAL)
    contorno, descripcion = detectar_contorno_lateral(
        imagen,
        fondo=fondo,
        roi=config.ROI_LATERAL,
    )

    x, y, ancho_px, alto_px = cv2.boundingRect(contorno)
    px_mm_ancho = ancho_px / ancho_mm
    px_mm_alto  = alto_px  / alto_mm

    # Imagen de control: bbox y descripción del método
    ctrl = imagen.copy()
    cv2.rectangle(ctrl, (x, y), (x + ancho_px, y + alto_px), (0, 255, 0), 2)
    cv2.putText(ctrl, "{} x {} px".format(ancho_px, alto_px),
                (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(ctrl, descripcion[:50],
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1)
    nombre_ctrl = os.path.join(
        CARPETA_PRUEBAS,
        os.path.splitext(os.path.basename(ruta_img))[0] + "_deteccion.jpg",
    )
    _guardar_control(nombre_ctrl, ctrl)

    return ancho_px, alto_px, px_mm_ancho, px_mm_alto


def main():
    parser = argparse.ArgumentParser(
        description="Calcula px/mm usando los detectores de producción de DIMENSIA."
    )
    parser.add_argument("--alto-mm",  type=float, required=True,
                        help="Alto real de la pieza patrón en mm (ej: 57)")
    parser.add_argument("--ancho-mm", type=float, required=True,
                        help="Diámetro real de la pieza patrón en mm (ej: 34)")
    parser.add_argument("--guardar",  action="store_true",
                        help="Escribe calibracion_camaras.json con los valores calculados")
    args = parser.parse_args()

    # ── Buscar las últimas capturas ang360 ────────────────────────────────────
    patron_sup = os.path.join(CARPETA_CAPTURAS, "superior_ang360_*.jpg")
    patron_lat = os.path.join(CARPETA_CAPTURAS, "lateral_ang360_*.jpg")

    ruta_sup = _ultima_captura(patron_sup)
    ruta_lat = _ultima_captura(patron_lat)

    if ruta_sup is None:
        sys.exit("[ERROR] No se encontraron capturas superior_ang360_*.jpg en {}".format(
            CARPETA_CAPTURAS))
    if ruta_lat is None:
        sys.exit("[ERROR] No se encontraron capturas lateral_ang360_*.jpg en {}".format(
            CARPETA_CAPTURAS))

    print("Imágenes a procesar:")
    print("  Superior: {}".format(ruta_sup))
    print("  Lateral:  {}".format(ruta_lat))
    print()

    # ── Cámara superior ───────────────────────────────────────────────────────
    print("── Cámara superior ─────────────────────────────────")
    try:
        diametro_px, px_mm_sup = calibrar_superior(ruta_sup, args.ancho_mm)
        print("  Diámetro detectado: {:.1f} px".format(diametro_px))
        print("  px/mm superior:     {:.4f}  ({:.1f} px / {:.1f} mm)".format(
            px_mm_sup, diametro_px, args.ancho_mm))
    except Exception as e:
        sys.exit("[ERROR] Cámara superior: {}".format(e))

    # ── Cámara lateral ────────────────────────────────────────────────────────
    print()
    print("── Cámara lateral ──────────────────────────────────")
    try:
        ancho_px, alto_px, px_mm_lat_ancho, px_mm_lat_alto = calibrar_lateral(
            ruta_lat, args.ancho_mm, args.alto_mm)
        print("  Bbox detectado:     {} x {} px  (ancho x alto)".format(ancho_px, alto_px))
        print("  px/mm por ancho:    {:.4f}  ({} px / {:.1f} mm)".format(
            px_mm_lat_ancho, ancho_px, args.ancho_mm))
        print("  px/mm por alto:     {:.4f}  ({} px / {:.1f} mm)".format(
            px_mm_lat_alto,  alto_px,  args.alto_mm))
    except Exception as e:
        sys.exit("[ERROR] Cámara lateral: {}".format(e))

    # ── Consistencia lateral ──────────────────────────────────────────────────
    print()
    if px_mm_lat_ancho > 0 and px_mm_lat_alto > 0:
        diferencia_pct = abs(px_mm_lat_ancho - px_mm_lat_alto) / max(px_mm_lat_ancho, px_mm_lat_alto) * 100
    else:
        diferencia_pct = 100.0
    print("  Diferencia ancho/alto: {:.1f} %".format(diferencia_pct))

    if diferencia_pct < 5.0:
        px_mm_lat = (px_mm_lat_ancho + px_mm_lat_alto) / 2
        print("  → Usando promedio:  {:.4f} px/mm".format(px_mm_lat))
        consistente = True
    else:
        print("[AVISO] La diferencia lateral ({:.1f} %) supera el 5 %. "
              "Verificá que las medidas --ancho-mm y --alto-mm sean correctas "
              "y que el bbox esté bien centrado.".format(diferencia_pct))
        consistente = False

    # ── Guardar ───────────────────────────────────────────────────────────────
    if args.guardar:
        if not consistente:
            sys.exit("[ERROR] No se guardó: diferencia lateral fuera de tolerancia.")
        datos = {
            "px_por_mm_superior": round(px_mm_sup,   4),
            "px_por_mm_lateral":  round(px_mm_lat,   4),
        }
        with open(RUTA_JSON, "w") as f:
            json.dump(datos, f, indent=2)
        print()
        print("Guardado en {}:".format(RUTA_JSON))
        print("  px_por_mm_superior: {}".format(datos["px_por_mm_superior"]))
        print("  px_por_mm_lateral:  {}".format(datos["px_por_mm_lateral"]))
    else:
        print()
        print("(Corré con --guardar para escribir calibracion_camaras.json)")


if __name__ == "__main__":
    main()
