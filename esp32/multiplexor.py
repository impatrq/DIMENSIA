# Driver MicroPython para el multiplexor I2C TCA9548A
# Permite usar hasta 8 dispositivos con la misma dirección en el mismo bus
# Nosotros usamos los canales 0 al 3 para los 4 sensores VL53L4CD

_DIRECCION_I2C = 0x70  # Dirección I2C del TCA9548A (pines A0-A2 en GND)


class Multiplexor:
    """Driver para el TCA9548A. Selecciona qué canal I2C está activo."""

    def __init__(self, i2c):
        self.i2c = i2c

    def seleccionar_canal(self, canal):
        """
        Activa un canal (0-3) y desactiva todos los demás.
        El TCA9548A usa un byte de máscara: bit N=1 activa el canal N.
        """
        if canal < 0 or canal > 7:
            raise ValueError("Canal inválido: {}. Debe ser 0-7.".format(canal))
        self.i2c.writeto(_DIRECCION_I2C, bytes([1 << canal]))

    def desactivar_todos(self):
        """Desactiva todos los canales escribiendo 0x00."""
        self.i2c.writeto(_DIRECCION_I2C, bytes([0x00]))
