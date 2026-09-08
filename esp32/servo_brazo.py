# Control del servo del brazo empujador — DIMENSIA
# Servo MG996R de 180° posicional (estándar, con feedback de ángulo interno).
# A diferencia del servo_plato.py (rotación continua sin posición), este servo
# SÍ tiene control de ángulo directo: se le indica un ángulo y el servo
# se mueve hasta él y lo mantiene por sí solo.
# El brazo empuja la pieza fuera del plato después de que fue clasificada.
# MicroPython

from machine import Pin, PWM
from time import sleep_ms

# ─── Pines y frecuencia ───────────────────────────────────────────────────────

PIN_SERVO_BRAZO = 16   # ajustar según el cableado real
FRECUENCIA_PWM  = 50   # 50 Hz estándar para servos RC

# ─── Ángulos de operación ─────────────────────────────────────────────────────

ANGULO_REPOSO = 0    # brazo retraído, posición de espera entre inspecciones
ANGULO_EMPUJE = 90   # brazo extendido, empuja la pieza fuera del plato


def _angulo_a_duty(angulo):
    """
    Convierte un ángulo (0–180°) al duty cycle correspondiente.
    Para PWM de 50 Hz en MicroPython (escala 0–1023):
      0°   → duty ~40  (~0.5ms de pulso)
      180° → duty ~115 (~2.5ms de pulso)
    La interpolación lineal entre esos extremos da la posición intermedia.
    Los valores 40 y 115 son típicos para servo estándar; ajustar si el
    servo no llega a los extremos o si los supera y vibra.
    """
    duty_min = 40
    duty_max = 115
    return int(duty_min + (duty_max - duty_min) * angulo / 180)


class ServoBrazo:
    """
    Controla el servo posicional del brazo empujador.
    Permite mover el brazo a cualquier ángulo entre 0° y 180°.
    El flujo normal de uso es: esperar en reposo → empujar() → volver a reposo.
    """

    def __init__(self):
        # Inicializar el PWM en el pin del servo
        self._pwm = PWM(Pin(PIN_SERVO_BRAZO), freq=FRECUENCIA_PWM)
        # Arrancar siempre con el brazo retraído para no interferir con el plato
        self.mover_a(ANGULO_REPOSO)

    def mover_a(self, angulo):
        """
        Mueve el servo al ángulo indicado (0–180°).
        Lanza ValueError si el ángulo está fuera del rango válido.
        """
        if not (0 <= angulo <= 180):
            raise ValueError("Ángulo fuera de rango: {} (debe ser 0–180)".format(angulo))
        self._pwm.duty(_angulo_a_duty(angulo))

    def empujar(self, tiempo_ms=800):
        """
        Extiende el brazo para sacar la pieza del plato y lo retrae al terminar.
        Se llama una vez por ciclo de inspección, después de que la Raspberry Pi
        decide si la pieza es APROBADA o RECHAZADA.
        El tiempo_ms da al brazo margen para que la pieza caiga antes de retraerse.
        """
        self.mover_a(ANGULO_EMPUJE)
        sleep_ms(tiempo_ms)
        self.mover_a(ANGULO_REPOSO)

    def reposo(self):
        """Mueve el servo directamente a la posición de espera."""
        self.mover_a(ANGULO_REPOSO)
