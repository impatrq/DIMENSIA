# Visor en vivo de la medición — DIMENSIA
# Muestra en el navegador (Mac o celular) lo que ven las dos cámaras y marca
# sobre la imagen qué se está midiendo:
#   - Superior: círculo detectado + diámetro exterior (OD).
#   - Lateral: contorno de la pieza + rectángulo envolvente con largo y alto,
#              y el recuadro amarillo de la zona de búsqueda (ROI).
#
# Se abre en:  http://DIMENSIA.local:8081
#
# Usos:
#   1) Solo mirar en vivo (sirve para ajustar luces y encuadre):
#        python3 visor_vivo.py --en-vivo
#   2) Dentro del ciclo: ciclo_serial.py llama a visor.publicar(...) después de
#      cada captura (ver docs en el prompt de integración).
#
# No modifica la medición: solo vuelve a correr los mismos detectores sobre la
# imagen para dibujar lo que encuentran.

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

import config
from segmentacion import detectar_circulo_superior, detectar_contorno_lateral

PUERTO = 8081
ANCHO_SALIDA = 1280          # ancho total de la imagen publicada (px)

VERDE = (0, 255, 0)
AMARILLO = (0, 255, 255)
ROJO = (0, 0, 255)
BLANCO = (255, 255, 255)

PAGINA = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DIMENSIA - Visor en vivo</title>
<style>body{margin:0;background:#111;color:#eee;font-family:sans-serif;text-align:center}
img{width:100%;max-width:1400px}h3{margin:8px}</style></head><body>
<h3>DIMENSIA - medicion en vivo</h3><img id="v" src="/frame.jpg">
<script>setInterval(()=>{document.getElementById('v').src='/frame.jpg?'+Date.now()},500)</script>
</body></html>"""


def _texto(img, txt, pos, color=BLANCO, escala=0.8):
    """Texto con borde negro para que se lea sobre cualquier fondo."""
    cv2.putText(img, txt, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, txt, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, color, 2, cv2.LINE_AA)


def anotar_superior(img, procesador):
    """Dibuja el círculo del anillo y su diámetro. Devuelve (imagen, od_mm o None)."""
    out = img.copy()
    try:
        res = detectar_circulo_superior(
            img, radio_min=config.HOUGH_RADIO_MIN, radio_max=config.HOUGH_RADIO_MAX,
            fondo=getattr(procesador, "_fondo_superior", None))
    except Exception:
        res = None
    if res is None:
        _texto(out, "SUPERIOR: no se detecta la pieza", (20, 40), ROJO)
        return out, None
    cx, cy, r = int(res[0]), int(res[1]), float(res[2])
    d_px = 2 * r
    od_mm = d_px / procesador.px_mm_superior
    cv2.circle(out, (cx, cy), int(round(r)), VERDE, 3)
    cv2.circle(out, (cx, cy), 5, ROJO, -1)
    p1, p2 = (int(cx - r), cy), (int(cx + r), cy)
    cv2.arrowedLine(out, (cx, cy), p2, AMARILLO, 3, tipLength=0.08)
    cv2.arrowedLine(out, (cx, cy), p1, AMARILLO, 3, tipLength=0.08)
    _texto(out, "OD {:.1f} mm ({:.0f} px)".format(od_mm, d_px), (max(cx - 140, 10), max(cy - int(r) - 15, 30)), VERDE)
    return out, od_mm


def anotar_lateral(img, procesador):
    """Dibuja ROI, contorno y rectángulo con largo y alto. Devuelve (imagen, largo_mm, alto_mm)."""
    out = img.copy()
    roi = getattr(config, "ROI_LATERAL", None)
    if roi:
        x, y, w, h = roi
        cv2.rectangle(out, (x, y), (x + w, y + h), AMARILLO, 2)
        _texto(out, "zona de busqueda", (x, max(y - 10, 25)), AMARILLO, 0.6)
    try:
        contorno, _ = detectar_contorno_lateral(
            img, fondo=getattr(procesador, "_fondo_lateral", None), roi=roi)
    except Exception:
        contorno = None
    if contorno is None:
        _texto(out, "LATERAL: no se detecta la pieza", (20, 40), ROJO)
        return out, None, None
    x, y, w, h = cv2.boundingRect(contorno)
    largo_mm = w / procesador.px_mm_lateral
    alto_mm = h / procesador.px_mm_lateral
    cv2.drawContours(out, [contorno], -1, VERDE, 2)
    cv2.rectangle(out, (x, y), (x + w, y + h), ROJO, 2)
    # Cotas: largo (horizontal) abajo, alto (vertical) a la derecha
    cv2.arrowedLine(out, (x, y + h + 18), (x + w, y + h + 18), AMARILLO, 2, tipLength=0.03)
    cv2.arrowedLine(out, (x + w, y + h + 18), (x, y + h + 18), AMARILLO, 2, tipLength=0.03)
    cv2.arrowedLine(out, (x + w + 18, y), (x + w + 18, y + h), AMARILLO, 2, tipLength=0.03)
    cv2.arrowedLine(out, (x + w + 18, y + h), (x + w + 18, y), AMARILLO, 2, tipLength=0.03)
    _texto(out, "largo {:.1f} mm".format(largo_mm), (x, y + h + 50), VERDE, 0.7)
    _texto(out, "alto {:.1f} mm".format(alto_mm), (min(x + w + 28, out.shape[1] - 200), y + h // 2), VERDE, 0.7)
    return out, largo_mm, alto_mm


def componer(img_sup, img_lat, procesador, titulo=""):
    """Anota las dos imágenes y las une lado a lado. Devuelve la imagen final."""
    sup, od = anotar_superior(img_sup, procesador)
    lat, largo, alto = anotar_lateral(img_lat, procesador)
    mitad = ANCHO_SALIDA // 2
    def ajustar(im):
        h = int(im.shape[0] * mitad / im.shape[1])
        return cv2.resize(im, (mitad, h))
    sup, lat = ajustar(sup), ajustar(lat)
    alto_max = max(sup.shape[0], lat.shape[0])
    lienzo = np.zeros((alto_max + 50, ANCHO_SALIDA, 3), np.uint8)
    lienzo[50:50 + sup.shape[0], :mitad] = sup
    lienzo[50:50 + lat.shape[0], mitad:] = lat
    _texto(lienzo, titulo or "medicion en vivo", (10, 33), BLANCO, 0.9)
    return lienzo


class VisorVivo:
    """Servidor HTTP mínimo que publica la última imagen anotada."""

    def __init__(self, puerto=PUERTO):
        self._jpg = None
        self._lock = threading.Lock()
        visor = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/frame.jpg"):
                    with visor._lock:
                        datos = visor._jpg
                    if datos is None:
                        self.send_response(204)
                        self.end_headers()
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(datos)
                else:
                    cuerpo = PAGINA.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(cuerpo)

        self._servidor = ThreadingHTTPServer(("0.0.0.0", puerto), Handler)
        self._hilo = threading.Thread(target=self._servidor.serve_forever, daemon=True)
        self._hilo.start()
        self.puerto = puerto

    def publicar(self, img_sup, img_lat, procesador, titulo=""):
        """Recibe imágenes BGR (arrays) y publica la versión anotada."""
        try:
            lienzo = componer(img_sup, img_lat, procesador, titulo)
            ok, buf = cv2.imencode(".jpg", lienzo, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                with self._lock:
                    self._jpg = buf.tobytes()
        except Exception as e:  # el visor nunca debe romper la medición
            print("[visor] error al publicar: {}".format(e))

    def publicar_rutas(self, ruta_sup, ruta_lat, procesador, titulo=""):
        """Igual que publicar(), pero leyendo las imágenes desde archivos."""
        sup, lat = cv2.imread(ruta_sup), cv2.imread(ruta_lat)
        if sup is not None and lat is not None:
            self.publicar(sup, lat, procesador, titulo)

    def cerrar(self):
        self._servidor.shutdown()


def _modo_en_vivo():
    """Abre las cámaras y publica de forma continua (para ajustar luces y encuadre)."""
    from ciclo_serial import _abrir_camara, _leer_cuadro_fresco
    from procesamiento import ProcesadorImagenes
    cam_sup = _abrir_camara(config.CAM_SUPERIOR, "superior")
    cam_lat = _abrir_camara(config.CAM_LATERAL, "lateral")
    proc = ProcesadorImagenes()
    visor = VisorVivo()
    print("Visor en vivo: http://DIMENSIA.local:{}   (Ctrl+C para salir)".format(visor.puerto))
    try:
        while True:
            ok1, sup = _leer_cuadro_fresco(cam_sup)
            ok2, lat = _leer_cuadro_fresco(cam_lat)
            if ok1 and ok2:
                visor.publicar(sup, lat, proc, "EN VIVO")
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        cam_sup.release()
        cam_lat.release()
        visor.cerrar()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Visor en vivo de la medición DIMENSIA")
    ap.add_argument("--en-vivo", action="store_true", help="publicar las cámaras de forma continua")
    ap.add_argument("--puerto", type=int, default=PUERTO)
    args = ap.parse_args()
    if args.en_vivo:
        _modo_en_vivo()
    else:
        ap.print_help()
