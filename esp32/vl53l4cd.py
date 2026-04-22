# Driver MicroPython para el sensor de distancia VL53L4CD (STMicroelectronics)
# Comunicación I2C, dirección 0x29, registros de 16 bits
# Basado en el Ultra Lite Driver (ULD) oficial de ST

# ─── Registros principales ────────────────────────────────────────────────────
_DIRECCION_I2C        = 0x29
_REG_WHO_AM_I         = 0x010F  # Identificación del chip — debe devolver 0xEB
_REG_SYSTEM_START     = 0x0087  # 0x40 = iniciar medición continua, 0x00 = detener
_REG_INTERRUPT_CLEAR  = 0x0086  # Escribir 0x01 para limpiar la interrupción
_REG_RANGE_STATUS     = 0x0089  # Estado del resultado — 0x09 en bit 0 = dato listo
_REG_DISTANCE_MM      = 0x0096  # Distancia medida: 2 bytes big-endian

# ─── Secuencia de configuración por defecto (ULD de STMicroelectronics) ───────
# Se escribe de una vez a partir del registro 0x002D.
# Valores extraídos directamente del archivo vl53l4cd_api.c del ULD oficial.
_REGISTRO_INICIO_CONFIG = 0x002D

_CONFIG_DEFAULT = bytes([
    0x12,  # 0x2D
    0x00,  # 0x2E
    0x00,  # 0x2F
    0x11,  # 0x30
    0x02,  # 0x31
    0x00,  # 0x32
    0x02,  # 0x33
    0x08,  # 0x34
    0x00,  # 0x35
    0x08,  # 0x36
    0x10,  # 0x37
    0x01,  # 0x38
    0x01,  # 0x39
    0x00,  # 0x3A
    0x00,  # 0x3B
    0x00,  # 0x3C
    0x00,  # 0x3D
    0xFF,  # 0x3E
    0x00,  # 0x3F
    0x0F,  # 0x40
    0x00,  # 0x41
    0x00,  # 0x42
    0x00,  # 0x43
    0x00,  # 0x44
    0x00,  # 0x45
    0x20,  # 0x46 — interrupción: "nuevo dato listo"
    0x0B,  # 0x47
    0x00,  # 0x48
    0x00,  # 0x49
    0x02,  # 0x4A
    0x14,  # 0x4B
    0x21,  # 0x4C
    0x00,  # 0x4D
    0x00,  # 0x4E
    0x05,  # 0x4F
    0x00,  # 0x50
    0x00,  # 0x51
    0x00,  # 0x52
    0x00,  # 0x53
    0xC8,  # 0x54
    0x00,  # 0x55
    0x00,  # 0x56
    0x38,  # 0x57
    0xFF,  # 0x58
    0x01,  # 0x59
    0x00,  # 0x5A
    0x08,  # 0x5B
    0x00,  # 0x5C
    0x00,  # 0x5D
    0x01,  # 0x5E
    0xCC,  # 0x5F
    0x07,  # 0x60
    0x01,  # 0x61
    0xF1,  # 0x62
    0x05,  # 0x63
    0x00,  # 0x64 — umbral sigma MSB (por defecto 15 mm)
    0xA0,  # 0x65 — umbral sigma LSB
    0x00,  # 0x66 — umbral de señal mínima MSB
    0x80,  # 0x67 — umbral de señal mínima LSB
    0x08,  # 0x68
    0x38,  # 0x69
    0x00,  # 0x6A
    0x00,  # 0x6B
    0x00,  # 0x6C — período entre mediciones MSB (4 bytes)
    0x00,  # 0x6D
    0x0F,  # 0x6E
    0x89,  # 0x6F — período entre mediciones LSB
    0x00,  # 0x70
    0x00,  # 0x71
    0x00,  # 0x72 — umbral distancia alta MSB
    0x00,  # 0x73 — umbral distancia alta LSB
    0x00,  # 0x74 — umbral distancia baja MSB
    0x00,  # 0x75 — umbral distancia baja LSB
    0x00,  # 0x76
    0x01,  # 0x77
    0x07,  # 0x78
    0x05,  # 0x79
    0x06,  # 0x7A
    0x06,  # 0x7B
    0x00,  # 0x7C
    0x00,  # 0x7D
    0x02,  # 0x7E
    0xC7,  # 0x7F — centro del ROI
    0xFF,  # 0x80 — tamaño del ROI (ancho x alto)
    0x9B,  # 0x81
    0x00,  # 0x82
    0x00,  # 0x83
    0x00,  # 0x84
    0x01,  # 0x85
    0x00,  # 0x86 — interrupción limpia (se pone en 0 al cargar)
    0x00,  # 0x87 — start/stop en 0; se arranca por separado con 0x40
])


# ─── Funciones de bajo nivel para leer/escribir registros ────────────────────

def _escribir(i2c, registro, datos):
    """Escribe uno o más bytes en un registro de 16 bits."""
    reg_alto = (registro >> 8) & 0xFF
    reg_bajo = registro & 0xFF
    i2c.writeto(_DIRECCION_I2C, bytes([reg_alto, reg_bajo]) + bytes(datos))


def _leer(i2c, registro, n_bytes):
    """Lee n_bytes desde un registro de 16 bits. Devuelve bytes."""
    reg_alto = (registro >> 8) & 0xFF
    reg_bajo = registro & 0xFF
    i2c.writeto(_DIRECCION_I2C, bytes([reg_alto, reg_bajo]))
    return i2c.readfrom(_DIRECCION_I2C, n_bytes)


# ─── Clase principal ──────────────────────────────────────────────────────────

class VL53L4CD:
    """Driver para el sensor ToF láser VL53L4CD en MicroPython."""

    def __init__(self, i2c):
        self.i2c = i2c

    def inicializar(self):
        """
        Verifica el sensor, carga la configuración por defecto del ULD
        y arranca las mediciones continuas.
        """
        # Verificar que el sensor responde con el ID correcto
        who_am_i = _leer(self.i2c, _REG_WHO_AM_I, 1)[0]
        if who_am_i != 0xEB:
            raise Exception(
                "VL53L4CD no encontrado en I2C 0x29. "
                "WHO_AM_I esperado: 0xEB, recibido: 0x{:02X}".format(who_am_i)
            )

        # Cargar la secuencia de configuración completa del ULD de ST
        # Se escribe en un solo bloque a partir del registro 0x002D
        _escribir(self.i2c, _REGISTRO_INICIO_CONFIG, _CONFIG_DEFAULT)

        # Arrancar mediciones continuas (0x40 en el registro SYSTEM_START)
        _escribir(self.i2c, _REG_SYSTEM_START, [0x40])

    def leer_distancia(self):
        """
        Espera a que haya un dato nuevo, lee la distancia en mm,
        limpia la interrupción y devuelve la distancia como entero.
        """
        # Esperar hasta que el sensor indique que hay un resultado listo.
        # El registro RANGE_STATUS vale 0x09 cuando el dato es válido.
        for _ in range(200):
            estado = _leer(self.i2c, _REG_RANGE_STATUS, 1)[0]
            if estado == 0x09:
                break

        # Leer los 2 bytes de distancia (big-endian) y convertirlos a entero
        datos = _leer(self.i2c, _REG_DISTANCE_MM, 2)
        distancia_mm = (datos[0] << 8) | datos[1]

        # Limpiar la interrupción para habilitar la siguiente medición
        _escribir(self.i2c, _REG_INTERRUPT_CLEAR, [0x01])

        return distancia_mm

    def detener(self):
        """Detiene las mediciones continuas."""
        _escribir(self.i2c, _REG_SYSTEM_START, [0x00])
