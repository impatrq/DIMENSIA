from flask import Flask, jsonify, request
from database import init_db, obtener_inspecciones, guardar_inspeccion, obtener_piezas

app = Flask(__name__)

# Inicializar base de datos al arrancar
init_db()

# ── RUTAS ────────────────────────────────────────────

# Ruta principal - verificar que el servidor funciona
@app.route('/')
def index():
    return jsonify({'mensaje': 'DIMENSIA Backend funcionando', 'version': '1.0'})

# Recibir datos de una inspeccion desde la Raspberry Pi
@app.route('/inspeccion', methods=['POST'])
def nueva_inspeccion():
    datos = request.get_json()
    guardar_inspeccion(datos)
    return jsonify({'estado': 'ok', 'mensaje': 'Inspeccion guardada'})

# Obtener todas las inspecciones para el dashboard
@app.route('/inspecciones', methods=['GET'])
def get_inspecciones():
    inspecciones = obtener_inspecciones()
    return jsonify(inspecciones)

# Obtener tipos de piezas registradas
@app.route('/piezas', methods=['GET'])
def get_piezas():
    piezas = obtener_piezas()
    return jsonify(piezas)

# ── ARRANCAR SERVIDOR ────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)