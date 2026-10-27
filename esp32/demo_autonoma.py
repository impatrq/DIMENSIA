# Demo autónoma del ciclo — DIMENSIA
# Ciclo completo sin la Raspberry: subir, 8 paradas de 45° del plato, bajar.
# Uso desde el REPL:
#   import demo_autonoma
#   demo_autonoma.ciclo()           # un ciclo a mano (sirve sin botón cableado)
#   demo_autonoma.esperar_boton()   # un ciclo por cada pulsación de PIN_BOTON
# MicroPython

from machine import Pin
import time
from pines import PIN_BOTON
from elevador_demo import ElevadorDemo, TIMEOUT_MS, F_MAX
from servo_plato import ServoPlato

# ─── Configuración ────────────────────────────────────────────────────────────

PARADAS = 8
ESPERA_MS = 1000           # pausa entre etapas del ciclo
ASENTAMIENTO_MS = 1000     # espera después de cada girar_paso()
ANTIRREBOTE_MS = 50        # el botón tiene que mantenerse estable este tiempo
PERIODO_BOTON_MS = 10      # cada cuánto se lee el botón mientras se espera


def _estado(elevador, mensaje):
    """Imprime el paso actual junto con el estado de los finales de carrera."""
    print("[{} ms] {} | arriba: {} | abajo: {}".format(
        time.ticks_ms(), mensaje, elevador.esta_arriba(), elevador.esta_abajo()))


def _liberar_plato(plato):
    """
    Detiene el servo y libera su PWM de 50 Hz antes de volver a usar el de STEP.
    ServoPlato no tiene un método público para esto, así que se usa _pwm.
    """
    plato.detener()
    plato._pwm.deinit()


def ciclo(timeout_ms=TIMEOUT_MS, f_max=F_MAX):
    """
    Ejecuta un ciclo completo. Devuelve True si no hubo errores.
    Para las primeras pruebas con carga usar timeout_ms=10000:
        ciclo(timeout_ms=10000)
    """
    elevador = ElevadorDemo()
    plato = None
    try:
        _estado(elevador, "inicio del ciclo")

        _estado(elevador, "subiendo")
        if not elevador.subir(f_max=f_max, timeout_ms=timeout_ms):
            _estado(elevador, "ERROR: el elevador no llego arriba (timeout)")
            return False
        _estado(elevador, "arriba")
        time.sleep_ms(ESPERA_MS)

        # El PWM del servo se crea recién acá: el de STEP ya fue liberado
        plato = ServoPlato()
        for n in range(1, PARADAS + 1):
            plato.girar_paso("horario")
            time.sleep_ms(ASENTAMIENTO_MS)
            _estado(elevador, "parada {} de {}".format(n, PARADAS))
        _liberar_plato(plato)
        plato = None
        time.sleep_ms(ESPERA_MS)

        _estado(elevador, "bajando")
        if not elevador.bajar(f_max=f_max, timeout_ms=timeout_ms):
            _estado(elevador, "ERROR: el elevador no llego abajo (timeout)")
            return False
        _estado(elevador, "ciclo completo")
        return True
    finally:
        # Si se interrumpe a mitad de un giro, el servo de rotación continua
        # seguiría girando: detenerlo y liberar su PWM.
        # El elevador ya se para solo en el finally de subir()/bajar().
        if plato is not None:
            _liberar_plato(plato)


def _estable(pin, valor):
    """True si el pin se mantiene en valor durante ANTIRREBOTE_MS."""
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ANTIRREBOTE_MS:
        if pin.value() != valor:
            return False
        time.sleep_ms(1)
    return True


def esperar_boton():
    """
    Espera un flanco de bajada en PIN_BOTON (PULL_UP, activo en 0) con
    antirrebote y corre ciclo(). Repite hasta Ctrl+C.
    """
    boton = Pin(PIN_BOTON, Pin.IN, Pin.PULL_UP)
    while True:
        print("Esperando boton en GPIO {} (Ctrl+C para salir)".format(PIN_BOTON))
        # Primero el botón suelto, así un botón mantenido no dispara otro ciclo
        while not _estable(boton, 1):
            time.sleep_ms(PERIODO_BOTON_MS)
        while not _estable(boton, 0):
            time.sleep_ms(PERIODO_BOTON_MS)
        print("Boton presionado")
        ciclo()


if __name__ == "__main__":
    esperar_boton()
