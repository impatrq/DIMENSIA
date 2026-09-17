# ═══════════════════════════════════════════════════════
# PINES GPIO — DIMENSIA
# VALORES DE EJEMPLO — pendientes de confirmar con el
# cableado real del equipo de estructura.
# Ajustar acá y listo, no hace falta tocar cada módulo.
# ═══════════════════════════════════════════════════════

# --- Elevador (motor NEMA17 + finales de carrera) ---
PIN_STEP               = 14
PIN_DIR                = 12
PIN_ENABLE             = 13
PIN_FIN_CARRERA_ARRIBA = 32
PIN_FIN_CARRERA_ABAJO  = 33

# --- Servo del plato (MG996R 360°, rotación continua) ---
PIN_SERVO_PLATO = 15

# --- Servo del brazo empujador (MG996R 180°, posicional) ---
PIN_SERVO_BRAZO = 16

# --- Servo de la paleta clasificadora (SG90 180°, posicional) ---
PIN_SERVO_PALETA = 17

# --- Botón físico de inicio de ciclo ---
PIN_BOTON = 4
