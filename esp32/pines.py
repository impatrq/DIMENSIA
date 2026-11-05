# ═══════════════════════════════════════════════════════
# PINES GPIO — DIMENSIA
# Cableado real de la placa perforada (5/11/2026).
# Ajustar acá y listo, no hace falta tocar cada módulo.
# ═══════════════════════════════════════════════════════

# --- Elevador (motor NEMA23 Wantai 57BYGH633 + driver TB6600) ---
# Driver configurado en 1/16 de micropaso (3200 pulsos por vuelta), 2,0 A, 12 V.
#
# NOTA — pines de strapping del ESP32: PIN_DIR = GPIO 2 es pin de strapping.
#   Conectado a la entrada del optoacoplador (DIR+) arranca bien. Si algún día
#   no arranca o no deja cargar archivos, desconectar DIR un momento.
#   (Antes se usaba GPIO 12, que también es de strapping; se cambió el 5/11
#   por un error de soldadura en la placa perforada.)
#
# NOTA: PIN_ENABLE (GPIO 13) hoy NO está conectado a ENA del TB6600.
#   El driver queda siempre habilitado. El código maneja el pin igualmente
#   por si se conecta en el futuro.
PIN_STEP               = 4
PIN_DIR                = 2    # pin de strapping (ver nota arriba)
PIN_ENABLE             = 13   # hoy sin conectar a ENA — driver siempre habilitado
PIN_FIN_CARRERA_ARRIBA = 32
PIN_FIN_CARRERA_ABAJO  = 33
PIN_PUERTA             = 25   # microswitch de la puerta: COM a GND y NO al pin, con
                               # pull-up interno (activo en bajo: cerrada = 0).
                               # Se activa con USAR_PUERTA = True en elevador_demo.py.

# Sentido de giro que hace subir el carro.
# Medido el 29/10 con el husillo T8 acoplado (placa nueva): con 0 sube.
SENTIDO_SUBIR = 0

# --- Servo del plato (MG996R 360°, rotación continua) ---
# GPIO 15 es pin de strapping del ESP32; arranca bien con el servo conectado.
PIN_SERVO_PLATO = 15
# El servo se alimenta desde una fuente aparte (6 V) a través de un TIP142.
# PIN_SERVO_ALIM va a la base del TIP142 (resistencia de 330 ohm).
PIN_SERVO_ALIM = 26

# --- Servo del brazo empujador (MG996R 180°, posicional) ---
PIN_SERVO_BRAZO = 16

# --- Servo de la paleta clasificadora (SG90 180°, posicional) ---
PIN_SERVO_PALETA = 17

# --- Botón físico de inicio de ciclo ---
PIN_BOTON = 14   # pulsador entre el pin y GND, con pull-up interno
