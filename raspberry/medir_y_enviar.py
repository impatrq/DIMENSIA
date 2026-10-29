# Demostración: mide UNA pieza con las cámaras y manda la inspección al backend.
# Script independiente: no modifica main.py ni el ciclo automatizado.
# Uso:
#   python medir_y_enviar.py
#   python medir_y_enviar.py --indice-superior 0 --indice-lateral 1
#   python medir_y_enviar.py --pieza "Niple NPT 1/2\"" --sin-enviar
# Requiere: pip install opencv-python requests

import argparse
import base64
import json
import os
import sys

import cv2
import requests

import config
from procesamiento import ProcesadorImagenes

# Campo del POST /inspeccion donde va el diámetro exterior (cámara superior).
# El backend usa "ancho" para esa dimensión.
CAMPO_DIAMETRO = "ancho"

CARPETA_CAPTURAS = os.path.join(os.path.dirname(__file__), "capturas")
RUTA_CALIBRACION = os.path.join(os.path.dirname(__file__), "calibracion_camaras.json")


# ── Helpers de pieza ──────────────────────────────────────────────────────────

def _obtener_nombre_pieza(args):
    """Devuelve el nombre de la pieza desde --pieza o desde GET /pieza_activa."""
    if args.pieza:
        return args.pieza
    try:
        resp = requests.get(config.URL_BACKEND + "/pieza_activa", timeout=3)
        resp.raise_for_status()
        nombre = resp.json().get("pieza")
    except requests.exceptions.RequestException as e:
        print("[ERROR] No se pudo consultar /pieza_activa: {}".format(e))
        sys.exit(1)
    if not nombre:
        print("[ERROR] No hay pieza activa seleccionada en el backend. "
              "Seleccioná una desde el dashboard o usá --pieza.")
        sys.exit(1)
    return nombre


def _obtener_datos_pieza(nombre):
    """Busca la pieza en GET /piezas por nombre exacto y devuelve su dict."""
    try:
        resp = requests.get(config.URL_BACKEND + "/piezas", timeout=3)
        resp.raise_for_status()
        piezas = resp.json()
    except requests.exceptions.RequestException as e:
        print("[ERROR] No se pudo consultar /piezas: {}".format(e))
        sys.exit(1)
    for p in piezas:
        if p.get("nombre") == nombre:
            return p
    print("[ERROR] No se encontró la pieza '{}' en el backend.".format(nombre))
    sys.exit(1)


# ── Helpers de cámara ─────────────────────────────────────────────────────────

def _capturar_camara(indice, ruta_guardado, label):
    """
    Captura una imagen con calentamiento de autofocus (30 cuadros descartados),
    solicita ENTER del operario y descarta 10 cuadros más antes de la captura final.
    Libera siempre la cámara aunque ocurra un error.
    """
    cam = cv2.VideoCapture(indice)
    try:
        if not cam.isOpened():
            raise Exception(
                "No se pudo abrir la cámara con índice {}. ¿Está conectada?".format(indice)
            )
        cam.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        # Descartar 30 cuadros para estabilizar el autofocus y la exposición automática
        for _ in range(30):
            cam.read()

        input("Poné la pieza y presioná ENTER ({})...".format(label))

        # Descartar 10 cuadros más para purgar el buffer y el posible reajuste de enfoque
        for _ in range(10):
            cam.read()

        ret, frame = cam.read()
        if not ret:
            raise Exception("Error al capturar imagen de la cámara {}.".format(indice))

        cv2.imwrite(ruta_guardado, frame)
        print("  Imagen guardada: {}".format(ruta_guardado))
        return ruta_guardado

    finally:
        cam.release()


def _imagen_a_base64(ruta):
    """
    Carga la imagen, la redimensiona a 640 px de ancho máximo (manteniendo relación de aspecto)
    y devuelve el contenido como string base64 en formato JPG.
    Devuelve None si la imagen no se puede cargar o codificar.
    """
    imagen = cv2.imread(ruta)
    if imagen is None:
        return None
    alto_orig, ancho_orig = imagen.shape[:2]
    if ancho_orig > 640:
        factor     = 640 / ancho_orig
        nuevo_alto = int(alto_orig * factor)
        imagen     = cv2.resize(imagen, (640, nuevo_alto))
    ok, buffer = cv2.imencode(".jpg", imagen)
    if not ok:
        return None
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def _leer_px_por_mm(clave):
    """
    Lee calibracion_camaras.json y devuelve el valor de la clave indicada
    ("px_por_mm_superior" o "px_por_mm_lateral").
    Devuelve None si el archivo no existe, la clave falta o el JSON no es válido.
    """
    if not os.path.exists(RUTA_CALIBRACION):
        return None
    try:
        with open(RUTA_CALIBRACION, "r") as f:
            return json.load(f).get(clave)
    except (json.JSONDecodeError, ValueError):
        return None


# ── Evaluación ────────────────────────────────────────────────────────────────

def _evaluar(medida, ref, tol):
    """
    Devuelve True si la medida está dentro de ref ± tol, False si está fuera,
    None si no se puede evaluar (algún valor es None).
    """
    if medida is None or ref is None or tol is None:
        return None
    return (ref - tol) <= medida <= (ref + tol)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Medir una pieza y enviar la inspección al backend — DIMENSIA"
    )
    parser.add_argument(
        "--indice-superior", type=int, default=0,
        help="Índice OpenCV de la cámara superior (default: 0)",
    )
    parser.add_argument(
        "--indice-lateral", type=int, default=None,
        help="Índice OpenCV de la cámara lateral (omitir para no usarla)",
    )
    parser.add_argument(
        "--pieza", type=str, default=None,
        help="Nombre exacto de la pieza (default: consultar /pieza_activa)",
    )
    parser.add_argument(
        "--sin-enviar", action="store_true",
        help="Solo mostrar el resultado sin hacer POST al backend",
    )
    args = parser.parse_args()

    os.makedirs(CARPETA_CAPTURAS, exist_ok=True)

    # ── Obtener pieza y sus referencias ───────────────────────────────────────
    nombre_pieza = _obtener_nombre_pieza(args)
    pieza        = _obtener_datos_pieza(nombre_pieza)
    print("\nPieza: {}".format(nombre_pieza))

    # ── Verificar calibración de la cámara superior ───────────────────────────
    # Sin calibración válida no tiene sentido capturar: el px_por_mm sería el
    # valor por defecto (10.0) y las medidas serían completamente incorrectas.
    px_sup = _leer_px_por_mm("px_por_mm_superior")
    if px_sup is None or px_sup == 10.0:
        print("[ERROR] La cámara superior no está calibrada en esta máquina: "
              "corré calibracion_camaras.py --camara superior --indice N --mm X")
        sys.exit(1)

    # ── Determinar si se usa la cámara lateral ────────────────────────────────
    # Si el índice fue pasado pero la cámara no está calibrada, descartarla con aviso.
    usar_lateral = args.indice_lateral is not None
    if usar_lateral:
        px_lat = _leer_px_por_mm("px_por_mm_lateral")
        if px_lat is None or px_lat == 10.0:
            print("[AVISO] La cámara lateral no está calibrada: no se usan largo ni alto.")
            usar_lateral = False

    # ── Capturar imágenes ─────────────────────────────────────────────────────
    ruta_superior = os.path.join(CARPETA_CAPTURAS, "medicion_superior.jpg")
    ruta_lateral  = os.path.join(CARPETA_CAPTURAS, "medicion_lateral.jpg")

    print("\n--- Cámara SUPERIOR (índice {}) ---".format(args.indice_superior))
    _capturar_camara(args.indice_superior, ruta_superior, "cámara superior")

    if usar_lateral:
        print("\n--- Cámara LATERAL (índice {}) ---".format(args.indice_lateral))
        _capturar_camara(args.indice_lateral, ruta_lateral, "cámara lateral")

    # ── Medir con ProcesadorImagenes ──────────────────────────────────────────
    procesador  = ProcesadorImagenes()

    med_sup     = procesador.procesar_superior(ruta_superior)
    diametro_mm = med_sup.get("diametro_exterior_mm")

    largo_mm = None
    alto_mm  = None
    if usar_lateral:
        med_lat  = procesador.procesar_lateral(ruta_lateral)
        largo_mm = med_lat.get("largo_mm")
        alto_mm  = med_lat.get("alto_mm")

    # ── Evaluar dimensiones ───────────────────────────────────────────────────
    evaluaciones = {
        "diámetro (ancho)": (diametro_mm, pieza.get("ancho_ref"), pieza.get("ancho_tol")),
        "largo":            (largo_mm,    pieza.get("largo_ref"), pieza.get("largo_tol")),
        "alto":             (alto_mm,     pieza.get("alto_ref"),  pieza.get("alto_tol")),
    }

    print("\n{:<22} {:>10}  {:>18}  {}".format("Dimensión", "Medida", "Referencia ± tol", "Estado"))
    print("-" * 65)

    resultados_evaluados     = []   # True = dentro, False = fuera
    dimensiones_no_evaluadas = []

    for nombre_dim, (medida, ref, tol) in evaluaciones.items():
        ok = _evaluar(medida, ref, tol)
        if ok is None:
            dimensiones_no_evaluadas.append(nombre_dim)
            medida_str = "{:.1f} mm".format(medida) if medida is not None else "—"
            ref_str    = "{} ± {}".format(ref, tol) if ref is not None and tol is not None else "—"
            print("{:<22} {:>10}  {:>18}  (no evaluada)".format(
                nombre_dim, medida_str, ref_str))
        else:
            resultados_evaluados.append(ok)
            estado = "OK" if ok else "FUERA"
            print("{:<22} {:>10}  {:>18}  {}".format(
                nombre_dim,
                "{:.1f} mm".format(medida),
                "{} ± {}".format(ref, tol),
                estado,
            ))

    if dimensiones_no_evaluadas:
        print("\nNo evaluadas: {}".format(", ".join(dimensiones_no_evaluadas)))

    if not resultados_evaluados:
        print("\n[ERROR] No se pudo evaluar ninguna dimensión. "
              "Verificá la calibración y que las imágenes sean nítidas.")
        sys.exit(1)

    resultado = "APROBADA" if all(resultados_evaluados) else "RECHAZADA"
    print("\nResultado: {}".format(resultado))

    # ── Armar payload ─────────────────────────────────────────────────────────
    payload = {
        "pieza":     nombre_pieza,
        "alto":      round(alto_mm,     1) if alto_mm     is not None else None,
        CAMPO_DIAMETRO: round(diametro_mm, 1) if diametro_mm is not None else None,
        "largo":     round(largo_mm,    1) if largo_mm    is not None else None,
        "resultado": resultado,
    }

    # Agregar capturas en base64 redimensionadas a 640 px de ancho
    b64_sup = _imagen_a_base64(ruta_superior)
    if b64_sup:
        payload["captura_superior"] = b64_sup

    if usar_lateral and os.path.exists(ruta_lateral):
        b64_lat = _imagen_a_base64(ruta_lateral)
        if b64_lat:
            payload["captura_lateral"] = b64_lat

    # ── Enviar al backend (o solo mostrar con --sin-enviar) ───────────────────
    payload_debug = {k: v for k, v in payload.items()
                     if k not in ("captura_superior", "captura_lateral")}

    if args.sin_enviar:
        print("\n(--sin-enviar: no se realizó el POST)")
        print("Payload (sin imágenes):\n{}".format(
            json.dumps(payload_debug, indent=2, ensure_ascii=False)))
        return

    try:
        resp = requests.post(config.URL_BACKEND + "/inspeccion", json=payload, timeout=5)
        resp.raise_for_status()
        datos_resp = resp.json()
        print("\nEnviado al backend.")
        print("  id:           {}".format(datos_resp.get("id")))
        print("  numero_serie: {}".format(datos_resp.get("numero_serie")))
    except requests.exceptions.RequestException as e:
        print("\n[ERROR] No se pudo enviar al backend: {}".format(e))
        print("Payload (sin imágenes):\n{}".format(
            json.dumps(payload_debug, indent=2, ensure_ascii=False)))
        sys.exit(1)


if __name__ == "__main__":
    main()
