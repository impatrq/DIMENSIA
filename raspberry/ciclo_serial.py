# Ciclo de inspección con comunicación Serial — DIMENSIA
# Lee señales de la ESP32 por Serial, captura con las dos cámaras,
# mide con visión y envía el resultado al backend Flask.
# Uso:
#   python ciclo_serial.py
#   python ciclo_serial.py --iniciar                   # enviar INICIAR + esperar LISTO
#   python ciclo_serial.py --sin-serial --sin-enviar   # prueba en mesa
#   python ciclo_serial.py --debug-serial              # mostrar todo lo que llega por serial
#   python ciclo_serial.py --pasos 4                   # ciclo corto
# Requiere: pip install pyserial opencv-python requests

import argparse
import base64
import fcntl
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
LOCK_PATH          = "/tmp/ciclo_serial.lock"

PAUSA_ASENTAMIENTO_SEG = 0.3   # tiempo entre PASO_OK y captura (el plato se asienta)
REINTENTOS_POST        = 3     # intentos de POST antes de guardar en pendientes
REINTENTOS_CAMARA      = 3     # aperturas extra antes de fallar definitivamente
PAUSA_REINTENTO_CAMARA = 2     # segundos entre reintentos de apertura de cámara

_DEBUG_SERIAL = False  # activado con --debug-serial: imprime cada línea recibida de la ESP32
_lock_fd      = None   # descriptor del archivo de lock (mantenido abierto durante toda la sesión)


# ── Instancia única ───────────────────────────────────────────────────────────

def _tomar_lock():
    """
    Toma un lock exclusivo no bloqueante sobre LOCK_PATH con fcntl.flock.
    Si ya hay otra instancia corriendo, imprime su PID y termina el proceso.
    El lock se libera automáticamente cuando el proceso termina (el kernel
    cierra el descriptor al salir, incluso ante kill o excepción no capturada).

    Se abre con "a+" para no truncar el archivo antes de tener el lock.
    Solo después de conseguir el lock se trunca y se escribe el PID propio,
    así un tercer intento siempre lee el PID correcto del proceso dueño.
    """
    global _lock_fd
    _lock_fd = open(LOCK_PATH, "a+")
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Leer el PID sin modificar el archivo (el proceso dueño lo tiene bloqueado)
        _lock_fd.seek(0)
        pid_existente = _lock_fd.read().strip()
        pid_info = "PID {}".format(pid_existente) if pid_existente else "PID desconocido"
        print("[ERROR] Ya hay una instancia de ciclo_serial.py corriendo ({}).".format(pid_info))
        print("        Para cerrarla: kill {}".format(
            pid_existente if pid_existente else "<PID>"))
        sys.exit(1)
    # Conseguimos el lock: truncar y escribir nuestro PID
    _lock_fd.seek(0)
    _lock_fd.truncate()
    _lock_fd.write(str(os.getpid()))
    _lock_fd.flush()


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


def _consultar_pieza_por_ciclo(nombre_anterior, pieza_anterior):
    """
    Consulta /pieza_activa justo después de ARRIBA, en cada ciclo.
    Si el backend no responde usa la última pieza conocida.
    Si la pieza cambió, consulta sus datos y lo avisa.
    Devuelve (nombre, pieza_dict).
    """
    try:
        resp = requests.get(config.URL_BACKEND + "/pieza_activa", timeout=3)
        resp.raise_for_status()
        nombre = resp.json().get("pieza")
    except requests.exceptions.RequestException as e:
        print("[AVISO] No se pudo consultar /pieza_activa: {}. "
              "Usando última pieza conocida: '{}'.".format(e, nombre_anterior))
        return nombre_anterior, pieza_anterior

    if not nombre:
        print("[AVISO] No hay pieza activa en el backend. "
              "Usando última conocida: '{}'.".format(nombre_anterior))
        return nombre_anterior, pieza_anterior

    if nombre == nombre_anterior:
        return nombre, pieza_anterior

    # La pieza cambió: buscar los nuevos datos
    print("[AVISO] Pieza cambió: '{}' → '{}'.".format(nombre_anterior, nombre))
    try:
        resp2 = requests.get(config.URL_BACKEND + "/piezas", timeout=3)
        resp2.raise_for_status()
        for p in resp2.json():
            if p.get("nombre") == nombre:
                return nombre, p
        print("[AVISO] No se encontró '{}' en /piezas. "
              "Usando última pieza conocida.".format(nombre))
        return nombre_anterior, pieza_anterior
    except requests.exceptions.RequestException as e:
        print("[AVISO] No se pudo consultar /piezas: {}. "
              "Usando última pieza conocida.".format(e))
        return nombre_anterior, pieza_anterior


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

def _configurar_v4l2(device, label, foco, exposicion, ganancia=0):
    """
    Aplica los ajustes de cámara vía v4l2-ctl en llamadas separadas,
    respetando el orden de dependencia:
      1. Deshabilitar autofocus → 2. Fijar foco manual
      3. Modo exposición manual → 4. Deshabilitar framerate dinámico
      5. Fijar tiempo de exposición
      6. Deshabilitar AWB → 7. Fijar temperatura de color
      8. Fijar ganancia (siempre, incluso si es 0)
    Los controles 2, 5 y 7 fallan si se envían en el mismo comando que los
    controles que los habilitan (el modo automático todavía está activo cuando
    v4l2-ctl procesa la lista de una vez). Usarlos en llamadas separadas garantiza
    que cada modo automático esté desactivado antes de fijar el valor manual.
    Si v4l2-ctl no está instalado, avisa una vez y vuelve.
    Si un control falla, avisa con el nombre y el stderr, y sigue con los demás.
    """
    controles = [
        ("focus_automatic_continuous", "0"),
        ("focus_absolute",             str(foco)),
        ("auto_exposure",              "1"),
        ("exposure_dynamic_framerate", "0"),
        ("exposure_time_absolute",     str(exposicion)),
        ("white_balance_automatic",    "0"),
        ("white_balance_temperature",  "4600"),
    ]
    controles.append(("gain", str(ganancia)))
    for nombre, valor in controles:
        try:
            res = subprocess.run(
                ["v4l2-ctl", "-d", device,
                 "--set-ctrl={}={}".format(nombre, valor)],
                check=False, capture_output=True,
            )
            if res.returncode != 0:
                stderr = res.stderr.decode("utf-8", errors="replace").strip()
                print("[AVISO] v4l2-ctl cámara {}, control '{}' falló: {}".format(
                    label, nombre, stderr or "(sin mensaje)"))
        except FileNotFoundError:
            print("[AVISO] v4l2-ctl no está instalado. "
                  "Los ajustes de foco/exposición no se aplicaron.")
            return  # si no está instalado, no tiene sentido seguir


def _abrir_camara(device, label):
    """
    Abre la cámara por su ruta de dispositivo, fija MJPG 1280×720 y descarta
    los primeros 10 cuadros para que el autofocus y la exposición se estabilicen.

    Si no se puede abrir, reintenta REINTENTOS_CAMARA veces con
    PAUSA_REINTENTO_CAMARA s de espera entre cada intento. Si sigue fallando,
    corre `fuser -v` sobre la ruta real del dispositivo (resolviendo el symlink
    by-id) para identificar qué proceso tiene el dispositivo ocupado.
    """
    for intento in range(1, REINTENTOS_CAMARA + 2):  # +2: 1 intento original + REINTENTOS_CAMARA
        cam = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if cam.isOpened():
            break
        cam.release()
        if intento <= REINTENTOS_CAMARA:
            print("[AVISO] No se pudo abrir cámara {} (intento {}/{}). "
                  "Reintentando en {} s...".format(
                      label, intento, REINTENTOS_CAMARA + 1, PAUSA_REINTENTO_CAMARA))
            time.sleep(PAUSA_REINTENTO_CAMARA)
    else:
        # Todos los intentos fallaron: intentar diagnosticar con fuser
        detalle = _diagnostico_dispositivo(device)
        raise Exception(
            "No se pudo abrir la cámara {} ({}) tras {} intentos. {}".format(
                label, device, REINTENTOS_CAMARA + 1, detalle))

    # Limitar el buffer interno a 1 cuadro para reducir la latencia.
    # No todos los backends lo soportan; el error se ignora silenciosamente.
    try:
        cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)
    # Descartar primeros 10 cuadros para estabilizar autofocus y exposición
    for _ in range(10):
        cam.read()
    return cam


def _diagnostico_dispositivo(device):
    """
    Resuelve el symlink by-id a la ruta real y ejecuta fuser -v para ver
    qué proceso tiene el dispositivo abierto. Devuelve un string descriptivo.
    Si fuser no existe o falla, devuelve un aviso genérico sin lanzar excepción.
    """
    try:
        ruta_real = os.path.realpath(device)
    except Exception:
        ruta_real = device
    try:
        res = subprocess.run(
            ["fuser", "-v", ruta_real],
            capture_output=True, timeout=5,
        )
        salida = (res.stdout + res.stderr).decode("utf-8", errors="replace").strip()
        if salida:
            return "Proceso que tiene el dispositivo ({}):\n{}".format(ruta_real, salida)
        return "Ningún proceso detectado con fuser en {}.".format(ruta_real)
    except FileNotFoundError:
        return "fuser no está disponible para diagnosticar {}.".format(ruta_real)
    except Exception as e:
        return "No se pudo ejecutar fuser: {}.".format(e)


def _leer_cuadro_fresco(cam, descartar=None):
    """
    Vacía el buffer de la cámara descartando `descartar` cuadros con grab()
    (rápido: decodifica solo el próximo en la cola, no el frame completo)
    y hace read() para obtener uno fresco. Reduce la diferencia entre el
    momento de disparo y el contenido real del frame capturado.
    """
    if descartar is None:
        descartar = config.CUADROS_DESCARTADOS
    for _ in range(descartar):
        cam.grab()
    return cam.read()


def _capturar_par(cam_sup, cam_lat, angulo):
    """
    Captura un frame fresco de cada cámara y los guarda con nombre por ángulo y timestamp.
    Usa _leer_cuadro_fresco para descartar cuadros viejos del buffer.
    Devuelve {"superior": ruta, "lateral": ruta}.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ruta_sup = os.path.join(CARPETA_CAPTURAS, "superior_ang{}_{}.jpg".format(angulo, ts))
    ruta_lat = os.path.join(CARPETA_CAPTURAS, "lateral_ang{}_{}.jpg".format(angulo, ts))

    ret, frame = _leer_cuadro_fresco(cam_sup)
    if not ret:
        raise Exception("Error al capturar cámara superior en {}°".format(angulo))
    cv2.imwrite(ruta_sup, frame)

    ret, frame = _leer_cuadro_fresco(cam_lat)
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


def _limpiar_capturas(pasos, captura_ref):
    """
    Borra todos los JPG del ciclo que no sean la captura representativa.
    Los errores de borrado se ignoran silenciosamente (el archivo puede
    no existir si la captura falló).
    """
    rutas_conservar = set()
    if captura_ref:
        if captura_ref.get("superior"):
            rutas_conservar.add(captura_ref["superior"])
        if captura_ref.get("lateral"):
            rutas_conservar.add(captura_ref["lateral"])

    for p in pasos:
        if p["capturas"] is None:
            continue
        for ruta in p["capturas"].values():
            if ruta and ruta not in rutas_conservar:
                try:
                    os.remove(ruta)
                except OSError:
                    pass


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
    - Sin --iniciar: pide ENTER para simular ARRIBA al inicio de cada ciclo.
    - Con --iniciar: al recibir INICIAR responde ARRIBA sin pedir ENTER.
    - Al recibir PASO:   responde PASO_OK (o ERROR si simular_error_en_paso coincide).
    - Al recibir FIN:    encola LISTO (simula que el elevador bajó).

    Parámetro interno de prueba:
      simular_error_en_paso (int o None): si está seteado, cuando se recibe
      ese PASO (contando desde 1) se responde ERROR TIMEOUT_RPI en lugar de
      PASO_OK, y se encola LISTO automáticamente (la ESP32 baja sola ante error).
    """

    def __init__(self, simular_error_en_paso=None):
        self._pendiente            = None
        self._esperando_arriba     = True
        self._post_listo           = False  # True: próxima llamada a readline devuelve LISTO
        self._simular_error_en_paso = simular_error_en_paso
        self._contador_pasos       = 0

    def readline(self):
        # Respuesta pendiente tiene prioridad (ARRIBA tras INICIAR, PASO_OK, ERROR)
        if self._pendiente:
            resp            = self._pendiente
            self._pendiente = None
            time.sleep(0.05)
            return resp
        # FIN fue enviado (o error simulado): entregar LISTO y preparar el próximo ciclo
        if self._post_listo:
            self._post_listo       = False
            self._esperando_arriba = True
            self._contador_pasos   = 0
            time.sleep(0.05)
            return b"LISTO\n"
        # Sin INICIAR: pedir ENTER al operario para simular ARRIBA
        if self._esperando_arriba:
            input("\n[SIMULADO] Presioná ENTER para simular ARRIBA (pieza en posición)...")
            self._esperando_arriba = False
            return b"ARRIBA\n"
        time.sleep(0.05)
        return b"DEBUG: linea ignorada\n"

    def write(self, data):
        cmd = data.strip().decode("utf-8", errors="replace")
        if cmd == "INICIAR":
            # Responde ARRIBA sin ENTER; cancela cualquier LISTO pendiente
            self._pendiente        = b"ARRIBA\n"
            self._post_listo       = False
            self._esperando_arriba = False
            self._contador_pasos   = 0
        elif cmd == "PASO":
            self._contador_pasos += 1
            if (self._simular_error_en_paso is not None
                    and self._contador_pasos == self._simular_error_en_paso):
                print("[SIMULADO] Simulando ERROR en paso {}.".format(self._contador_pasos))
                # La ESP32 real baja sola y luego manda LISTO
                self._pendiente  = b"ERROR TIMEOUT_RPI\n"
                self._post_listo = True
            else:
                self._pendiente = b"PASO_OK\n"
        elif cmd.startswith("FIN"):
            print("[SIMULADO] ESP32 recibió: {}".format(cmd))
            self._post_listo = True  # LISTO se entregará en el próximo readline

    def reset_input_buffer(self):
        """No-op: el simulador no tiene buffer real que limpiar."""
        pass

    def close(self):
        print("[SIMULADO] Serial cerrado.")


def _leer_linea_serial(ser):
    """Lee una línea del serial. Devuelve string sin espacios, o '' si timeout."""
    try:
        raw   = ser.readline()
        linea = raw.decode("utf-8", errors="replace").strip()
        if _DEBUG_SERIAL and linea:
            print("[ESP32] {}".format(linea))
        return linea
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


def _esperar_listo(ser, timeout_seg):
    """
    Espera la señal LISTO de la ESP32 (elevador terminó de bajar, lista para otro INICIAR).
    Solo se usa en modo --iniciar.
    Devuelve True si llegó LISTO, False si se agotó el timeout.
    """
    inicio = time.time()
    while time.time() - inicio < timeout_seg:
        linea = _leer_linea_serial(ser)
        if linea == "LISTO":
            return True
        if linea.startswith("ERROR"):
            print("[AVISO ESP32] {} (esperando LISTO)".format(linea))
        # Debug de MicroPython: ignorar
    return False


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

def _ejecutar_ciclo(ser, cam_sup, cam_lat, procesador, nombre_pieza, pieza,
                    n_pasos, sin_enviar, conservar_capturas, usar_iniciar=False):
    """
    Un ciclo completo: (INICIAR →) esperar ARRIBA → consultar pieza → n pasos
    → mediana → evaluar → FIN → POST → limpiar capturas → (esperar LISTO).

    FIN se envía ANTES del POST porque el POST con reintentos puede tardar ~17 s
    y la ESP32 aborta tras 30 s de silencio.

    Los ciclos inválidos (< 4 mediciones o sin referencias evaluables) siempre
    generan un POST con resultado RECHAZADA: el operario puede ver la inspección
    fallida en el dashboard.

    Devuelve (completó, nombre_pieza_actual, pieza_actual).
    completó = False solo cuando hay un error de comunicación serial irrecuperable.
    """
    # Limpiar buffer de entrada al empezar cada ciclo para descartar
    # cualquier basura acumulada entre ciclos.
    ser.reset_input_buffer()

    # ── Paso 1 (opcional): enviar INICIAR y esperar ARRIBA ────────────────────
    if usar_iniciar:
        input("\nPresioná ENTER para iniciar el ciclo...")
        ser.write(b"INICIAR\n")
        print("Enviado a ESP32: INICIAR")

    print("\nEsperando ARRIBA de la ESP32 (timeout {} s)...".format(
        config.TIMEOUT_ARRIBA_SEG))
    if not _esperar_arriba(ser, config.TIMEOUT_ARRIBA_SEG):
        print("[AVISO] No llegó ARRIBA en {} s. Volviendo a esperar.".format(
            config.TIMEOUT_ARRIBA_SEG))
        return False, nombre_pieza, pieza

    # ── Actualizar pieza activa en cada ciclo ──────────────────────────────────
    # Si cambió en el dashboard entre dos ciclos, se toma el nuevo valor.
    nombre_pieza, pieza = _consultar_pieza_por_ciclo(nombre_pieza, pieza)

    print("Pieza: {}  |  Iniciando ciclo ({} pasos)...".format(nombre_pieza, n_pasos))
    angulo_paso = 360 // n_pasos
    pasos       = []

    # ── Paso 2: n_pasos giros + captura ───────────────────────────────────────
    for n in range(n_pasos):
        # El ángulo corresponde a la posición DESPUÉS del giro.
        angulo = (n + 1) * angulo_paso

        # Limpiar buffer antes de enviar PASO para no confundir respuestas viejas.
        ser.reset_input_buffer()
        ser.write(b"PASO\n")

        estado, detalle = _esperar_paso_ok(ser)
        if estado == "ERROR":
            print("[ERROR ESP32] {}. Abortando ciclo.".format(detalle))
            if usar_iniciar:
                print("Esperando LISTO de la ESP32 (el elevador puede estar bajando)...")
                if not _esperar_listo(ser, config.TIMEOUT_LISTO_SEG):
                    print("[AVISO] No llegó LISTO en {} s.".format(config.TIMEOUT_LISTO_SEG))
            return False, nombre_pieza, pieza
        if estado is None:
            print("[ERROR] Timeout esperando PASO_OK en paso {}. Abortando.".format(n + 1))
            if usar_iniciar:
                print("Esperando LISTO de la ESP32 (el elevador puede estar bajando)...")
                if not _esperar_listo(ser, config.TIMEOUT_LISTO_SEG):
                    print("[AVISO] No llegó LISTO en {} s.".format(config.TIMEOUT_LISTO_SEG))
            return False, nombre_pieza, pieza

        # Esperar a que el plato se asiente antes de capturar
        time.sleep(PAUSA_ASENTAMIENTO_SEG)

        # Capturar y medir
        try:
            capturas = _capturar_par(cam_sup, cam_lat, angulo)
        except Exception as e:
            print("  [AVISO] Paso {:>2}/{} {:>3}°  — falla de captura: {}".format(
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

    n_validos    = len(vals_diametro)
    med_diametro = statistics.median(vals_diametro) if vals_diametro else None
    med_largo    = statistics.median(vals_largo)    if vals_largo    else None
    med_alto     = statistics.median(vals_alto)     if vals_alto     else None

    # ── Paso 4: evaluar ───────────────────────────────────────────────────────
    if n_validos < 4:
        print("[ERROR] Solo {} medición/es válida/s de diámetro (mínimo 4). "
              "Ciclo inválido — se registra como RECHAZADA.".format(n_validos))
        resultado = "RECHAZADA"
        resultados_evaluados = []
    else:
        print("\nMedianas  —  OD: {}mm  largo: {}mm  alto: {}mm".format(
            round(med_diametro, 1) if med_diametro is not None else "—",
            round(med_largo,    1) if med_largo    is not None else "—",
            round(med_alto,     1) if med_alto     is not None else "—",
        ))

        evaluaciones = {
            "diámetro (ancho)": (med_diametro, pieza.get("ancho_ref"), pieza.get("ancho_tol")),
            "largo":            (med_largo,    pieza.get("largo_ref"), pieza.get("largo_tol")),
            "alto":             (med_alto,     pieza.get("alto_ref"),  pieza.get("alto_tol")),
        }
        resultados_evaluados, dim_no_evaluadas = _imprimir_tabla(evaluaciones)

        if dim_no_evaluadas:
            print("No evaluadas: {}".format(", ".join(dim_no_evaluadas)))

        if not resultados_evaluados:
            print("[ERROR] No se pudo evaluar ninguna dimensión — "
                  "verificá referencias de la pieza en el backend.")
            resultado = "RECHAZADA"
        else:
            resultado = "APROBADA" if all(resultados_evaluados) else "RECHAZADA"

    print("\nResultado: {}".format(resultado))

    # ── Paso 5: armar payload ─────────────────────────────────────────────────
    captura_ref = _captura_mas_cercana_a_mediana(pasos, med_diametro)
    payload = {
        "pieza":        nombre_pieza,
        "alto":         round(med_alto,     1) if med_alto     is not None else None,
        CAMPO_DIAMETRO: round(med_diametro, 1) if med_diametro is not None else None,
        "largo":        round(med_largo,    1) if med_largo    is not None else None,
        "resultado":    resultado,
    }

    if captura_ref:
        b64_sup = _imagen_a_base64(captura_ref["superior"])
        if b64_sup:
            payload["captura_superior"] = b64_sup
        b64_lat = _imagen_a_base64(captura_ref["lateral"])
        if b64_lat:
            payload["captura_lateral"] = b64_lat

    # ── Paso 6: notificar a la ESP32 ANTES del POST ───────────────────────────
    # El POST con reintentos puede tardar ~17 s; la ESP32 aborta a los 30 s de
    # silencio. FIN se envía siempre, aunque el POST falle después.
    cmd_fin = "FIN {}\n".format(resultado)
    ser.write(cmd_fin.encode("utf-8"))
    print("Enviado a ESP32: {}".format(cmd_fin.strip()))

    # ── Paso 7: enviar al backend ─────────────────────────────────────────────
    # Siempre se envía, incluso para ciclos inválidos o no evaluables,
    # para que el dashboard muestre la inspección fallida.
    if sin_enviar:
        payload_debug = {k: v for k, v in payload.items()
                         if k not in ("captura_superior", "captura_lateral")}
        print("\n(--sin-enviar)")
        print("Payload (sin imágenes):\n{}".format(
            json.dumps(payload_debug, indent=2, ensure_ascii=False)))
    else:
        _enviar_con_reintentos(payload)

    # ── Paso 8: limpiar capturas del ciclo ────────────────────────────────────
    if not conservar_capturas:
        _limpiar_capturas(pasos, captura_ref)

    # ── Paso 9 (modo --iniciar): esperar LISTO antes del próximo ciclo ────────
    if usar_iniciar:
        print("Esperando LISTO de la ESP32 (timeout {} s)...".format(
            config.TIMEOUT_LISTO_SEG))
        if not _esperar_listo(ser, config.TIMEOUT_LISTO_SEG):
            print("[AVISO] No llegó LISTO en {} s. "
                  "El elevador puede no haber bajado. Continuando.".format(
                      config.TIMEOUT_LISTO_SEG))
        else:
            print("ESP32 lista para el próximo ciclo.")

    return True, nombre_pieza, pieza


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
    parser.add_argument(
        "--conservar-capturas", action="store_true",
        help="No borrar los JPG del ciclo después del POST (útil para depuración)",
    )
    parser.add_argument(
        "--iniciar", action="store_true",
        help="Enviar INICIAR a la ESP32 al comienzo de cada ciclo y esperar LISTO al final",
    )
    parser.add_argument(
        "--debug-serial", action="store_true",
        help="Imprimir cada línea recibida de la ESP32 con prefijo [ESP32]",
    )
    args = parser.parse_args()

    global _DEBUG_SERIAL
    _DEBUG_SERIAL = args.debug_serial

    # Garantizar que solo haya una instancia corriendo a la vez.
    # El lock se libera automáticamente cuando termina el proceso.
    _tomar_lock()

    os.makedirs(CARPETA_CAPTURAS, exist_ok=True)

    # ── Verificar calibración antes de abrir cualquier hardware ───────────────
    _verificar_calibracion()

    # ── Obtener pieza activa al arrancar ──────────────────────────────────────
    # Se actualiza en cada ciclo después de ARRIBA.
    nombre_pieza = _obtener_pieza_activa()
    pieza        = _obtener_datos_pieza(nombre_pieza)
    print("Pieza activa al arrancar: {}".format(nombre_pieza))

    # ── Abrir cámaras ─────────────────────────────────────────────────────────
    print("Configurando cámaras...")
    _configurar_v4l2(config.CAM_SUPERIOR, "superior",
                     config.FOCO_SUPERIOR, config.EXPOSICION_SUPERIOR, config.GANANCIA_SUPERIOR)
    _configurar_v4l2(config.CAM_LATERAL,  "lateral",
                     config.FOCO_LATERAL,  config.EXPOSICION_LATERAL,  config.GANANCIA_LATERAL)

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
            _, nombre_pieza, pieza = _ejecutar_ciclo(
                ser, cam_sup, cam_lat, procesador,
                nombre_pieza, pieza,
                args.pasos, args.sin_enviar, args.conservar_capturas,
                usar_iniciar=args.iniciar,
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
