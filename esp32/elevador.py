# Control del elevador — DIMENSIA
# Motor paso a paso NEMA17 con driver A4988/DRV8825.
# El carro sube y baja por un husillo T8 guiado por 2 varillas laterales.
# Dos finales de carrera limitan el recorrido: uno arriba y uno abajo.
# MicroPython

from machine import Pin
from time import sleep_ms, sleep_us

# ─── Pines (ajustar con el hardware real) ─────────────────────────────────────

PIN_STEP                 = 14   # pulso de paso al driver
PIN_DIR                  = 12   # dirección: HIGH = subir, LOW = bajar
PIN_ENABLE               = 13   # habilitación del driver: LOW = activo, HIGH = apagado
PIN_FIN_CARRERA_ARRIBA   = 32   # final de carrera límite superior
PIN_FIN_CARRERA_ABAJO    = 33   # final de carrera límite inferior

PASOS_POR_VUELTA = 200          # NEMA17 estándar: 1.8° por paso


class Elevador:
    """
    Controla el motor paso a paso del elevador.
    El driver se mantiene deshabilitado (enable=HIGH) cuando no hay movimiento
    para reducir el calentamiento de la bobina.
    """

    def __init__(self):
        # Pines de control del driver
        self._step   = Pin(PIN_STEP,   Pin.OUT, value=0)
        self._dir    = Pin(PIN_DIR,    Pin.OUT, value=0)
        self._enable = Pin(PIN_ENABLE, Pin.OUT, value=1)  # HIGH = deshabilitado

        # Finales de carrera con pull-up interno.
        # Con PULL_UP el pin lee HIGH en reposo y cae a LOW cuando se presiona
        # el final de carrera, sin necesidad de resistencia externa.
        self._fc_arriba = Pin(PIN_FIN_CARRERA_ARRIBA, Pin.IN, Pin.PULL_UP)
        self._fc_abajo  = Pin(PIN_FIN_CARRERA_ABAJO,  Pin.IN, Pin.PULL_UP)

    def _dar_paso(self, retardo_us=800):
        """
        Genera un pulso en el pin STEP.
        El driver interpreta cada flanco ascendente como un paso del motor.
        El retardo_us controla la velocidad: más bajo = más rápido, pero
        valores muy bajos pueden hacer que el motor pierda pasos.
        """
        self._step.value(1)
        sleep_us(retardo_us)
        self._step.value(0)
        sleep_us(retardo_us)

    def subir(self, timeout_ms=15000):
        """
        Mueve el carro hacia arriba hasta que el final de carrera superior
        se active o se cumpla el timeout.
        El final de carrera activo se lee como LOW (pull-up + contacto a GND).
        Devuelve True si llegó arriba, False si hizo timeout sin llegar.
        """
        self._enable.value(0)   # habilitar driver
        self._dir.value(1)      # dirección: subir

        pasos_max = (timeout_ms // 2)  # estimación conservadora de pasos en el tiempo límite
        for _ in range(pasos_max):
            if self._fc_arriba.value() == 0:  # final de carrera presionado (LOW activo)
                break
            self._dar_paso()
        else:
            # El loop terminó sin que el final de carrera se activara
            self._enable.value(1)
            return False

        self._enable.value(1)   # deshabilitar driver
        return True

    def bajar(self, timeout_ms=15000):
        """
        Mueve el carro hacia abajo hasta que el final de carrera inferior
        se active o se cumpla el timeout.
        Misma lógica que subir() pero con dirección invertida y verificando
        el final de carrera de abajo.
        Devuelve True si llegó abajo, False si hizo timeout sin llegar.
        """
        self._enable.value(0)   # habilitar driver
        self._dir.value(0)      # dirección: bajar

        pasos_max = (timeout_ms // 2)
        for _ in range(pasos_max):
            if self._fc_abajo.value() == 0:   # final de carrera presionado (LOW activo)
                break
            self._dar_paso()
        else:
            self._enable.value(1)
            return False

        self._enable.value(1)   # deshabilitar driver
        return True

    def esta_arriba(self):
        """
        Devuelve True si el final de carrera superior está activo (carro en límite superior).
        Con pull-up, el pin vale 0 cuando el final de carrera cierra el circuito.
        """
        return self._fc_arriba.value() == 0

    def esta_abajo(self):
        """
        Devuelve True si el final de carrera inferior está activo (carro en límite inferior).
        """
        return self._fc_abajo.value() == 0
