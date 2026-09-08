# Control del servo del plato giratorio — DIMENSIA
# Servo MG996R de rotación continua (360°, modificado sin potenciómetro).
# A diferencia de un servo posicional, este NO tiene feedback de posición:
# se controla por velocidad y tiempo, no por ángulo directo.
# Para girar 45°, se aplica el duty de giro durante una cantidad de ms
# que se determina a prueba y error con el hardware real.
# MicroPython

from machine import Pin, PWM
from time import sleep_ms

# ─── Pines y frecuencia ───────────────────────────────────────────────────────

PIN_SERVO_PLATO = 15   # ajustar según el cableado real
FRECUENCIA_PWM  = 50   # 50 Hz estándar para servos RC

# ─── Duty cycle de referencia ─────────────────────────────────────────────────
# Los duty cycles se expresan en la escala de MicroPython: 0–1023.
# Relación aproximada con el ancho de pulso:
#   DUTY_DETENIDO      ~77  → ~1.5ms → servo quieto (punto neutro)
#   DUTY_GIRO_HORARIO  ~60  → pulso más corto → gira horario
#   DUTY_ANTIHORARIO   ~90  → pulso más largo → gira antihorario
#
# IMPORTANTE: estos valores son de referencia. Cada servo tiene su
# punto neutro ligeramente distinto. Ajustarlos con la función
# calibrar_paso() una vez que el hardware esté armado.

DUTY_DETENIDO        = 77
DUTY_GIRO_HORARIO    = 60
DUTY_GIRO_ANTIHORARIO = 90


class ServoPlato:
    """
    Controla el servo de rotación continua que gira el plato de la estación.
    No hay control directo de ángulo: se gira durante un tiempo determinado
    y se confía en la consistencia mecánica para llegar a la posición deseada.
    Para el ciclo de inspección, girar_tiempo() se llama 8 veces con el
    tiempo calibrado para avanzar 45° cada vez.
    """

    def __init__(self):
        # Inicializar el PWM en el pin del servo
        self._pwm = PWM(Pin(PIN_SERVO_PLATO), freq=FRECUENCIA_PWM)
        # Siempre arrancar con el servo detenido para no mover el plato
        self.detener()

    def detener(self):
        """Pone el servo en punto neutro (sin movimiento)."""
        self._pwm.duty(DUTY_DETENIDO)

    def girar_tiempo(self, direccion="horario", tiempo_ms=500):
        """
        Gira el plato en la dirección indicada durante tiempo_ms milisegundos,
        luego lo detiene. Es el método principal del ciclo de inspección:
        se llama una vez por ángulo (0°, 45°, 90°... hasta 315°).
        El tiempo_ms que equivale a un avance de 45° se determina con
        calibrar_paso() y depende de la velocidad real del servo.
        """
        if direccion == "horario":
            self._pwm.duty(DUTY_GIRO_HORARIO)
        else:
            self._pwm.duty(DUTY_GIRO_ANTIHORARIO)

        sleep_ms(tiempo_ms)
        self.detener()

    def calibrar_paso(self, tiempo_ms):
        """
        Herramienta de calibración manual: gira horario durante tiempo_ms
        y se detiene. Llamar repetidamente ajustando tiempo_ms hasta que
        el plato avance exactamente 45° cada vez.
        El valor correcto se usa como argumento en girar_tiempo() en main.py.
        """
        self.girar_tiempo(direccion="horario", tiempo_ms=tiempo_ms)
