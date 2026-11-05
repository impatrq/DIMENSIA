# main.py — arranque automático de la ESP32 — DIMENSIA
# Corre solo al encender la ESP32. Espera órdenes por el USB (serial) y/o el
# botón de PIN_BOTON, y ejecuta el ciclo: subir, 8 paradas del plato, bajar.
#
# Protocolo (una línea por mensaje, terminada en \n, a 115200 baud):
#   ESP32 -> RPi:  LISTO            (arrancó o terminó un ciclo, espera orden)
#                  ARRIBA           (el carro llegó arriba; se repite cada 2 s
#                                    hasta que llega el primer PASO)
#                  PASO_OK          (el plato giró 45° y se asentó)
#                  ABAJO            (el carro llegó abajo; ciclo terminado)
#                  ERROR <motivo>   (SUBIR, BAJAR, TIMEOUT_RPI, PASOS_EXCEDIDOS)
#                  PARADO           (se recibió PARAR y no se estaba moviendo)
#                  PONG / ESTADO ...(respuestas a PING / ESTADO)
#                  Las líneas que empiezan con # son comentarios: ignorarlas.
#   RPi -> ESP32:  INICIAR          (arranca un ciclo, igual que el botón)
#                  PASO             (gira un paso; responde PASO_OK) x8
#                  FIN APROBADA / FIN RECHAZADA (terminó de medir: baja el carro)
#                  PARAR            (corta el plato y deja el carro donde está)
#                  PING, ESTADO
#
# Limitación: mientras el carro se mueve (subir/bajar, hasta TIMEOUT_MS) la
# ESP32 no lee el serial. Para parar en ese momento: cortar los 12 V del driver
# (o sacar el fusible) o Ctrl+C. PARAR funciona entre pasos del plato.
# Para volver al REPL y editar archivos: Ctrl+C (mpremote lo hace solo).
# MicroPython

import sys
import time
import select
from machine import Pin
import pines
from elevador_demo import ElevadorDemo, TIMEOUT_MS, F_MAX
from servo_plato import ServoPlato

# ─── Configuración ────────────────────────────────────────────────────────────

PARADAS = 8
ASENTAMIENTO_MS = 1000     # espera después de cada paso del plato (antes de PASO_OK)
ESPERA_ARRIBA_MS = 1000    # pausa al llegar arriba, antes de avisar ARRIBA
ESPERA_CMD_MS = 30000      # si la RPi no manda nada en este tiempo (entre PASO y FIN): ERROR y baja
ESPERA_PRIMER_PASO_MS = 60000  # idem, esperando el primer PASO
REPETIR_ARRIBA_MS = 2000   # ARRIBA se repite cada tanto hasta que llega el primer PASO
ANTIRREBOTE_MS = 50

_poll = select.poll()
_poll.register(sys.stdin, select.POLLIN)
_elev = ElevadorDemo()
_boton = Pin(pines.PIN_BOTON, Pin.IN, Pin.PULL_UP)


def enviar(mensaje):
    print(mensaje)


def leer_linea(timeout_ms=0):
    """Devuelve la línea recibida en mayúsculas, o None si no llegó nada."""
    if _poll.poll(timeout_ms):
        linea = sys.stdin.readline()
        # Descartar caracteres raros (basura al abrir el puerto, \r, etc.)
        linea = "".join(c for c in linea if " " <= c <= "~").strip().upper()
        if linea:
            return linea
    return None


def apagar_servo():
    """Corta la alimentación del servo (base del TIP142 en 0)."""
    Pin(pines.PIN_SERVO_ALIM, Pin.OUT, value=0)


def liberar_plato(plato):
    plato.detener()
    apagar_servo()                       # primero cortar la alimentación del servo
    plato._pwm.deinit()
    Pin(pines.PIN_SERVO_PLATO, Pin.OUT, value=0)   # señal en 0, no flotante


def boton_apretado():
    if _boton.value() != 0:
        return False
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ANTIRREBOTE_MS:
        if _boton.value() != 0:
            return False
        time.sleep_ms(1)
    while _boton.value() == 0:      # esperar a que suelte
        time.sleep_ms(10)
    return True


def ciclo():
    plato = None
    try:
        if not _elev.subir(f_max=F_MAX, timeout_ms=TIMEOUT_MS):
            enviar("ERROR SUBIR")
            return
        time.sleep_ms(ESPERA_ARRIBA_MS)
        enviar("ARRIBA")

        plato = ServoPlato()
        pasos = 0
        t_espera = time.ticks_ms()
        t_arriba = t_espera
        while True:
            cmd = leer_linea(200)
            ahora = time.ticks_ms()
            if cmd is None:
                if pasos == 0 and time.ticks_diff(ahora, t_arriba) >= REPETIR_ARRIBA_MS:
                    enviar("ARRIBA")
                    t_arriba = ahora
                limite = ESPERA_PRIMER_PASO_MS if pasos == 0 else ESPERA_CMD_MS
                if time.ticks_diff(ahora, t_espera) >= limite:
                    enviar("ERROR TIMEOUT_RPI")
                    break
                continue
            t_espera = ahora
            if cmd == "PASO":
                if pasos >= PARADAS:
                    enviar("ERROR PASOS_EXCEDIDOS")
                    continue
                plato.girar_paso("horario")
                time.sleep_ms(ASENTAMIENTO_MS)
                pasos += 1
                enviar("PASO_OK")
            elif cmd.startswith("FIN"):
                enviar("# " + cmd)
                break
            elif cmd == "PARAR":
                liberar_plato(plato)
                plato = None
                enviar("PARADO")
                return          # el carro queda arriba
            elif cmd == "PING":
                enviar("PONG")
            else:
                enviar("# COMANDO_DESCONOCIDO " + cmd)

        liberar_plato(plato)
        plato = None
        time.sleep_ms(1000)
        if _elev.bajar(f_max=F_MAX, timeout_ms=TIMEOUT_MS):
            enviar("ABAJO")
        else:
            enviar("ERROR BAJAR")
    finally:
        if plato is not None:
            liberar_plato(plato)
        _elev.parar()


def main():
    apagar_servo()
    enviar("LISTO")
    while True:
        cmd = leer_linea(20)
        if cmd == "INICIAR" or boton_apretado():
            ciclo()
            enviar("LISTO")
        elif cmd == "PING":
            enviar("PONG")
        elif cmd == "ESTADO":
            enviar("ESTADO arriba={} abajo={} puerta_cerrada={}".format(
                int(_elev.esta_arriba()), int(_elev.esta_abajo()),
                int(_elev.puerta_cerrada())))
        elif cmd == "PARAR":
            enviar("PARADO")
        elif cmd is not None:
            enviar("# COMANDO_DESCONOCIDO " + cmd)


try:
    main()
except KeyboardInterrupt:
    _elev.parar()
    apagar_servo()
    print("# main.py detenido (Ctrl+C)")
