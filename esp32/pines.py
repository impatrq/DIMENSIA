# ═══════════════════════════════════════════════════════
# PINES GPIO — DIMENSIA
# VALORES DE EJEMPLO — pendientes de confirmar con el
# cableado real del equipo de estructura.
# Ajustar acá y listo, no hace falta tocar cada módulo.
# ═══════════════════════════════════════════════════════

# --- Elevador (motor NEMA23 Wantai 57BYGH633 + driver TB6600) ---
# Driver configurado en 1/16 de micropaso (3200 pulsos por vuelta), 2,0 A, 12 V.
#
# ADVERTENCIA — pines de strapping del ESP32:
#   PIN_DIR = GPIO 12: si está en alto al encender puede impedir el arranque.
#   Verificar el arranque en frío con el driver alimentado; si falla, mover
#   DIR a un pin libre que no sea strapping.
#
# NOTA: PIN_ENABLE (GPIO 13) hoy NO está conectado a ENA del TB6600.
#   El driver queda siempre habilitado. El código maneja el pin igualmente
#   por si se conecta en el futuro.
PIN_STEP               = 14
PIN_DIR                = 12   # ADVERTENCIA: pin de strapping (ver comentario arriba)
PIN_ENABLE             = 13   # hoy sin conectar a ENA — driver siempre habilitado
PIN_FIN_CARRERA_ARRIBA = 32
PIN_FIN_CARRERA_ABAJO  = 33
PIN_FIN_CARRERA_PUERTA = 18   # final de carrera de la puerta, contacto NO entre el pin
                               # y GND, con pull-up interno (activo en bajo),
                               # igual que los de arriba y abajo — probado con
                               # la lógica de pull-up, respondió bien.

# Sentido de giro que hace subir el carro.
# PROVISIONAL: con el driver real, DIR = 1 gira horario visto desde la punta
# del eje (medido sin carga y sin husillo). Cuál sentido sube depende del
# husillo montado y de si la rosca es derecha o izquierda; confirmar con
# el husillo instalado y ajustar este valor si el carro baja en vez de subir.
SENTIDO_SUBIR = 1

# --- Servo del plato (MG996R 360°, rotación continua) ---
# ADVERTENCIA: GPIO 15 es pin de strapping del ESP32. Verificar el arranque
# en frío con el servo conectado; si falla mover a un pin libre.
PIN_SERVO_PLATO = 15   # ADVERTENCIA: pin de strapping (ver comentario arriba)

# --- Servo del brazo empujador (MG996R 180°, posicional) ---
PIN_SERVO_BRAZO = 16

# --- Servo de la paleta clasificadora (SG90 180°, posicional) ---
PIN_SERVO_PALETA = 17

# --- Botón físico de inicio de ciclo ---
PIN_BOTON = 4
