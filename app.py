from flask import Flask, jsonify, request
from flask_cors import CORS
from database import init_db, obtener_inspecciones, guardar_inspeccion, obtener_piezas, guardar_pieza, guardar_calibracion, obtener_calibracion

app = Flask(__name__) 
CORS(app)

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

# Guardar una nueva pieza
@app.route('/piezas', methods=['POST'])
def nueva_pieza():
    datos = request.get_json()
    id_pieza = guardar_pieza(datos)
    return jsonify({'estado': 'ok', 'mensaje': 'Pieza guardada', 'id': id_pieza})

# Obtener tipos de piezas registradas
@app.route('/piezas', methods=['GET'])
def get_piezas():
    piezas = obtener_piezas()
    return jsonify(piezas)

# Operario activo en memoria
operario_activo = {'operario': None, 'legajo': None}

# Guardar operario activo
@app.route('/operario_activo', methods=['POST'])
def set_operario():
    datos = request.get_json()
    operario_activo['operario'] = datos.get('operario')
    operario_activo['legajo'] = datos.get('legajo')
    return jsonify({'estado': 'ok'})

# Obtener operario activo
@app.route('/operario_activo', methods=['GET'])
def get_operario():
    return jsonify(operario_activo)

# Guardar calibracion del sistema diferencial
@app.route('/calibracion', methods=['POST'])
def set_calibracion():
    datos = request.get_json()
    guardar_calibracion(datos)
    return jsonify({
        'estado': 'ok',
        'REF_S1': datos.get('REF_S1'),
        'D_S2_S2p': datos.get('D_S2_S2p'),
        'D_S3_S3p': datos.get('D_S3_S3p')
    })

# Obtener ultima calibracion guardada
@app.route('/calibracion', methods=['GET'])
def get_calibracion():
    calibracion = obtener_calibracion()
    return jsonify(calibracion)

# ── ARRANCAR SERVIDOR ────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
