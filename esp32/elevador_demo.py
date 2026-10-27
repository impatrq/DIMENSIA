# Control del elevador para la demo autónoma — DIMENSIA
# Motor paso a paso NEMA23 con driver tipo TB6600 en 1/16 de micropaso
# (3200 pulsos por vuelta). STEP se genera con machine.PWM (duty 50 %) en vez
# de bit-banging, con una rampa lineal de frecuencia al arrancar.
# ENA no está conectada: el driver queda siempre habilitado y el motor mantiene
# el torque al terminar. Por eso este módulo NO usa PIN_ENABLE.
# Finales de carrera: microswitch con COM a GND y NO al pin, con PULL_UP,
# activos en 0.
# MicroPython

from machine import Pin, PWM
import time
from pines import (PIN_STEP, PIN_DIR,
                   PIN_FIN_CARRERA_ARRIBA, PIN_FIN_CARRERA_ABAJO)

try:
    from pines import SENTIDO_SUBIR
except ImportError:
    # PROVISORIA: valor de DIR que hace subir el carro. Hay que confirmarlo
    # con el husillo montado: si subir() hace bajar el carro, cambiar a 0.
    # Una vez confirmado, moverlo a pines.py.
    SENTIDO_SUBIR = 1

# ─── Configuración ────────────────────────────────────────────────────────────

PULSOS_POR_VUELTA = 3200   # 1/16 de micropaso (solo informativo)
F_INICIAL = 500            # Hz, frecuencia de arranque
F_MAX = 1500               # Hz, valor por defecto para las primeras pruebas con carga
F_LIMITE = 3000            # Hz, tope de seguridad para f_max (rampa probada sin carga hasta 3000 Hz)
T_RAMPA_MS = 2000          # ms para ir de F_INICIAL a f_max
PERIODO_LECTURA_MS = 5     # cada cuánto se revisa el final de carrera
PERIODO_RAMPA_MS = 50      # cada cuánto se actualiza la frecuencia de la rampa
ESPERA_DIR_MS = 5          # espera entre setear DIR y el primer pulso
TIMEOUT_MS = 60000         # timeout por tiempo, por defecto
DUTY_50 = 32768            # duty_u16 al 50 %


class ElevadorDemo:
    """
    Sube y baja el carro hasta los finales de carrera usando PWM en STEP.
    El PWM se crea solo durante cada movimiento y se libera en parar(),
    así no queda ocupando un canal/timer LEDC mientras se usa el servo.
    """

    def __init__(self):
        self._dir = Pin(PIN_DIR, Pin.OUT)
        self._fc_arriba = Pin(PIN_FIN_CARRERA_ARRIBA, Pin.IN, Pin.PULL_UP)
        self._fc_abajo  = Pin(PIN_FIN_CARRERA_ABAJO,  Pin.IN, Pin.PULL_UP)
        self._pwm = None

    def _confirmado(self, fc):
        """Dos lecturas seguidas en 0, separadas PERIODO_LECTURA_MS."""
        if fc.value() != 0:
            return False
        time.sleep_ms(PERIODO_LECTURA_MS)
        return fc.value() == 0

    def _mover(self, sentido, fc, f_max, timeout_ms):
        """
        Mueve el carro en el sentido indicado hasta que fc se active
        (True) o venza timeout_ms (False). Siempre termina en parar().
        """
        if not 0 < f_max <= F_LIMITE:
            raise ValueError("f_max fuera de rango: {}".format(f_max))

        # Si ya está en el final de carrera, no mover
        if self._confirmado(fc):
            return True

        try:
            self._pwm = PWM(Pin(PIN_STEP), freq=F_INICIAL, duty_u16=0)
            self._dir.value(sentido)
            time.sleep_ms(ESPERA_DIR_MS)

            t0 = time.ticks_ms()
            f_actual = F_INICIAL
            t_ultima_rampa = 0     # ms desde t0 de la última actualización de freq
            lecturas_en_0 = 0
            self._pwm.duty_u16(DUTY_50)

            while True:
                # Final de carrera: dos lecturas seguidas en 0
                if fc.value() == 0:
                    lecturas_en_0 += 1
                    if lecturas_en_0 >= 2:
                        self._pwm.duty_u16(0)
                        return True
                else:
                    lecturas_en_0 = 0

                t = time.ticks_diff(time.ticks_ms(), t0)
                if t >= timeout_ms:
                    self._pwm.duty_u16(0)
                    return False

                # Rampa lineal de F_INICIAL a f_max en T_RAMPA_MS,
                # actualizada cada PERIODO_RAMPA_MS
                if t - t_ultima_rampa >= PERIODO_RAMPA_MS:
                    t_ultima_rampa = t
                    if t < T_RAMPA_MS:
                        f = int(F_INICIAL + (f_max - F_INICIAL) * t / T_RAMPA_MS)
                    else:
                        f = int(f_max)
                    if f != f_actual:
                        self._pwm.freq(f)
                        f_actual = f

                time.sleep_ms(PERIODO_LECTURA_MS)
        finally:
            # También corre ante una excepción o KeyboardInterrupt
            self.parar()

    def subir(self, f_max=F_MAX, timeout_ms=TIMEOUT_MS):
        """Sube hasta el final de carrera superior. True si llegó, False si timeout."""
        return self._mover(SENTIDO_SUBIR, self._fc_arriba, f_max, timeout_ms)

    def bajar(self, f_max=F_MAX, timeout_ms=TIMEOUT_MS):
        """Baja hasta el final de carrera inferior. True si llegó, False si timeout."""
        # Sentido contrario a SENTIDO_SUBIR (asume valores 0/1)
        return self._mover(1 - SENTIDO_SUBIR, self._fc_abajo, f_max, timeout_ms)

    def parar(self):
        """
        Corta los pulsos y libera el PWM de STEP. El driver sigue habilitado
        (ENA sin conectar), así que el motor mantiene el torque.
        """
        if self._pwm is not None:
            self._pwm.duty_u16(0)
            self._pwm.deinit()
            self._pwm = None

    def esta_arriba(self):
        """True si el final de carrera superior está activo."""
        return self._fc_arriba.value() == 0

    def esta_abajo(self):
        """True si el final de carrera inferior está activo."""
        return self._fc_abajo.value() == 0
