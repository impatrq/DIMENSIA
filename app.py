import io
import csv
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from database import init_db, obtener_inspecciones, guardar_inspeccion, obtener_piezas, guardar_pieza, guardar_calibracion, obtener_calibracion, obtener_calibraciones

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
    # Agregar operario activo automaticamente si no viene en los datos
    if not datos.get('operario'):
        datos['operario'] = operario_activo.get('operario')
        datos['legajo']   = operario_activo.get('legajo')
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

# Guardar calibracion de las camaras (factor px/mm)
@app.route('/calibracion', methods=['POST'])
def set_calibracion():
    datos = request.get_json()
    fecha = guardar_calibracion(datos)
    return jsonify({
        'estado': 'ok',
        'px_por_mm_superior': datos.get('px_por_mm_superior'),
        'px_por_mm_lateral': datos.get('px_por_mm_lateral'),
        'fecha': fecha
    })

# Obtener ultima calibracion guardada
@app.route('/calibracion', methods=['GET'])
def get_calibracion():
    calibracion = obtener_calibracion()
    return jsonify(calibracion)

# Obtener ultimas 5 calibraciones
@app.route('/calibraciones', methods=['GET'])
def get_calibraciones():
    calibraciones = obtener_calibraciones()
    return jsonify(calibraciones)

# Estado del elevador y la compuerta de seguridad (booleanos)
# final_carrera_superior: elevador llegó al tope superior
# final_carrera_inferior: elevador llegó al tope inferior
# puerta_cerrada: compuerta de seguridad cerrada
estado_elevador = {
    'final_carrera_superior': False,
    'final_carrera_inferior': True,
    'puerta_cerrada': True
}

# Recibir estado del elevador y la compuerta desde el ESP32
@app.route('/sensores', methods=['POST'])
def set_sensores():
    datos = request.get_json()
    for key in ('final_carrera_superior', 'final_carrera_inferior', 'puerta_cerrada'):
        if key in datos:
            estado_elevador[key] = bool(datos[key])
    return jsonify({'estado': 'ok'})

# Obtener estado actual del elevador y la compuerta
@app.route('/sensores', methods=['GET'])
def get_sensores():
    return jsonify(estado_elevador)

# Estados posibles del ciclo de inspeccion
ESTADOS_CICLO_VALIDOS = (
    'IDLE', 'SUBIENDO', 'MIDIENDO', 'PROCESANDO', 'DECISION',
    'BAJANDO', 'INCLINANDO_PLATAFORMA', 'EMPUJANDO', 'CLASIFICADO'
)

# Estado del ciclo de inspeccion en memoria
estado_ciclo = {'estado': 'IDLE'}

# Recibir nuevo estado del ciclo desde el ESP32
@app.route('/estado_ciclo', methods=['POST'])
def set_estado_ciclo():
    datos = request.get_json()
    nuevo_estado = datos.get('estado')
    if nuevo_estado not in ESTADOS_CICLO_VALIDOS:
        return jsonify({
            'estado': 'error',
            'mensaje': f'Estado invalido: {nuevo_estado}. Valores permitidos: {", ".join(ESTADOS_CICLO_VALIDOS)}'
        }), 400
    estado_ciclo['estado'] = nuevo_estado
    return jsonify({'estado': 'ok'})

# Obtener estado actual del ciclo de inspeccion
@app.route('/estado_ciclo', methods=['GET'])
def get_estado_ciclo():
    return jsonify(estado_ciclo)

# Capturas registradas por el ESP32 (ángulo en que se tomó cada foto)
capturas = []

# Recibir aviso del ESP32 indicando el ángulo de cada captura
@app.route('/captura', methods=['POST'])
def nueva_captura():
    datos = request.get_json()
    angulo = datos.get('angulo')
    if angulo is None:
        return jsonify({'estado': 'error', 'mensaje': 'Falta campo angulo'}), 400
    capturas.append({'angulo': angulo})
    return jsonify({'estado': 'ok', 'angulo': angulo, 'total': len(capturas)})

# Obtener lista de capturas registradas en el ciclo actual
@app.route('/captura', methods=['GET'])
def get_capturas():
    return jsonify({'capturas': capturas, 'total': len(capturas)})

# Limpiar lista de capturas (inicio de nuevo ciclo)
@app.route('/captura', methods=['DELETE'])
def limpiar_capturas():
    capturas.clear()
    return jsonify({'estado': 'ok', 'mensaje': 'Capturas reiniciadas'})

# Estado del plato giratorio en memoria
estado_plato = {
    'girando': False,
    'angulo_actual': 0,
    'ciclo_completo': False
}

# Recibir estado del plato desde el ESP32
@app.route('/plato', methods=['POST'])
def set_plato():
    datos = request.get_json()
    estado_plato.update({k: datos[k] for k in ('girando', 'angulo_actual', 'ciclo_completo') if k in datos})
    return jsonify({'estado': 'ok'})

# Obtener estado actual del plato giratorio
@app.route('/plato', methods=['GET'])
def get_plato():
    return jsonify(estado_plato)

# Estado de los 3 servos en memoria
estado_servos = {
    'servo1': {'activo': False, 'nombre': 'Empuje al plato'},
    'servo2': {'activo': False, 'nombre': 'Salida aprobada'},
    'servo3': {'activo': False, 'nombre': 'Rechazador'},
}

# Recibir estado de los servos desde el ESP32
@app.route('/servos', methods=['POST'])
def set_servos():
    datos = request.get_json()
    for key in ('servo1', 'servo2', 'servo3'):
        if key in datos:
            valor = datos[key]
            if isinstance(valor, str):
                estado_servos[key]['activo'] = valor.lower() == 'activo'
            else:
                estado_servos[key]['activo'] = bool(valor)
    return jsonify({'estado': 'ok'})

# Obtener estado actual de los 3 servos
@app.route('/servos', methods=['GET'])
def get_servos():
    return jsonify(estado_servos)

# ── EXPORTAR CSV ────────────────────────────────────
@app.route('/exportar', methods=['GET'])
def exportar_csv():
    inspecciones = obtener_inspecciones()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    output.write('sep=;\n')
    writer.writerow(['#', 'Pieza', 'N° Serie', 'Alto (mm)', 'Ancho (mm)', 'Largo (mm)', 'Estado', 'Operario', 'Fecha'])
    for i in inspecciones:
        writer.writerow([
            i.get('id', ''),
            i.get('pieza', '—'),
            i.get('numero_serie', '—'),
            f"{i['alto']:.1f}" if i.get('alto') else '—',
            f"{i['ancho']:.1f}" if i.get('ancho') else '—',
            f"{i['largo']:.1f}" if i.get('largo') else '—',
            i.get('resultado', '—'),
            i.get('operario', '—'),
            i.get('fecha', '—')
        ])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=inspecciones_dimensia.csv'}
    )

# ── ARRANCAR SERVIDOR ────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
