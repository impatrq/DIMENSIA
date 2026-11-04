# Ciclo de inspección con comunicación Serial — DIMENSIA
# Lee señales de la ESP32 por Serial, captura con las dos cámaras,
# mide con visión y envía el resultado al backend Flask.
# Uso:
#   python ciclo_serial.py
#   python ciclo_serial.py --sin-serial --sin-enviar   # prueba en mesa
#   python ciclo_serial.py --pasos 4                   # ciclo corto
# Requiere: pip install pyserial opencv-python requests

import argparse
import base64
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime

import cv2
import requests
import serial

import config
from procesamiento import ProcesadorImagenes

# Campo de POST /inspeccion donde va el diámetro exterior (cámara superior).
CAMPO_DIAMETRO = "ancho"

CARPETA_CAPTURAS   = os.path.join(os.path.dirname(__file__), "capturas")
CARPETA_PENDIENTES = os.path.join(CARPETA_CAPTURAS, "pendientes")
RUTA_CALIBRACION   = os.path.join(os.path.dirname(__file__), "calibracion_camaras.json")

PAUSA_ASENTAMIENTO_SEG = 0.3   # tiempo entre PASO_OK y captura (el plato se asienta)
REINTENTOS_POST        = 3     # intentos de POST antes de guardar en pendientes


# ── Verificación de calibración ───────────────────────────────────────────────

def _leer_px_por_mm(clave):
    """Lee una clave de calibracion_camaras.json. Devuelve None si falta o no es válido."""
    if not os.path.exists(RUTA_CALIBRACION):
        return None
    try:
        with open(RUTA_CALIBRACION, "r") as f:
            return json.load(f).get(clave)
    except (json.JSONDecodeError, ValueError):
        return None


def _verificar_calibracion():
    """Termina con sys.exit si alguna cámara no está calibrada (valor 10.0 = por defecto)."""
    px_sup = _leer_px_por_mm("px_por_mm_superior")
    if px_sup is None or px_sup == 10.0:
        print("[ERROR] La cámara superior no está calibrada. "
              "Corré: python calibracion_camaras.py --camara superior")
        sys.exit(1)
    px_lat = _leer_px_por_mm("px_por_mm_lateral")
    if px_lat is None or px_lat == 10.0:
        print("[ERROR] La cámara lateral no está calibrada. "
              "Corré: python calibracion_camaras.py --camara lateral")
        sys.exit(1)


# ── Backend ───────────────────────────────────────────────────────────────────

def _obtener_pieza_activa():
    """Consulta /pieza_activa y devuelve el nombre, o termina con error."""
    try:
        resp = requests.get(config.URL_BACKEND + "/pieza_activa", timeout=3)
        resp.raise_for_status()
        nombre = resp.json().get("pieza")
    except requests.exceptions.RequestException as e:
        print("[ERROR] No se pudo consultar /pieza_activa: {}".format(e))
        sys.exit(1)
    if not nombre:
        print("[ERROR] No hay pieza activa seleccionada. "
              "Seleccioná una desde el dashboard.")
        sys.exit(1)
    return nombre


def _obtener_datos_pieza(nombre):
    """Busca la pieza en /piezas por nombre exacto y devuelve su dict, o termina con error."""
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


def _enviar_con_reintentos(payload):
    """
    Intenta POST /inspeccion hasta REINTENTOS_POST veces.
    Si todos fallan, guarda el payload (con imágenes) en capturas/pendientes/.
    """
    payload_debug = {k: v for k, v in payload.items()
                     if k not in ("captura_superior", "captura_lateral")}

    for intento in range(1, REINTENTOS_POST + 1):
        try:
            resp = requests.post(
                config.URL_BACKEND + "/inspeccion", json=payload, timeout=5
            )
            resp.raise_for_status()
            datos = resp.json()
            print("  Enviado al backend (intento {}).".format(intento))
            print("  id: {}  numero_serie: {}".format(
                datos.get("id"), datos.get("numero_serie")))
            return
        except requests.exceptions.RequestException as e:
            print("  [AVISO] Intento {}/{} fallido: {}".format(
                intento, REINTENTOS_POST, e))
            if intento < REINTENTOS_POST:
                time.sleep(1)

    # Todos los reintentos fallaron: guardar en pendientes
    os.makedirs(CARPETA_PENDIENTES, exist_ok=True)
    nombre_archivo = "pendiente_{}.json".format(
        datetime.now().strftime("%Y%m%d_%H%M%S"))
    ruta_pendiente = os.path.join(CARPETA_PENDIENTES, nombre_archivo)
    with open(ruta_pendiente, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print("  [ERROR] No se pudo enviar. Guardado en: {}".format(ruta_pendiente))
    print("  Payload (sin imágenes):\n  {}".format(
        json.dumps(payload_debug, indent=2, ensure_ascii=False)))


# ── Cámaras ───────────────────────────────────────────────────────────────────

def _configurar_v4l2(device, foco, exposicion):
    """
    Aplica ajustes de cámara vía v4l2-ctl.
    Foco manual, exposición manual y balance de blancos fijo.
    Los ajustes se pierden al desconectar la cámara, por eso se aplican al arrancar.
    check=False porque v4l2-ctl puede no estar disponible (el script sigue igual).
    """
    subprocess.run([
        "v4l2-ctl", "-d", device,
        "--set-ctrl=focus_automatic_continuous=0",
        "--set-ctrl=focus_absolute={}".format(foco),
        "--set-ctrl=auto_exposure=1",
        "--set-ctrl=exposure_dynamic_framerate=0",
        "--set-ctrl=exposure_time_absolute={}".format(exposicion),
        "--set-ctrl=white_balance_automatic=0",
        "--set-ctrl=white_balance_temperature=4600",
    ], check=False, capture_output=True)


def _abrir_camara(device, label):
    """
    Abre la cámara por su ruta de dispositivo, fija MJPG 1280×720 y descarta
    los primeros 10 cuadros para que el autofocus y la exposición se estabilicen.
    """
    cam = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cam.isOpened():
        raise Exception("No se pudo abrir la cámara {} ({}).".format(label, device))
    cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)
    # Descartar primeros 10 cuadros para estabilizar autofocus y exposición
    for _ in range(10):
        cam.read()
    return cam


def _capturar_par(cam_sup, cam_lat, angulo):
    """
    Captura un frame de cada cámara y los guarda con nombre por ángulo y timestamp.
    Devuelve {"superior": ruta, "lateral": ruta}.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ruta_sup = os.path.join(CARPETA_CAPTURAS, "superior_ang{}_{}.jpg".format(angulo, ts))
    ruta_lat = os.path.join(CARPETA_CAPTURAS, "lateral_ang{}_{}.jpg".format(angulo, ts))

    ret, frame = cam_sup.read()
    if not ret:
        raise Exception("Error al capturar cámara superior en {}°".format(angulo))
    cv2.imwrite(ruta_sup, frame)

    ret, frame = cam_lat.read()
    if not ret:
        raise Exception("Error al capturar cámara lateral en {}°".format(angulo))
    cv2.imwrite(ruta_lat, frame)

    return {"superior": ruta_sup, "lateral": ruta_lat}


def _imagen_a_base64(ruta):
    """Redimensiona a 640 px de ancho y devuelve base64 JPG, o None si falla."""
    imagen = cv2.imread(ruta)
    if imagen is None:
        return None
    h, w = imagen.shape[:2]
    if w > 640:
        imagen = cv2.resize(imagen, (640, int(h * 640 / w)))
    ok, buf = cv2.imencode(".jpg", imagen)
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("utf-8")


# ── Serial ────────────────────────────────────────────────────────────────────

def _abrir_serial(puerto):
    """
    Abre el puerto serial SIN resetear la ESP32 (dtr=False, rts=False).
    Un reset borraría el estado interno de la máquina de estados de MicroPython.
    """
    ser = serial.Serial()
    ser.port     = puerto
    ser.baudrate = 115200
    ser.timeout  = 1      # readline devuelve tras 1 s si no llega \n
    ser.dtr      = False  # sin reset por DTR
    ser.rts      = False  # sin reset por RTS
    ser.open()
    print("Serial abierto: {}".format(puerto))
    return ser


class _SerialSimulado:
    """
    Simula el lado ESP32 del protocolo dentro de Python.
    Permite probar el flujo completo sin hardware serial conectado.
    - Al esperar ARRIBA: pide ENTER al operario para simular que el elevador subió.
    - Al recibir PASO:   responde PASO_OK con una pequeña pausa.
    - Al recibir FIN:    imprime el resultado y queda listo para el próximo ciclo.
    """

    def __init__(self):
        self._pendiente        = None
        self._esperando_arriba = True

    def readline(self):
        if self._esperando_arriba:
            input("\n[SIMULADO] Presioná ENTER para simular ARRIBA (pieza en posición)...")
            self._esperando_arriba = False
            return b"ARRIBA\n"
        if self._pendiente:
            resp            = self._pendiente
            self._pendiente = None
            time.sleep(0.05)
            return resp
        time.sleep(0.05)
        return b"DEBUG: linea ignorada\n"

    def write(self, data):
        cmd = data.strip().decode("utf-8", errors="replace")
        if cmd == "PASO":
            self._pendiente = b"PASO_OK\n"
        elif cmd.startswith("FIN"):
            print("[SIMULADO] ESP32 recibió: {}".format(cmd))
            self._esperando_arriba = True  # listo para el próximo ciclo

    def close(self):
        print("[SIMULADO] Serial cerrado.")


def _leer_linea_serial(ser):
    """Lee una línea del serial. Devuelve string sin espacios, o '' si timeout."""
    try:
        raw = ser.readline()
        return raw.decode("utf-8", errors="replace").strip()
    except Exception as e:
        print("[ERROR] Falla al leer serial: {}".format(e))
        return ""


def _esperar_arriba(ser, timeout_seg):
    """
    Espera la señal ARRIBA de la ESP32.
    Ignora líneas de debug de MicroPython (cualquier línea que no sea protocolo).
    Devuelve True si llegó ARRIBA, False si se agotó el timeout.
    """
    inicio = time.time()
    while time.time() - inicio < timeout_seg:
        linea = _leer_linea_serial(ser)
        if linea == "ARRIBA":
            return True
        if linea.startswith("ERROR"):
            print("[ERROR ESP32] {}".format(linea))
            return False
        # Cualquier otra cosa es debug de MicroPython: ignorar silenciosamente
    return False


def _esperar_paso_ok(ser, timeout_seg=10):
    """
    Espera PASO_OK o ERROR tras enviar PASO.
    Devuelve ("PASO_OK", None), ("ERROR", detalle) o (None, None) si timeout.
    """
    inicio = time.time()
    while time.time() - inicio < timeout_seg:
        linea = _leer_linea_serial(ser)
        if linea == "PASO_OK":
            return "PASO_OK", None
        if linea.startswith("ERROR"):
            return "ERROR", linea[len("ERROR"):].strip()
        # Debug de MicroPython: ignorar
    return None, None


# ── Evaluación ────────────────────────────────────────────────────────────────

def _evaluar(medida, ref, tol):
    """True si medida ∈ [ref-tol, ref+tol]. None si falta algún valor."""
    if medida is None or ref is None or tol is None:
        return None
    return (ref - tol) <= medida <= (ref + tol)


def _imprimir_tabla(evaluaciones):
    """Imprime la tabla de dimensiones y devuelve (resultados_evaluados, no_evaluadas)."""
    print("\n{:<22} {:>10}  {:>18}  {}".format(
        "Dimensión", "Medida", "Referencia ± tol", "Estado"))
    print("-" * 65)
    resultados = []
    no_evaluadas = []
    for nombre_dim, (medida, ref, tol) in evaluaciones.items():
        ok = _evaluar(medida, ref, tol)
        medida_str = "{:.1f} mm".format(medida) if medida is not None else "—"
        ref_str    = "{} ± {}".format(ref, tol) if ref is not None and tol is not None else "—"
        if ok is None:
            no_evaluadas.append(nombre_dim)
            print("{:<22} {:>10}  {:>18}  (no evaluada)".format(
                nombre_dim, medida_str, ref_str))
        else:
            resultados.append(ok)
            print("{:<22} {:>10}  {:>18}  {}".format(
                nombre_dim, medida_str, ref_str, "OK" if ok else "FUERA"))
    return resultados, no_evaluadas


def _captura_mas_cercana_a_mediana(pasos, mediana_diametro):
    """
    Devuelve el dict de capturas del paso cuyo diámetro está más cerca de la mediana.
    Si ningún paso tiene diámetro válido, devuelve las capturas del primer paso no nulo.
    """
    if mediana_diametro is None:
        for p in pasos:
            if p["capturas"] is not None:
                return p["capturas"]
        return None
    mejor     = None
    mejor_dif = float("inf")
    for p in pasos:
        if p["capturas"] is None or p["diametro"] is None:
            continue
        dif = abs(p["diametro"] - mediana_diametro)
        if dif < mejor_dif:
            mejor_dif = dif
            mejor     = p["capturas"]
    return mejor


# ── Ciclo de inspección ───────────────────────────────────────────────────────

def _ejecutar_ciclo(ser, cam_sup, cam_lat, procesador, pieza, nombre_pieza,
                    n_pasos, sin_enviar):
    """
    Un ciclo completo: esperar ARRIBA → 8 pasos → mediana → evaluar → POST → FIN.
    Devuelve True si completó normalmente, False si se abortó sin POST.
    """
    # ── Paso 1: esperar ARRIBA ─────────────────────────────────────────────────
    print("\nEsperando ARRIBA de la ESP32 (timeout {} s)...".format(
        config.TIMEOUT_ARRIBA_SEG))
    if not _esperar_arriba(ser, config.TIMEOUT_ARRIBA_SEG):
        print("[AVISO] No llegó ARRIBA en {} s. Volviendo a esperar.".format(
            config.TIMEOUT_ARRIBA_SEG))
        return False

    print("Elevador arriba. Iniciando ciclo ({} pasos)...".format(n_pasos))
    angulo_paso = 360 // n_pasos
    pasos       = []

    # ── Paso 2: n_pasos giros + captura ───────────────────────────────────────
    for n in range(n_pasos):
        angulo = n * angulo_paso

        ser.write(b"PASO\n")

        estado, detalle = _esperar_paso_ok(ser)
        if estado == "ERROR":
            print("[ERROR ESP32] {}. Abortando ciclo.".format(detalle))
            return False
        if estado is None:
            print("[ERROR] Timeout esperando PASO_OK en paso {}. Abortando.".format(n + 1))
            return False

        # Esperar a que el plato se asiente antes de capturar
        time.sleep(PAUSA_ASENTAMIENTO_SEG)

        # Capturar y medir
        try:
            capturas = _capturar_par(cam_sup, cam_lat, angulo)
        except Exception as e:
            print("  [AVISO] Paso {:>2}/{} {}°  — falla de captura: {}".format(
                n + 1, n_pasos, angulo, e))
            pasos.append({"capturas": None, "diametro": None, "largo": None, "alto": None})
            continue

        med_sup  = procesador.procesar_superior(capturas["superior"])
        med_lat  = procesador.procesar_lateral(capturas["lateral"])
        diametro = med_sup.get("diametro_exterior_mm")
        largo    = med_lat.get("largo_mm")
        alto     = med_lat.get("alto_mm")

        print("  Paso {:>2}/{}  {:>3}°  OD:{:>8}  largo:{:>8}  alto:{:>8}".format(
            n + 1, n_pasos, angulo,
            "{:.1f}mm".format(diametro) if diametro is not None else "—",
            "{:.1f}mm".format(largo)    if largo    is not None else "—",
            "{:.1f}mm".format(alto)     if alto     is not None else "—",
        ))

        pasos.append({"capturas": capturas, "diametro": diametro,
                      "largo": largo, "alto": alto})

    # ── Paso 3: calcular medianas ──────────────────────────────────────────────
    vals_diametro = [p["diametro"] for p in pasos if p["diametro"] is not None]
    vals_largo    = [p["largo"]    for p in pasos if p["largo"]    is not None]
    vals_alto     = [p["alto"]     for p in pasos if p["alto"]     is not None]

    n_validos = len(vals_diametro)
    if n_validos < 4:
        print("[ERROR] Solo {} medición/es válida/s de diámetro (mínimo 4). "
              "Ciclo inválido.".format(n_validos))
        ser.write(b"FIN RECHAZADA\n")
        return False

    med_diametro = statistics.median(vals_diametro) if vals_diametro else None
    med_largo    = statistics.median(vals_largo)    if vals_largo    else None
    med_alto     = statistics.median(vals_alto)     if vals_alto     else None

    print("\nMedianas  —  OD: {}mm  largo: {}mm  alto: {}mm".format(
        round(med_diametro, 1) if med_diametro is not None else "—",
        round(med_largo,    1) if med_largo    is not None else "—",
        round(med_alto,     1) if med_alto     is not None else "—",
    ))

    # ── Paso 4: evaluar ───────────────────────────────────────────────────────
    evaluaciones = {
        "diámetro (ancho)": (med_diametro, pieza.get("ancho_ref"), pieza.get("ancho_tol")),
        "largo":            (med_largo,    pieza.get("largo_ref"), pieza.get("largo_tol")),
        "alto":             (med_alto,     pieza.get("alto_ref"),  pieza.get("alto_tol")),
    }
    resultados_evaluados, dim_no_evaluadas = _imprimir_tabla(evaluaciones)

    if dim_no_evaluadas:
        print("No evaluadas: {}".format(", ".join(dim_no_evaluadas)))

    if not resultados_evaluados:
        print("[ERROR] No se pudo evaluar ninguna dimensión. "
              "Verificá la calibración y la iluminación.")
        ser.write(b"FIN RECHAZADA\n")
        return False

    resultado = "APROBADA" if all(resultados_evaluados) else "RECHAZADA"
    print("\nResultado: {}".format(resultado))

    # ── Paso 5: armar payload ─────────────────────────────────────────────────
    payload = {
        "pieza":        nombre_pieza,
        "alto":         round(med_alto,     1) if med_alto     is not None else None,
        CAMPO_DIAMETRO: round(med_diametro, 1) if med_diametro is not None else None,
        "largo":        round(med_largo,    1) if med_largo    is not None else None,
        "resultado":    resultado,
    }

    # Captura representativa: el paso cuyo diámetro está más cerca de la mediana
    captura_ref = _captura_mas_cercana_a_mediana(pasos, med_diametro)
    if captura_ref:
        b64_sup = _imagen_a_base64(captura_ref["superior"])
        if b64_sup:
            payload["captura_superior"] = b64_sup
        b64_lat = _imagen_a_base64(captura_ref["lateral"])
        if b64_lat:
            payload["captura_lateral"] = b64_lat

    # ── Paso 6: enviar al backend ─────────────────────────────────────────────
    if sin_enviar:
        payload_debug = {k: v for k, v in payload.items()
                         if k not in ("captura_superior", "captura_lateral")}
        print("\n(--sin-enviar)")
        print("Payload (sin imágenes):\n{}".format(
            json.dumps(payload_debug, indent=2, ensure_ascii=False)))
    else:
        _enviar_con_reintentos(payload)

    # ── Paso 7: notificar a la ESP32 (siempre, aunque el POST haya fallado) ───
    cmd_fin = "FIN {}\n".format(resultado)
    ser.write(cmd_fin.encode("utf-8"))
    print("Enviado a ESP32: {}".format(cmd_fin.strip()))

    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ciclo de inspección con comunicación Serial — DIMENSIA"
    )
    parser.add_argument(
        "--sin-enviar", action="store_true",
        help="No hacer POST al backend: solo mostrar el resultado",
    )
    parser.add_argument(
        "--sin-serial", action="store_true",
        help="Simular la ESP32 dentro de Python (para probar en mesa sin hardware serial)",
    )
    parser.add_argument(
        "--pasos", type=int, default=8,
        help="Número de pasos de rotación por ciclo (default: 8)",
    )
    args = parser.parse_args()

    os.makedirs(CARPETA_CAPTURAS, exist_ok=True)

    # ── Verificar calibración antes de abrir cualquier hardware ───────────────
    _verificar_calibracion()

    # ── Obtener pieza activa ──────────────────────────────────────────────────
    # Se consulta una sola vez al arrancar. Si cambia durante el turno, reiniciar.
    nombre_pieza = _obtener_pieza_activa()
    pieza        = _obtener_datos_pieza(nombre_pieza)
    print("Pieza activa: {}".format(nombre_pieza))

    # ── Abrir cámaras ─────────────────────────────────────────────────────────
    print("Configurando cámaras...")
    _configurar_v4l2(config.CAM_SUPERIOR, config.FOCO_SUPERIOR, config.EXPOSICION_SUPERIOR)
    _configurar_v4l2(config.CAM_LATERAL,  config.FOCO_LATERAL,  config.EXPOSICION_LATERAL)

    cam_sup = _abrir_camara(config.CAM_SUPERIOR, "superior")
    cam_lat = _abrir_camara(config.CAM_LATERAL,  "lateral")
    print("Cámaras listas (1280×720, MJPG).")

    # ── Abrir serial (o simulador) ────────────────────────────────────────────
    if args.sin_serial:
        ser = _SerialSimulado()
        print("Modo --sin-serial: ESP32 simulada.")
    else:
        ser = _abrir_serial(config.PUERTO_SERIE)

    procesador = ProcesadorImagenes()

    print("\nSistema listo. Esperando ciclos (Ctrl+C para salir)...\n")

    try:
        while True:
            _ejecutar_ciclo(
                ser, cam_sup, cam_lat, procesador,
                pieza, nombre_pieza, args.pasos, args.sin_enviar,
            )
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        cam_sup.release()
        cam_lat.release()
        ser.close()
        print("Recursos liberados.")


if __name__ == "__main__":
    main()
