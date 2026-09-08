# Control del servo de la paleta basculante — DIMENSIA
# Servo SG90 posicional que inclina la plataforma en "Y" para dirigir
# la pieza hacia la rama correcta: aprobadas o rechazadas.
# Se mueve UNA VEZ por inspección, antes de que servo_brazo.py empuje la pieza.
# Secuencia correcta: posicionar paleta → empujar pieza.
# MicroPython

from machine import Pin, PWM

# ─── Pines y frecuencia ───────────────────────────────────────────────────────

PIN_SERVO_PALETA = 17   # ajustar según el cableado real
FRECUENCIA_PWM   = 50   # 50 Hz estándar para servos RC

# ─── Ángulos de operación ─────────────────────────────────────────────────────

ANGULO_APROBADA  = 45    # paleta inclinada hacia la rama de piezas aprobadas
ANGULO_RECHAZADA = 135   # paleta inclinada hacia la rama de piezas rechazadas


def _angulo_a_duty(angulo):
    """
    Convierte un ángulo (0–180°) al duty cycle correspondiente.
    Misma fórmula que servo_brazo.py — duplicada aquí porque en MicroPython
    no es práctico compartir un módulo común entre archivos tan chicos.
    Rango 40–115 en escala 0–1023 para PWM de 50 Hz.
    """
    duty_min = 40
    duty_max = 115
    return int(duty_min + (duty_max - duty_min) * angulo / 180)


class ServoPaleta:
    """
    Controla la paleta que dirige la pieza a la rama correcta de la rampa en Y.
    Se llama antes del empuje: primero posicionar(), luego servo_brazo.empujar().
    """

    def __init__(self):
        self._pwm = PWM(Pin(PIN_SERVO_PALETA), freq=FRECUENCIA_PWM)
        # Arrancar en la posición de aprobadas como posición neutra de seguridad
        self._pwm.duty(_angulo_a_duty(ANGULO_APROBADA))

    def posicionar(self, resultado):
        """
        Inclina la paleta según el resultado de la inspección.
        Debe llamarse ANTES de que servo_brazo.empujar() suelte la pieza.
        Lanza ValueError si el resultado no es "APROBADA" ni "RECHAZADA".
        """
        if resultado == "APROBADA":
            self._pwm.duty(_angulo_a_duty(ANGULO_APROBADA))
        elif resultado == "RECHAZADA":
            self._pwm.duty(_angulo_a_duty(ANGULO_RECHAZADA))
        else:
            raise ValueError(
                "Resultado desconocido: '{}'. Usar 'APROBADA' o 'RECHAZADA'.".format(resultado)
            )
