# Control del servo del plato giratorio — DIMENSIA
# Servo MG996R de rotación continua (360°, modificado sin potenciómetro).
# A diferencia de un servo posicional, este NO tiene feedback de posición:
# se controla por velocidad y tiempo, no por ángulo directo.
# El servo se alimenta desde una fuente aparte a través de un TIP142, que se
# enciende con el pin PIN_SERVO_ALIM (resistencia de 330 ohm a la base).
# MicroPython

from machine import Pin, PWM
from time import sleep_ms
from pines import PIN_SERVO_PLATO, PIN_SERVO_ALIM

# --- Frecuencia PWM ----------------------------------------------------------

FRECUENCIA_PWM = 50   # 50 Hz estándar para servos RC (periodo 20 ms)

# --- Pulsos en microsegundos -------------------------------------------------

PULSO_NEUTRO_US = 1500
# Servo quieto (punto muerto). Medido: 1,5 ms, no deriva en neutro.

PULSO_HORARIO_US = 1300
# Gira en sentido horario mirando el plato desde arriba.
# Si resulta antihorario, intercambiar PULSO_HORARIO_US y PULSO_ANTIHORARIO_US.

PULSO_ANTIHORARIO_US = 1700
# Simétrico respecto del neutro (1500 + 200 us).

TIEMPO_PASO_45_MS = 1038
# Tiempo para avanzar 45° (un octavo de vuelta). Calibrado el 5/11 con el
# servo en la placa y 6 V (no mover la fuente): la vuelta de 8 pasos cierra con menos de 5° de desvío.
# Si cambia la fuente o la carga, REPETIR la calibración.


def _aplicar_pulso(pwm, pulso_us):
    """
    Aplica un pulso en us al objeto PWM.
    duty_ns() está disponible desde MicroPython 1.20 en ESP32.
    """
    pwm.duty_ns(pulso_us * 1000)


class ServoPlato:
    """
    Controla el servo de rotación continua que gira el plato de la estación.
    No hay control directo de ángulo: se gira durante un tiempo determinado
    y se confía en la consistencia mecánica para llegar a la posición deseada.
    """

    def __init__(self):
        # Primero la señal en neutro, DESPUÉS la alimentación: si el servo se
        # enciende con la señal flotando o en 0, gira solo un instante.
        self._pwm = PWM(Pin(PIN_SERVO_PLATO), freq=FRECUENCIA_PWM)
        self.detener()
        sleep_ms(50)
        # Alimentar el servo a través del TIP142
        self._alim = Pin(PIN_SERVO_ALIM, Pin.OUT)
        self._alim.value(1)
        sleep_ms(300)
        # Dejar el servo detenido para no mover el plato
        self.detener()

    def detener(self):
        """Pone el servo en punto neutro (sin movimiento)."""
        _aplicar_pulso(self._pwm, PULSO_NEUTRO_US)

    def girar_tiempo(self, direccion="horario", tiempo_ms=500):
        """
        Gira el plato en la dirección indicada durante tiempo_ms milisegundos,
        luego lo detiene. Se llama una vez por ángulo (0°, 45°, 90°... 315°).
        """
        if direccion == "horario":
            _aplicar_pulso(self._pwm, PULSO_HORARIO_US)
        else:
            _aplicar_pulso(self._pwm, PULSO_ANTIHORARIO_US)

        sleep_ms(tiempo_ms)
        self.detener()

    def girar_paso(self, direccion="horario"):
        """
        Gira el plato un paso de 45° usando TIEMPO_PASO_45_MS.
        Es el método que usa el ciclo de inspección en condiciones normales.
        """
        self.girar_tiempo(direccion=direccion, tiempo_ms=TIEMPO_PASO_45_MS)

    def calibrar_paso(self, tiempo_ms):
        """
        Herramienta de calibración manual: gira horario durante tiempo_ms
        y se detiene. Se usa para ajustar TIEMPO_PASO_45_MS.
        """
        self.girar_tiempo(direccion="horario", tiempo_ms=tiempo_ms)