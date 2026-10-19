# Control del servo del plato giratorio — DIMENSIA
# Servo MG996R de rotación continua (360°, modificado sin potenciómetro).
# A diferencia de un servo posicional, este NO tiene feedback de posición:
# se controla por velocidad y tiempo, no por ángulo directo.
# MicroPython

from machine import Pin, PWM
from time import sleep_ms
from pines import PIN_SERVO_PLATO

# ─── Frecuencia PWM ───────────────────────────────────────────────────────────

FRECUENCIA_PWM = 50   # 50 Hz estándar para servos RC (periodo 20 ms)

# ─── Pulsos en microsegundos — medidos con el servo real a 6 V sin carga ──────

PULSO_NEUTRO_US = 1500
# Servo quieto (punto muerto). Medido: 1,5 ms → neutro real.

PULSO_HORARIO_US = 1400
# PROVISIONAL: falta confirmar con el servo montado que 1400 µs gira en sentido
# horario mirando el plato desde arriba. Si resulta antihorario, intercambiar
# PULSO_HORARIO_US y PULSO_ANTIHORARIO_US.

PULSO_ANTIHORARIO_US = 1600
# Simétrico respecto del neutro (1500 + 100 µs). NO fue medido directamente.

TIEMPO_PASO_45_MS = 2300
# Tiempo para avanzar 45° (un octavo de vuelta). Medido sin carga a 6 V.
# REPETIR la medición con el plato y la pieza montados y el servo alimentado
# por el buck de 6 V: la carga puede aumentar este valor.


def _aplicar_pulso(pwm, pulso_us):
    """
    Aplica un pulso en µs al objeto PWM.
    duty_ns() está disponible desde MicroPython 1.20 en ESP32.
    Si la build no lo soporta, descomentar la línea con duty_u16.
    """
    pwm.duty_ns(pulso_us * 1000)
    # Alternativa si duty_ns no está disponible:
    # pwm.duty_u16(int(pulso_us / 20000 * 65535))


class ServoPlato:
    """
    Controla el servo de rotación continua que gira el plato de la estación.
    No hay control directo de ángulo: se gira durante un tiempo determinado
    y se confía en la consistencia mecánica para llegar a la posición deseada.
    """

    def __init__(self):
        # Inicializar el PWM en el pin del servo
        self._pwm = PWM(Pin(PIN_SERVO_PLATO), freq=FRECUENCIA_PWM)
        # Siempre arrancar con el servo detenido para no mover el plato
        self.detener()

    def detener(self):
        """Pone el servo en punto neutro (sin movimiento)."""
        _aplicar_pulso(self._pwm, PULSO_NEUTRO_US)

    def girar_tiempo(self, direccion="horario", tiempo_ms=500):
        """
        Gira el plato en la dirección indicada durante tiempo_ms milisegundos,
        luego lo detiene. Es el método principal del ciclo de inspección:
        se llama una vez por ángulo (0°, 45°, 90°... hasta 315°).
        """
        if direccion == "horario":
            _aplicar_pulso(self._pwm, PULSO_HORARIO_US)
        else:
            _aplicar_pulso(self._pwm, PULSO_ANTIHORARIO_US)

        sleep_ms(tiempo_ms)
        self.detener()

    def girar_paso(self, direccion="horario"):
        """
        Gira el plato exactamente un paso de 45° usando TIEMPO_PASO_45_MS.
        Es el método que usa el ciclo de inspección en condiciones normales:
        llama a girar_tiempo() con el tiempo medido en calibración.
        """
        self.girar_tiempo(direccion=direccion, tiempo_ms=TIEMPO_PASO_45_MS)

    def calibrar_paso(self, tiempo_ms):
        """
        Herramienta de calibración manual: gira horario durante tiempo_ms
        y se detiene. Llamar repetidamente ajustando tiempo_ms hasta que
        el plato avance exactamente 45° cada vez.
        El valor correcto se actualiza en TIEMPO_PASO_45_MS.
        """
        self.girar_tiempo(direccion="horario", tiempo_ms=tiempo_ms)
