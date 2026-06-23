
# ====================================================================================
# IMPORTACIONES Y CONFIGURACIÓN
# ====================================================================================
import os
import sys
import io

# Forzar UTF-8 en stdout/stderr para evitar UnicodeEncodeError con emojis en Windows (cp1252)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import pyodbc
from functools import wraps
import json
import socket
from flask_cors import CORS, cross_origin
from datetime import datetime
import hashlib

# ====================================================================================
# FUNCIONES DE ENCRIPTACIÓN DE CONTRASEÑAS CON WERKZEUG
# ====================================================================================
def hash_password(password):
    """
    Encripta una contraseña usando werkzeug.security (Scrypt).
    Método recomendado y sin dependencias externas.
    """
    return generate_password_hash(password)
 
def verify_password(password, hashed_password):
    """
    Verifica una contraseña contra su hash.
    Soporta werkzeug (principal), SHA-256 con salt (legacy) y texto plano (legacy).
    Nota: Hashes legacy ya no son soportados - requieren migración.
    """
    if not hashed_password:
        return False
   
    try:
        # Verificar si es hash werkzeug (Scrypt o PBKDF2) - Método principal
        if hashed_password.startswith('scrypt:') or hashed_password.startswith('pbkdf2:'):
            return check_password_hash(hashed_password, password)
       
        # Hashes legacy no soportados - migrar a werkzeug
        if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$'):
            print("⚠️ Hash legacy encontrado - requiere migración a werkzeug")
            return False
       
        # Verificar si es hash SHA-256 con salt (legacy)
        if hashed_password.startswith('sha256$'):
            parts = hashed_password.split('$')
            if len(parts) == 3:
                salt = parts[1]
                stored_hash = parts[2]
                hash_obj = hashlib.sha256((password + salt).encode('utf-8'))
                return hash_obj.hexdigest() == stored_hash
       
        # Fallback: comparación directa (contraseñas legacy en texto plano)
        return password == hashed_password
       
    except Exception as e:
        print(f"Error en verificación de contraseña: {e}")
        return False
 
def is_password_hashed(password):
    """
    Determina si una contraseña ya está encriptada.
    Soporta formatos: werkzeug (scrypt/pbkdf2), SHA-256 legacy.
    """
    if not password:
        return False
   
    # Verificar si es werkzeug (scrypt o pbkdf2)
    if password.startswith('scrypt:') or password.startswith('pbkdf2:'):
        return True
   
    # Verificar si es hash legacy (ya no soportado - requiere migración)
    if password.startswith('$2b$') or password.startswith('$2a$'):
        return True
   
    # Verificar si es SHA-256 con salt (legacy)
    if password.startswith('sha256$'):
        return True
   
    return False
 
def migrate_password_if_needed(password):
    """
    Migra una contraseña legacy a formato werkzeug si es necesario.
    Prioriza werkzeug sobre otros formatos.
    """
    if password.startswith('scrypt:') or password.startswith('pbkdf2:'):
        return password  # Ya está en formato werkzeug
   
    # La contraseña necesita migración a werkzeug (texto plano, hash legacy, o sha256)
    return hash_password(password)
 
# Configuración directa de usuario y contraseña de la base de datos
DB_USER = 'sa'
DB_PASSWORD = 'Coppersink10EMESA'

# Configuración directa de usuario y contraseña de la base de datos CZ
DB_USERCZ = 'sccz'
DB_PASSWORDCZ = 'S@vera,CZ,2024'

SECRET_KEY = None
SHUTDOWN_SECRET_KEY = None

# Inicializar Flask (SOLO UNA VEZ)
app = Flask(__name__)
app.secret_key = 'emesa_sga_secret_key_2025'  # Para sesiones
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST", "PUT", "OPTIONS"], allow_headers=["Content-Type"])

# Ruta absoluta a la carpeta compartida (pantallas HTML)
RUTA_PANTALLAS = r"\\EMEBIDWH\DIgitalizacion\CAB - V1\templates"
# Ruta absoluta a la carpeta de assets
RUTA_ASSETS = r"\\EMEBIDWH\DIgitalizacion\CAB - V1\assets"
# Ruta absoluta a la carpeta de imágenes
RUTA_IMAGENES = r"\\EMEBIDWH\DIgitalizacion\CAB - V1\IMAGENES"

# ====================================================================================
# CLASE DE CONEXIÓN ODBC
# ====================================================================================
class ConexionODBC:
    def __init__(self, database=None, servidor='EMEBIDWH'):
        # Usa un driver más actual
        self.driver = 'ODBC Driver 17 for SQL Server'
        self.server = servidor
        self.database = database
        self.conn = None

    def __enter__(self):
        try:
            if not DB_USER or not DB_PASSWORD:
                raise Exception('Faltan credenciales de base de datos')

            conn_str = (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"UID={DB_USER};PWD={DB_PASSWORD};"
                "TrustServerCertificate=yes;"
            )

            # Forzamos timeout para que no se quede colgado eternamente
            self.conn = pyodbc.connect(conn_str, timeout=5, autocommit=True)
            return self.conn

        except Exception as e:
            print(f"Error CRÍTICO al conectar con la base de datos: {e}")
            return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()


# ====================================================================================
# CLASE DE CONEXIÓN ODBC PARA CZ
# ====================================================================================

class ConexionODBCCZ:
    def __init__(self, database='mapexbp', servidor='172.16.10.10'):
        self.driver = 'SQL Server'
        self.server = servidor
        self.database = database
        self.conn = None

    def __enter__(self):
        try:
            if not DB_USERCZ or not DB_PASSWORDCZ:
                raise Exception('Faltan credenciales de base de datos CZ')
            conn_str = (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"UID={DB_USERCZ};PWD={DB_PASSWORDCZ};"
                "TrustServerCertificate=yes;"
            )
            self.conn = pyodbc.connect(conn_str)
            return self.conn
        except Exception as e:
            print(f"Error CRÍTICO al conectar con la base de datos CZ: {e}")
            return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()


# ====================================================================================
# RUTAS PARA SERVIR ARCHIVOS ESTÁTICOS
# ====================================================================================

@app.route('/')
def index():
    """Página principal - redirigir a PuestosCAB"""
    return send_from_directory(RUTA_PANTALLAS + "\\generales", "PuestosCAB.html")

@app.route('/Templates/<path:nombre_archivo>')
def servir_pantalla(nombre_archivo):
    ruta_completa = os.path.join(RUTA_PANTALLAS, nombre_archivo)
    if not os.path.exists(ruta_completa):
        return f"Archivo no encontrado: {nombre_archivo}", 404
    return send_from_directory(RUTA_PANTALLAS, nombre_archivo)

@app.route('/templates/<path:nombre_archivo>')
def servir_templates_minuscula(nombre_archivo):
    """Ruta alternativa con minúsculas"""
    ruta_completa = os.path.join(RUTA_PANTALLAS, nombre_archivo)
    if not os.path.exists(ruta_completa):
        return f"Archivo no encontrado: {nombre_archivo}", 404
    return send_from_directory(RUTA_PANTALLAS, nombre_archivo)

@app.route('/assets/<path:nombre_archivo>')
def servir_assets(nombre_archivo):
    ruta_completa = os.path.join(RUTA_ASSETS, nombre_archivo)
    if not os.path.exists(ruta_completa):
        return f"Archivo no encontrado: {nombre_archivo}", 404
    return send_from_directory(RUTA_ASSETS, nombre_archivo)

@app.route('/IMAGENES/<path:nombre_archivo>')
def servir_imagenes(nombre_archivo):
    ruta_completa = os.path.join(RUTA_IMAGENES, nombre_archivo)
    if not os.path.exists(ruta_completa):
        return f"Archivo no encontrado: {nombre_archivo}", 404
    return send_from_directory(RUTA_IMAGENES, nombre_archivo)
# ====================================================================================
# ENDPOINT DE LOGIN CON SOPORTE PARA CONTRASEÑAS ENCRIPTADAS
# ====================================================================================
@app.route('/api/login', methods=['POST'])
def login():
    """Endpoint de login mejorado compatible con el sistema EMESA existente"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
       
        usuario = data.get('usuario', '').strip()
        password = data.get('password', '').strip()
       
        if not usuario or not password:
            return jsonify({'success': False, 'message': 'Usuario y contraseña requeridos'}), 400
       
        # Buscar usuario en la base de datos usando la estructura EMESA
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
           
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Id_Usuario, Num_Operario, Nombre, Nivel_Permisos, Roles, Contrasena
                FROM General.Usuarios
                WHERE Num_Operario = ?
            """, (usuario,))
           
            result = cursor.fetchone()
            if not result:
                return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 401
           
            # Verificar contraseña usando el sistema robusto
            stored_password = result[5]
            if not verify_password(password, stored_password):
                return jsonify({'success': False, 'message': 'Contraseña incorrecta'}), 401
           
            # Si la contraseña estaba en texto plano, migrarla a encriptada
            if not is_password_hashed(stored_password):
                new_hashed_password = hash_password(password)
                cursor.execute(
                    "UPDATE General.Usuarios SET Contrasena=? WHERE Id_Usuario=?",
                    (new_hashed_password, result[0])
                )
                conn.commit()
                print(f"✅ Contraseña migrada a hash para usuario {usuario}")
           
            # Crear sesión (mejora del sistema original)
            user_data = {
                'id': result[0],
                'num_operario': result[1],
                'nombre': result[2],
                'nivel': result[3],
                'rol': result[4]
            }
           
            session['user_id'] = result[0]
            session['user_data'] = user_data
            session.permanent = True
           
            # Respuesta compatible con el formato existente
            return jsonify({
                'success': True,
                'id': result[0],
                'num_operario': result[1],
                'nombre': result[2],
                'nivel': result[3],
                'rol': result[4]
            })
           
    except Exception as e:
        print(f"Error en /api/login: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
 
from flask import request, jsonify
 
# ====================================================================================
# NUEVOS ENDPOINTS DE SESIÓN Y AUTENTICACIÓN MEJORADA
# ====================================================================================
 
@app.route('/api/logout', methods=['POST'])
def logout():
    """Endpoint de logout"""
    try:
        session.clear()
        return jsonify({'success': True, 'message': 'Sesión cerrada exitosamente'})
    except Exception as e:
        print(f"Error en logout: {e}")
        return jsonify({'success': False, 'message': 'Error del servidor'}), 500
 
@app.route('/api/verify_session', methods=['GET'])
def verify_session():
    """Verificar sesión actual"""
    try:
        if 'user_id' in session and 'user_data' in session:
            return jsonify({
                'success': True,
                'authenticated': True,
                'user': session['user_data']
            })
       
        return jsonify({
            'success': True,
            'authenticated': False,
            'user': None
        })
       
    except Exception as e:
        print(f"Error verificando sesión: {e}")
        return jsonify({'success': False, 'message': 'Error del servidor'}), 500
 
 # ====================================================================================
# RUTAS PARA SERVIR ARCHIVOS ESTÁTICOS MEJORADAS
# ====================================================================================
 
@app.route('/LOGIN_MODULE/<path:nombre_archivo>')
def servir_login_module(nombre_archivo):
    ruta_login = r"\\EMEBIDWH\DIgitalizacion\CAB - V1\LOGIN_MODULE"
    ruta_completa = os.path.join(ruta_login, nombre_archivo)
    if not os.path.exists(ruta_completa):
        return f"Archivo no encontrado: {nombre_archivo}", 404
    return send_from_directory(ruta_login, nombre_archivo)
# ====================================================================================
# ENDPOINTS DE USUARIOS
# ====================================================================================
@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    # Suponiendo que el usuario autenticado se identifica por un header o token
    # Aquí se espera que el frontend envíe el id del usuario actual como query param o header
    id_usuario_actual = request.args.get('id_usuario', type=int)
    try:
        with ConexionODBC(database='Digitalizacion') as conn:
            cursor = conn.cursor()
            # Obtener nivel del usuario actual
            cursor.execute("SELECT Nivel_Permisos FROM General.Usuarios WHERE Id_Usuario=?", (id_usuario_actual,))
            row = cursor.fetchone()
            nivel_actual = row[0] if row else 0
 
            # Traer todos los usuarios
            cursor.execute("""
                SELECT Id_Usuario, Num_Operario, Nombre, Nivel_Permisos, Roles
                FROM General.Usuarios
            """)
            usuarios = []
            for u in cursor.fetchall():
                # Filtrar según nivel
                if nivel_actual < 9 and u[3] in (9, 10):
                    continue
                usuarios.append({
                    'id': u[0],
                    'num_operario': u[1],
                    'nombre': u[2],
                    'nivel': u[3],
                    'rol': u[4]
                })
        return jsonify({'success': True, 'usuarios': usuarios})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
 
# ====================================================================================
# ENDPOINT PARA OBTENER NIVEL DE PERMISOS DE UN USUARIO
# ====================================================================================
@app.route('/api/usuario/nivel', methods=['GET'])
def obtener_nivel_usuario():
    """Obtiene el nivel de permisos de un usuario específico (mejorado)"""
    user_id = request.args.get('id_usuario', type=int)
    num_operario = request.args.get('num_operario')
   
    if not user_id and not num_operario:
        return jsonify({'success': False, 'message': 'Se requiere id_usuario o num_operario'}), 400
   
    try:
        with ConexionODBC(database='Digitalizacion') as conn:
            if conn is None:
                return jsonify({'success': False, 'message': 'Error de conexión a la base de datos'}), 500
           
            cursor = conn.cursor()
           
            if user_id:
                cursor.execute("SELECT Nivel_Permisos FROM General.Usuarios WHERE Id_Usuario=?", (user_id,))
            else:
                cursor.execute("SELECT Nivel_Permisos FROM General.Usuarios WHERE Num_Operario=?", (num_operario,))
           
            row = cursor.fetchone()
           
            if row:
                return jsonify({
                    'success': True,
                    'nivel': row[0]
                })
            else:
                return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404
               
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
# ====================================================================================
# FUNCIONES AUXILIARES PARA TURNOS Y FECHAS
# ====================================================================================

def calcular_fecha_y_turno():
    """Calcula la fecha y turno según las reglas del negocio"""
    now = datetime.now()
    hora_actual = now.hour
    
    # Determinar el turno según la hora
    if 6 <= hora_actual < 14:
        turno = "TM"
        fecha = now.date()
    elif 14 <= hora_actual < 22:
        turno = "TT" 
        fecha = now.date()
    else:  # 22:00 a 6:00 (turno nocturno)
        turno = "TN"
        # Si es entre 22:00 y 00:00, la fecha es hoy + 1
        if hora_actual >= 22:
            from datetime import timedelta
            fecha = now.date() + timedelta(days=1)
        else:  # Entre 00:00 y 6:00, mantener la fecha actual
            fecha = now.date()
    
    return fecha, turno

def obtener_usuario_sesion():
    """Obtiene el número de operario del usuario logueado de la sesión actual"""
    try:
        if 'user_data' in session and session['user_data']:
            user_data = session['user_data']
            # 🔑 CORREGIDO: Devolver num_operario en lugar de nombre
            num_operario = user_data.get('num_operario')
            nombre = user_data.get('nombre', 'Usuario')
            
            print(f"🔍 Datos de sesión disponibles:")
            print(f"   - num_operario: {num_operario}")
            print(f"   - nombre: {nombre}")
            print(f"   - user_data completo: {user_data}")
            
            if num_operario:
                print(f"✅ Devolviendo num_operario: {num_operario}")
                return num_operario
            else:
                print(f"⚠️ num_operario no encontrado, devolviendo nombre: {nombre}")
                return nombre
        else:
            # Si no hay sesión activa, devolver un valor por defecto
            print("⚠️ No hay sesión activa, devolviendo 'Sistema'")
            return 'Sistema'
    except Exception as e:
        print(f"💥 Error obteniendo usuario de sesión: {e}")
        return 'Sistema'

# ====================================================================================
# ENDPOINTS PARA MOTIVOS DE FALTANTE
# ====================================================================================

@app.route('/api/motivos-faltante', methods=['GET'])
def obtener_motivos_faltante():
    """Obtener lista de motivos de faltante activos"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Id_Motivo, Descripcion, Orden
                FROM [Digitalizacion].[CAB].[MotivosFaltante]
                WHERE Activo = 1
                ORDER BY Orden, Descripcion
            """)
            
            resultados = cursor.fetchall()
            motivos = []
            for row in resultados:
                motivos.append({
                    'id': row[0],
                    'descripcion': row[1],
                    'orden': row[2]
                })
            
            return jsonify({
                'success': True,
                'motivos': motivos,
                'total': len(motivos)
            })
            
    except Exception as e:
        print(f"Error obteniendo motivos de faltante: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/motivos-faltante', methods=['POST'])
def crear_motivo_faltante():
    """Crear un nuevo motivo de faltante"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        descripcion = data.get('descripcion', '').strip()
        orden = data.get('orden', 0)
        
        if not descripcion:
            return jsonify({'success': False, 'message': 'La descripción es requerida'}), 400
        
        # Obtener usuario de la sesión
        operario = obtener_usuario_sesion()
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Verificar si ya existe un motivo con esa descripción
            cursor.execute("""
                SELECT COUNT(*) FROM [Digitalizacion].[CAB].[MotivosFaltante]
                WHERE Descripcion = ? AND Activo = 1
            """, (descripcion,))
            
            if cursor.fetchone()[0] > 0:
                return jsonify({'success': False, 'message': 'Ya existe un motivo con esa descripción'}), 400
            
            # Insertar el nuevo motivo
            cursor.execute("""
                INSERT INTO [Digitalizacion].[CAB].[MotivosFaltante]
                (Descripcion, Orden, Activo, FechaCreacion, CreadoPor)
                VALUES (?, ?, 1, GETDATE(), ?)
            """, (descripcion, orden, operario))
            
            cursor.execute("SELECT @@IDENTITY")
            nuevo_id = cursor.fetchone()[0]
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Motivo creado exitosamente',
                'id': nuevo_id,
                'descripcion': descripcion
            })
            
    except Exception as e:
        print(f"Error creando motivo de faltante: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/motivos-faltante/<int:id_motivo>', methods=['DELETE'])
def eliminar_motivo_faltante(id_motivo):
    """Desactivar (soft delete) un motivo de faltante"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # No permitir eliminar "Otro" (normalmente tiene orden 99)
            cursor.execute("""
                SELECT Descripcion FROM [Digitalizacion].[CAB].[MotivosFaltante]
                WHERE Id_Motivo = ?
            """, (id_motivo,))
            
            resultado = cursor.fetchone()
            if resultado and resultado[0].lower() == 'otro':
                return jsonify({'success': False, 'message': 'No se puede eliminar el motivo "Otro"'}), 400
            
            # Soft delete - marcar como inactivo
            cursor.execute("""
                UPDATE [Digitalizacion].[CAB].[MotivosFaltante]
                SET Activo = 0
                WHERE Id_Motivo = ?
            """, (id_motivo,))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Motivo eliminado exitosamente'
            })
            
    except Exception as e:
        print(f"Error eliminando motivo de faltante: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/motivos-faltante/<int:id_motivo>', methods=['PUT'])
def actualizar_motivo_faltante(id_motivo):
    """Actualizar un motivo de faltante existente"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        descripcion = data.get('descripcion', '').strip()
        orden = data.get('orden', 0)
        
        if not descripcion:
            return jsonify({'success': False, 'message': 'La descripción es requerida'}), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Verificar que existe el motivo
            cursor.execute("""
                SELECT Id_Motivo FROM [Digitalizacion].[CAB].[MotivosFaltante]
                WHERE Id_Motivo = ? AND Activo = 1
            """, (id_motivo,))
            
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': 'Motivo no encontrado'}), 404
            
            # Verificar que no exista otro motivo con la misma descripción
            cursor.execute("""
                SELECT COUNT(*) FROM [Digitalizacion].[CAB].[MotivosFaltante]
                WHERE Descripcion = ? AND Id_Motivo != ? AND Activo = 1
            """, (descripcion, id_motivo))
            
            if cursor.fetchone()[0] > 0:
                return jsonify({'success': False, 'message': 'Ya existe otro motivo con esa descripción'}), 400
            
            # Actualizar el motivo
            cursor.execute("""
                UPDATE [Digitalizacion].[CAB].[MotivosFaltante]
                SET Descripcion = ?, Orden = ?
                WHERE Id_Motivo = ?
            """, (descripcion, orden, id_motivo))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Motivo actualizado exitosamente'
            })
            
    except Exception as e:
        print(f"Error actualizando motivo de faltante: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

# ====================================================================================
# ENDPOINTS PARA DATOS DE CABINAS
# ====================================================================================

@app.route('/api/registrar-estado', methods=['POST'])
def registrar_estado():
    """Registrar cambio de estado (Hecho/Faltante/NoHecho/NoFaltante/EnProceso) en DatosUserCAB"""
    try:
        data = request.get_json()
        print(f"📥 Datos recibidos en /api/registrar-estado: {data}")
        
        if not data:
            print("❌ Error: Datos inválidos (data es None)")
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        codlinea = data.get('codlinea', '').strip()
        gfh = data.get('gfh', '').strip()
        estado = data.get('estado', '').strip()  # Hecho, Faltante, NoHecho, NoFaltante, EnProceso
        realizacion_frontend = data.get('realizacion_frontend')  # Valor del input del frontend
        texto_faltante = data.get('texto_faltante', '').strip()  # NUEVO: Texto del faltante
        
        print(f"📋 Valores extraídos - CODLINEA: '{codlinea}', GFH: '{gfh}', ESTADO: '{estado}', REALIZACION_FRONTEND: {realizacion_frontend}, TEXTO_FALTANTE: '{texto_faltante}'")
        
        # Validar datos requeridos
        if not codlinea or not gfh or not estado:
            print(f"❌ Error: Faltan datos requeridos - CODLINEA: {bool(codlinea)}, GFH: {bool(gfh)}, ESTADO: {bool(estado)}")
            return jsonify({
                'success': False, 
                'message': 'CODLINEA, GFH y ESTADO son requeridos'
            }), 400
        
        # Validar que el estado sea válido
        estados_validos = ['Hecho', 'Faltante', 'NoHecho', 'NoFaltante', 'EnProceso']
        if estado not in estados_validos:
            print(f"❌ Error: Estado inválido '{estado}'. Estados válidos: {estados_validos}")
            return jsonify({
                'success': False, 
                'message': f'Estado inválido. Debe ser uno de: {", ".join(estados_validos)}'
            }), 400
        
        # Validar realizacion_frontend para estado EnProceso
        if estado == 'EnProceso':
            if realizacion_frontend is None:
                print("❌ Error: realizacion_frontend es requerido para estado EnProceso")
                return jsonify({
                    'success': False, 
                    'message': 'realizacion_frontend es requerido para estado EnProceso'
                }), 400
            
            try:
                realizacion_frontend = float(realizacion_frontend)
                if realizacion_frontend < 0 or realizacion_frontend > 100:
                    print(f"❌ Error: realizacion_frontend debe estar entre 0 y 100, recibido: {realizacion_frontend}")
                    return jsonify({
                        'success': False, 
                        'message': 'realizacion_frontend debe estar entre 0 y 100'
                    }), 400
            except (ValueError, TypeError):
                print(f"❌ Error: realizacion_frontend debe ser un número válido, recibido: {realizacion_frontend}")
                return jsonify({
                    'success': False, 
                    'message': 'realizacion_frontend debe ser un número válido'
                }), 400
        
        # Calcular fecha y turno
        fecha, turno = calcular_fecha_y_turno()
        print(f"📅 Fecha calculada: {fecha}, Turno: {turno}")
        
        # Obtener usuario de la sesión
        operario = obtener_usuario_sesion()
        print(f"👤 Usuario de la sesión: {operario}")
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Lógica específica para estado EnProceso
            if estado == 'EnProceso':
                # Obtener la suma actual de Realizacion para este CODLINEA y GFH
                cursor.execute("""
                    SELECT ISNULL(SUM(Realizacion), 0) as suma_actual
                    FROM [Digitalizacion].[CAB].[DatosUserCAB]
                    WHERE CODLINEA = ? AND GFH = ?
                """, (codlinea, gfh))
                
                resultado = cursor.fetchone()
                suma_actual = float(resultado[0]) if resultado and resultado[0] is not None else 0.0
                print(f"📊 Suma actual de Realizacion: {suma_actual}%")
                
                # Asegurar que realizacion_frontend también sea float
                realizacion_frontend = float(realizacion_frontend)
                
                # Calcular el valor a insertar
                valor_a_insertar = realizacion_frontend - suma_actual
                print(f"🧮 Cálculo: {realizacion_frontend} - {suma_actual} = {valor_a_insertar}")
                
                # Validar el valor a insertar
                if valor_a_insertar <= 0:
                    print(f"⚠️ Advertencia: El valor a insertar es negativo o cero: {valor_a_insertar}")
                    
                    # Verificar si hay confirmación del usuario para valor negativo
                    confirmacion = data.get('confirmar_negativo', False)
                    
                    if confirmacion:
                        print(f"✅ Usuario confirmó actualización negativa: {valor_a_insertar}")
                    else:
                        print(f"❓ Se requiere confirmación para actualización negativa: {valor_a_insertar}")
                        
                        # Log detallado para depuración
                        print(f"ℹ️ Información detallada para depuración:")
                        print(f"   - CODLINEA: {codlinea} (tipo: {type(codlinea).__name__})")
                        print(f"   - GFH: {gfh} (tipo: {type(gfh).__name__})")
                        print(f"   - Suma actual: {suma_actual}% (tipo: {type(suma_actual).__name__})")
                        print(f"   - Realizacion frontend: {realizacion_frontend}% (tipo: {type(realizacion_frontend).__name__})")
                        print(f"   - Valor a insertar: {valor_a_insertar} (tipo: {type(valor_a_insertar).__name__})")
                        
                        # Respuesta completa con todos los datos necesarios
                        return jsonify({
                            'success': False,
                            'requiresConfirmation': True,
                            'message': f'Está introduciendo una actualización negativa ({valor_a_insertar}). El progreso actual es {suma_actual}% y está intentando establecerlo a {realizacion_frontend}%.',
                            'current_value': suma_actual,
                            'codlinea': codlinea,
                            'gfh': gfh,
                            'debug_info': {
                                'valor_a_insertar': valor_a_insertar,
                                'suma_actual': suma_actual,
                                'realizacion_frontend': realizacion_frontend
                            }
                        }), 200
                
                # Insertar nuevo registro con progreso (puede ser positivo o negativo si está confirmado)
                print(f"💾 Insertando registro EnProceso: Realizacion={valor_a_insertar}, Operario={operario}")
                cursor.execute("""
                    INSERT INTO [Digitalizacion].[CAB].[DatosUserCAB] 
                    (CODLINEA, GFH, ESTADO, Realizacion, Activo, Fecha, Turno, Operario)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """, (codlinea, gfh, estado, valor_a_insertar, fecha, turno, operario))
                
                conn.commit()
                
                # Obtener el ID del registro recién creado
                cursor.execute("SELECT @@IDENTITY")
                nuevo_id = cursor.fetchone()[0]
                
                print(f"✅ Estado '{estado}' registrado exitosamente - ID: {nuevo_id}")
                print(f"📊 Detalles del registro:")
                print(f"   - ID: {nuevo_id}")
                print(f"   - CODLINEA: {codlinea}")
                print(f"   - GFH: {gfh}")
                print(f"   - ESTADO: {estado}")
                print(f"   - Realizacion: {valor_a_insertar}")
                print(f"   - Fecha: {fecha}")
                print(f"   - Turno: {turno}")
                print(f"   - Operario: {operario}")
                print(f"   - Activo: 1")
                
                # Mensaje especial si es una actualización negativa confirmada
                if valor_a_insertar < 0:
                    print(f"⚠️ ACTUALIZACIÓN NEGATIVA REGISTRADA: Total acumulado ahora es {realizacion_frontend}% (disminución de {abs(valor_a_insertar)}%)")
                else:
                    print(f"🔄 PROGRESO REGISTRADO: Total acumulado ahora es {realizacion_frontend}%")
                
                # Mensaje personalizado según si es una actualización positiva o negativa
                mensaje = ''
                if valor_a_insertar < 0:
                    mensaje = f'Actualización negativa: Progreso reducido a {realizacion_frontend}% (disminución de {abs(valor_a_insertar)}%)'
                else:
                    mensaje = f'Progreso {realizacion_frontend}% registrado exitosamente'
                
                return jsonify({
                    'success': True,
                    'message': mensaje,
                    'registro': {
                        'id': nuevo_id,
                        'codlinea': codlinea,
                        'gfh': gfh,
                        'estado': estado,
                        'realizacion': valor_a_insertar,
                        'total_realizacion': realizacion_frontend,
                        'fecha': fecha.strftime('%Y-%m-%d'),
                        'turno': turno,
                        'operario': operario,
                        'activo': True
                    }
                })
            
            elif estado == 'Hecho':
                # Lógica especial para estado Hecho: calcular realizacion para llegar a 100%
                # Obtener la suma actual de Realizacion para este CODLINEA y GFH
                cursor.execute("""
                    SELECT ISNULL(SUM(Realizacion), 0) as suma_actual
                    FROM [Digitalizacion].[CAB].[DatosUserCAB]
                    WHERE CODLINEA = ? AND GFH = ?
                """, (codlinea, gfh))
                
                resultado = cursor.fetchone()
                suma_actual = float(resultado[0]) if resultado and resultado[0] is not None else 0.0
                print(f"📊 Suma actual de Realizacion para Hecho: {suma_actual}%")
                
                # Calcular el valor para llegar a 100%
                valor_a_insertar = 100.0 - suma_actual
                print(f"🧮 Cálculo para Hecho: 100.0 - {suma_actual} = {valor_a_insertar}")
                
                # Validar que el valor a insertar sea positivo (puede ser 0 si ya estaba en 100%)
                if valor_a_insertar < 0:
                    print(f"⚠️ Advertencia: La suma actual ({suma_actual}%) ya supera el 100%. Insertando 0.")
                    valor_a_insertar = 0.0
                
                # Primero, marcar como inactivos todos los registros previos para este CODLINEA_GF
                print(f"🔄 Marcando registros anteriores como inactivos para CODLINEA: {codlinea}, GFH: {gfh}")
                cursor.execute("""
                    UPDATE [Digitalizacion].[CAB].[DatosUserCAB]
                    SET Activo = 0
                    WHERE CODLINEA = ? AND GFH = ?
                """, (codlinea, gfh))
                
                affected_rows = cursor.rowcount
                print(f"✅ Marcados como inactivos: {affected_rows} registros")
                
                # Insertar nuevo registro con estado Hecho y realizacion calculada
                print(f"💾 Insertando registro Hecho: Realizacion={valor_a_insertar}, Operario={operario}")
                cursor.execute("""
                    INSERT INTO [Digitalizacion].[CAB].[DatosUserCAB] 
                    (CODLINEA, GFH, ESTADO, Realizacion, Activo, Fecha, Turno, Operario)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """, (codlinea, gfh, estado, valor_a_insertar, fecha, turno, operario))
                
                conn.commit()
                
                # Obtener el ID del registro recién creado
                cursor.execute("SELECT @@IDENTITY")
                nuevo_id = cursor.fetchone()[0]
                
                print(f"✅ Estado '{estado}' registrado exitosamente - ID: {nuevo_id}")
                print(f"📊 Detalles del registro:")
                print(f"   - ID: {nuevo_id}")
                print(f"   - CODLINEA: {codlinea}")
                print(f"   - GFH: {gfh}")
                print(f"   - ESTADO: {estado}")
                print(f"   - Realizacion: {valor_a_insertar}")
                print(f"   - Fecha: {fecha}")
                print(f"   - Turno: {turno}")
                print(f"   - Operario: {operario}")
                print(f"   - Activo: 1")
                print(f"🎯 HECHO REGISTRADO: Total realizacion ahora es 100%")
                
                return jsonify({
                    'success': True,
                    'message': f'Estado {estado} registrado exitosamente (100% completado)',
                    'registro': {
                        'id': nuevo_id,
                        'codlinea': codlinea,
                        'gfh': gfh,
                        'estado': estado,
                        'realizacion': valor_a_insertar,
                        'total_realizacion': 100.0,
                        'fecha': fecha.strftime('%Y-%m-%d'),
                        'turno': turno,
                        'operario': operario,
                        'activo': True
                    }
                })
            
            else:
                # Lógica original para otros estados (Faltante, NoHecho, NoFaltante)
                # Primero, marcar como inactivos todos los registros previos para este CODLINEA_GF
                print(f"🔄 Marcando registros anteriores como inactivos para CODLINEA: {codlinea}, GFH: {gfh}")
                cursor.execute("""
                    UPDATE [Digitalizacion].[CAB].[DatosUserCAB]
                    SET Activo = 0
                    WHERE CODLINEA = ? AND GFH = ?
                """, (codlinea, gfh))
                
                affected_rows = cursor.rowcount
                print(f"✅ Marcados como inactivos: {affected_rows} registros")
                
                # Ahora insertar el nuevo registro como activo
                print(f"💾 Insertando nuevo registro: ESTADO='{estado}', Activo=1, Fecha={fecha}, Turno={turno}")
                
                # Para estado NoHecho, incluir valor -100 en Realizacion
                if estado == 'NoHecho':
                    print(f"💾 Insertando registro NoHecho con Realizacion=-100, Operario={operario}")
                    cursor.execute("""
                        INSERT INTO [Digitalizacion].[CAB].[DatosUserCAB] 
                        (CODLINEA, GFH, ESTADO, Realizacion, Activo, Fecha, Turno, Operario)
                        VALUES (?, ?, ?, -100, 1, ?, ?, ?)
                    """, (codlinea, gfh, estado, fecha, turno, operario))
                elif estado == 'Faltante':
                    # NUEVO: Para estado Faltante, incluir el texto del faltante
                    print(f"💾 Insertando registro Faltante con texto: '{texto_faltante}', Operario={operario}")
                    cursor.execute("""
                        INSERT INTO [Digitalizacion].[CAB].[DatosUserCAB] 
                        (CODLINEA, GFH, ESTADO, Faltante, Activo, Fecha, Turno, Operario)
                        VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    """, (codlinea, gfh, estado, texto_faltante, fecha, turno, operario))
                else:
                    print(f"💾 Insertando registro {estado}, Operario={operario}")
                    cursor.execute("""
                        INSERT INTO [Digitalizacion].[CAB].[DatosUserCAB] 
                        (CODLINEA, GFH, ESTADO, Activo, Fecha, Turno, Operario)
                        VALUES (?, ?, ?, 1, ?, ?, ?)
                    """, (codlinea, gfh, estado, fecha, turno, operario))
                
                conn.commit()
                
                # Obtener el ID del registro recién creado
                cursor.execute("SELECT @@IDENTITY")
                nuevo_id = cursor.fetchone()[0]
                
                print(f"✅ Estado '{estado}' registrado exitosamente - ID: {nuevo_id}")
                print(f"📊 Detalles del registro:")
                print(f"   - ID: {nuevo_id}")
                print(f"   - CODLINEA: {codlinea}")
                print(f"   - GFH: {gfh}")
                print(f"   - ESTADO: {estado}")
                print(f"   - Fecha: {fecha}")
                print(f"   - Turno: {turno}")
                print(f"   - Operario: {operario}")
                print(f"   - Activo: 1")
                
                if estado in ['NoHecho', 'NoFaltante']:
                    print(f"🔄 ESTADO NEGATIVO REGISTRADO: Se desmarcó un checkbox y se registró '{estado}'")
                else:
                    print(f"✅ ESTADO POSITIVO REGISTRADO: Se marcó un checkbox y se registró '{estado}'")
                
                response_data = {
                    'success': True,
                    'message': f'Estado {estado} registrado exitosamente',
                    'registro': {
                        'id': nuevo_id,
                        'codlinea': codlinea,
                        'gfh': gfh,
                        'estado': estado,
                        'fecha': fecha.strftime('%Y-%m-%d'),
                        'turno': turno,
                        'operario': operario,
                        'activo': True
                    }
                }
                
                # Agregar realizacion al response si es NoHecho
                if estado == 'NoHecho':
                    response_data['registro']['realizacion'] = -100
                    response_data['registro']['total_realizacion'] = -100
                
                # NUEVO: Agregar texto del faltante al response si es Faltante
                if estado == 'Faltante' and texto_faltante:
                    response_data['registro']['texto_faltante'] = texto_faltante
                
                return jsonify(response_data)
        
    except Exception as e:
        print(f"💥 Error registrando estado: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/obtener-realizacion', methods=['GET'])
def obtener_realizacion():
    """Obtener el progreso total (suma de Realizacion) para un CODLINEA y GFH específicos"""
    try:
        # Obtener parámetros
        codlinea = request.args.get('codlinea', '').strip()
        gfh = request.args.get('gfh', '').strip()
        
        print(f"📥 Solicitud obtener-realizacion: CODLINEA='{codlinea}', GFH='{gfh}'")
        
        # Validar datos requeridos
        if not codlinea or not gfh:
            print(f"❌ Error: Faltan parámetros requeridos - CODLINEA: {bool(codlinea)}, GFH: {bool(gfh)}")
            return jsonify({
                'success': False, 
                'message': 'CODLINEA y GFH son requeridos'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Consultar la suma total de Realizacion para el CODLINEA y GFH específicos
            cursor.execute("""
                SELECT ISNULL(SUM(Realizacion), 0) as total_realizacion
                FROM [Digitalizacion].[CAB].[DatosUserCAB]
                WHERE CODLINEA = ? AND GFH = ?
            """, (codlinea, gfh))
            
            resultado = cursor.fetchone()
            total_realizacion = float(resultado[0]) if resultado and resultado[0] is not None else 0.0
            
            print(f"✅ Progreso obtenido para CODLINEA={codlinea}, GFH={gfh}: {total_realizacion}%")
            
            return jsonify({
                'success': True,
                'total_realizacion': total_realizacion,
                'codlinea': codlinea,
                'gfh': gfh
            })
        
    except Exception as e:
        print(f"💥 Error obteniendo realizacion: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/obtener-estados-activos', methods=['GET'])
def obtener_estados_activos():
    """Obtener estados activos para un puesto específico o filtros dados"""
    try:
        # Obtener parámetros de filtros
        anos = request.args.getlist('anos[]')
        semanas = request.args.getlist('semanas[]')
        puesto = request.args.get('puesto', '').strip()
        
        if not puesto:
            return jsonify({
                'success': False, 
                'message': 'El puesto es requerido'
            }), 400

        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Consulta para obtener estados activos usando el campo Activo
            sql_base = """
                SELECT 
                    d.CODLINEA,
                    d.GFH,
                    d.ESTADO,
                    d.Fecha,
                    d.Turno,
                    d.Faltante,
                    p.NumeroPedido,
                    p.CodigoPieza,
                    p.DESCRIPCIONPIEZA
                FROM [Digitalizacion].[CAB].[DatosUserCAB] d
                INNER JOIN [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas] p 
                    ON d.CODLINEA = p.CODLINEA AND d.GFH = p.GFH
                WHERE d.Activo = 1 
                AND p.PUESTO = ?
            """
            
            parametros = [puesto]
            condiciones_adicionales = []
            
            # Agregar filtros de años y semanas si están presentes
            if anos:
                anos_validos = [ano for ano in anos if ano.strip()]
                if anos_validos:
                    placeholders_anos = ','.join(['?' for _ in anos_validos])
                    condiciones_adicionales.append(f"p.Año IN ({placeholders_anos})")
                    parametros.extend(anos_validos)
            
            if semanas:
                semanas_validas = [semana for semana in semanas if semana.strip()]
                if semanas_validas:
                    placeholders_semanas = ','.join(['?' for _ in semanas_validas])
                    condiciones_adicionales.append(f"p.NumSemana IN ({placeholders_semanas})")
                    parametros.extend(semanas_validas)
            
            # Construir SQL final
            if condiciones_adicionales:
                sql_final = sql_base + " AND " + " AND ".join(condiciones_adicionales)
            else:
                sql_final = sql_base
            
            sql_final += " ORDER BY d.Fecha DESC, d.Turno"
            
            print(f"🔍 DEBUG - SQL para estados activos: {sql_final}")
            print(f"🔍 DEBUG - Parámetros: {parametros}")
            
            cursor.execute(sql_final, parametros)
            resultados = cursor.fetchall()
            
            print(f"🔍 DEBUG - Resultados encontrados: {len(resultados)}")
            for i, row in enumerate(resultados[:5]):  # Mostrar solo los primeros 5 para debug
                print(f"  📊 Fila {i+1}: CODLINEA={row[0]}, GFH={row[1]}, ESTADO={row[2]}")
            
            # Convertir resultados a formato JSON
            estados = {}
            for row in resultados:
                clave_item = f"{row[0]}_{row[1]}"  # CODLINEA_GFH
                estados[clave_item] = {
                    'CODLINEA': row[0],
                    'GFH': row[1],
                    'estado': row[2],
                    'fecha': row[3].strftime('%Y-%m-%d') if row[3] else None,
                    'turno': row[4],
                    'texto_faltante': row[5] if row[5] else '',  # NUEVO: Incluir texto del faltante
                    'NumeroPedido': row[6],
                    'CodigoPieza': row[7],
                    'DescripcionPieza': row[8]
                }
            
            return jsonify({
                'success': True,
                'estados': estados,
                'total': len(estados),
                'filtros_aplicados': {
                    'puesto': puesto,
                    'anos': anos,
                    'semanas': semanas
                }
            })
        
    except Exception as e:
        print(f"Error obteniendo estados activos: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/historial-estados', methods=['GET'])
def obtener_historial_estados():
    """Obtener historial completo de cambios de estado para una orden específica"""
    try:
        codlinea = request.args.get('codlinea', '').strip()
        gfh = request.args.get('gfh', '').strip()
        
        if not codlinea or not gfh:
            return jsonify({
                'success': False, 
                'message': 'CODLINEA y GFH son requeridos'
            }), 400

        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    ID,
                    CODLINEA,
                    GFH,
                    CODLINEA_GF,
                    ESTADO,
                    Activo,
                    Fecha,
                    Turno
                FROM [Digitalizacion].[CAB].[DatosUserCAB]
                WHERE CODLINEA = ? AND GFH = ?
                ORDER BY ID DESC
            """, (codlinea, gfh))
            
            resultados = cursor.fetchall()
            
            historial = []
            for row in resultados:
                historial.append({
                    'id': row[0],
                    'codlinea': row[1],
                    'gfh': row[2],
                    'codlinea_gf': row[3],
                    'estado': row[4],
                    'activo': bool(row[5]),
                    'fecha': row[6].strftime('%Y-%m-%d') if row[6] else None,
                    'turno': row[7]
                })
            
            return jsonify({
                'success': True,
                'historial': historial,
                'total': len(historial)
            })
        
    except Exception as e:
        print(f"Error obteniendo historial: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/puestos', methods=['GET'])
def obtener_puestos():
    """Obtener lista de puestos únicos desde tabla Puestos"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Primero probar una consulta simple para verificar la conexión
            try:
                cursor.execute("SELECT 1 as test")
                test_result = cursor.fetchone()
                print(f"Test de conexión: {test_result}")
            except Exception as e:
                print(f"Error en test de conexión: {e}")
                return jsonify({'success': False, 'message': f'Error de test: {str(e)}'}), 500
            
            # Ahora intentar la consulta real
            try:
                cursor.execute("""
                    SELECT DISTINCT Nombre_Puesto 
                    FROM [Digitalizacion].[CAB].[Puestos]
                    WHERE Nombre_Puesto IS NOT NULL 
                    ORDER BY Nombre_Puesto
                """)
                
                resultados = cursor.fetchall()
                puestos = [row[0] for row in resultados if row[0]]  # Filtrar valores NULL
                
                print(f"Puestos encontrados desde tabla Puestos: {len(puestos)}")
                
                return jsonify({
                    'success': True,
                    'puestos': puestos,
                    'total': len(puestos)
                })
                
            except Exception as e:
                print(f"Error en consulta de puestos desde tabla Puestos: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error del servidor: {str(e)}'
                }), 500
            
    except Exception as e:
        print(f"Error general obteniendo puestos: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

@app.route('/api/anos', methods=['GET'])
def obtener_anos():
    """Obtener lista de años únicos desde Fact_Procesos_Tiempos_Cabinas"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Intentar la consulta de años
            try:
                cursor.execute("""
                    SELECT DISTINCT Año 
                    FROM [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas]
                    WHERE Año IS NOT NULL 
                    ORDER BY Año DESC
                """)
                
                resultados = cursor.fetchall()
                anos = [str(row[0]) for row in resultados if row[0]]  # Convertir a string y filtrar NULL
                
                print(f"Años encontrados: {len(anos)} - {anos}")
                
                return jsonify({
                    'success': True,
                    'anos': anos,
                    'total': len(anos)
                })
                
            except Exception as e:
                print(f"Error en consulta de años: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error del servidor: {str(e)}'
                }), 500
            
    except Exception as e:
        print(f"Error general obteniendo años: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

@app.route('/api/semanas', methods=['GET'])
def obtener_semanas():
    """Obtener lista de semanas únicas desde Fact_Procesos_Tiempos_Cabinas"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Intentar la consulta de semanas
            try:
                cursor.execute("""
                    SELECT DISTINCT NumSemana 
                    FROM [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas]
                    WHERE NumSemana IS NOT NULL 
                    ORDER BY NumSemana ASC
                """)
                
                resultados = cursor.fetchall()
                # Parsear resultados preservando el string original (ej: '02')
                # Ordenar numéricamente para que la lista se vea bien 
                # (evita que '10' salga antes que '2', pero mantiene '02')
                semanas = sorted(
                    [str(row[0]) for row in resultados if row[0]],
                    key=lambda x: int(x) if x.isdigit() else x
                )
                
                print(f"Semanas encontradas: {len(semanas)} - {semanas}")
                
                return jsonify({
                    'success': True,
                    'semanas': semanas,
                    'total': len(semanas)
                })
                
            except Exception as e:
                print(f"Error en consulta de semanas: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error del servidor: {str(e)}'
                }), 500
            
    except Exception as e:
        print(f"Error general obteniendo semanas: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

@app.route('/api/codigos-puesto-disponibles', methods=['GET'])
def obtener_codigos_puesto_disponibles():
    """Obtener lista de códigos de puesto únicos desde Fact_Procesos_Tiempos_Cabinas"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Obtener códigos únicos excluyendo NULL
            cursor.execute("""
                SELECT DISTINCT PUESTO 
                FROM [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas]
                WHERE PUESTO IS NOT NULL 
                AND PUESTO != ''
                ORDER BY PUESTO
            """)
            
            resultados = cursor.fetchall()
            
            # Formatear resultados
            codigos = [row[0].strip() for row in resultados if row[0] and row[0].strip()]
            
            print(f"✅ Códigos de puesto disponibles obtenidos: {len(codigos)} códigos")
            
            return jsonify({
                'success': True,
                'codigos': codigos,
                'total': len(codigos)
            })
            
    except Exception as e:
        print(f"❌ Error obteniendo códigos de puesto: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

@app.route('/api/puesto-columnas/<codigo_puesto>', methods=['GET'])
def obtener_columnas_puesto(codigo_puesto):
    """Obtener las columnas configuradas para un puesto específico usando su código"""
    try:
        print(f"🔍 Buscando columnas para puesto: {codigo_puesto}")
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # PASO 1: Obtener ID_Puesto usando el Codigo_Puesto
            print(f"📋 PASO 1: Buscando ID_Puesto para código '{codigo_puesto}'")
            cursor.execute("""
                SELECT ID_Puesto, Nombre_Puesto, ColorPantalla 
                FROM [Digitalizacion].[CAB].[Puestos] 
                WHERE Codigo_Puesto = ?
            """, (codigo_puesto,))
            
            puesto_info = cursor.fetchone()
            if not puesto_info:
                print(f"❌ No se encontró el puesto con código: {codigo_puesto}")
                # Devolver columnas por defecto si no se encuentra el puesto
                columnas_defecto = ['numeroPedido', 'descripcionPieza', 'tiempoTotal', 'modelo']
                return jsonify({
                    'success': True,
                    'columnas': columnas_defecto,
                    'total': len(columnas_defecto),
                    'puesto_codigo': codigo_puesto,
                    'puesto_nombre': 'Desconocido',
                    'color_pantalla': '#87CEEB',  # Azul claro por defecto
                    'message': f'Puesto {codigo_puesto} no encontrado, usando columnas por defecto'
                })
            
            id_puesto, nombre_puesto, color_pantalla = puesto_info
            print(f"✅ Puesto encontrado: ID={id_puesto}, Nombre='{nombre_puesto}', Codigo='{codigo_puesto}', Color='{color_pantalla}'")
            
            # PASO 2: Obtener las columnas configuradas para este ID_Puesto ordenadas
            # Traemos AMBOS campos: Columna (código original) y Nombre (para mostrar en headers)
            print(f"📋 PASO 2: Buscando columnas configuradas para ID_Puesto={id_puesto}")
            cursor.execute("""
                SELECT Columna, Nombre, ISNULL(Tabla, 'Fact_Procesos_Tiempos_Cabinas') as Tabla
                FROM [Digitalizacion].[CAB].[PuestosColumnas]
                WHERE ID_Puesto = ?
                ORDER BY ISNULL(Orden, 999), Orden, Columna
            """, (id_puesto,))
            
            resultados = cursor.fetchall()
            columnas = [row[0] for row in resultados if row[0]]  # Códigos originales para buscar datos
            columnas_nombres = [row[1] if row[1] else row[0] for row in resultados if row[0]]  # Nombres para headers
            columnas_tablas = [row[2] if len(row) > 2 else 'Fact_Procesos_Tiempos_Cabinas' for row in resultados if row[0]]  # Tablas de origen
            
            print(f"📊 Columnas encontradas: {len(columnas)} - {columnas}")
            
            # Si no hay columnas configuradas, usar columnas por defecto
            if not columnas:
                print(f"⚠️ No hay columnas configuradas para {codigo_puesto}, usando columnas por defecto")
                columnas_defecto = ['numeroPedido', 'descripcionPieza', 'tiempoTotal', 'modelo']
                return jsonify({
                    'success': True,
                    'columnas': columnas_defecto,
                    'total': len(columnas_defecto),
                    'puesto_codigo': codigo_puesto,
                    'puesto_nombre': nombre_puesto,
                    'puesto_id': id_puesto,
                    'color_pantalla': color_pantalla or '#87CEEB',  # Azul claro por defecto si es NULL
                    'message': 'No hay columnas configuradas, usando columnas por defecto'
                })
            
            return jsonify({
                'success': True,
                'columnas': columnas,  # Códigos originales para buscar datos en ORDENES
                'columnas_nombres': columnas_nombres,  # Nombres para mostrar en headers
                'columnas_tablas': columnas_tablas,  # Tablas de origen de cada columna
                'total': len(columnas),
                'puesto_codigo': codigo_puesto,
                'puesto_nombre': nombre_puesto,
                'puesto_id': id_puesto,
                'color_pantalla': color_pantalla or '#87CEEB',  # Azul claro por defecto si es NULL
                'message': f'Columnas configuradas para {nombre_puesto}'
            })
            
    except Exception as e:
        print(f"❌ Error obteniendo columnas para puesto {codigo_puesto}: {e}")
        # En caso de error, devolver columnas por defecto
        columnas_defecto = ['numeroPedido', 'descripcionPieza', 'tiempoTotal', 'modelo']
        return jsonify({
            'success': True,
            'columnas': columnas_defecto,
            'total': len(columnas_defecto),
            'puesto_codigo': codigo_puesto,
            'puesto_nombre': 'Error',
            'color_pantalla': '#87CEEB',  # Azul claro por defecto en caso de error
            'message': f'Error al consultar BD, usando columnas por defecto: {str(e)}'
        }), 200  # Devolver 200 para que el frontend funcione

@app.route('/api/ordenes', methods=['GET'])
def obtener_ordenes():
    """Obtener órdenes de trabajo filtradas por año, semana y puesto desde Fact_Procesos_Tiempos_Cabinas"""
    try:
        # Obtener parámetros de filtros
        anos = request.args.getlist('anos[]')  # Lista de años
        semanas = request.args.getlist('semanas[]')  # Lista de semanas
        puesto = request.args.get('puesto', '').strip()  # Puesto individual
        
        print(f"Filtros recibidos - Años: {anos}, Semanas: {semanas}, Puesto: {puesto}")
        
        # Validar que tengamos al menos un filtro
        if not anos and not semanas:
            return jsonify({
                'success': False, 
                'message': 'Debe seleccionar al menos un año o semana'
            }), 400
            
        if not puesto:
            return jsonify({
                'success': False, 
                'message': 'El puesto es requerido'
            }), 400

        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            try:
                # Construir la consulta SQL con filtros dinámicos - OBTENER TODAS LAS COLUMNAS
                sql_base = """
                    SELECT TOP 1000 * 
                    FROM [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas]
                    WHERE PUESTO = ?
                """
                
                parametros = [puesto]
                condiciones_adicionales = []
                
                # Agregar filtro de años si está presente
                if anos:
                    anos_validos = [ano for ano in anos if ano.strip()]
                    if anos_validos:
                        placeholders_anos = ','.join(['?' for _ in anos_validos])
                        condiciones_adicionales.append(f"Año IN ({placeholders_anos})")
                        parametros.extend(anos_validos)
                
                # Agregar filtro de semanas si está presente
                if semanas:
                    # Normalizar semanas para asegurar compatibilidad con formatos '2' y '02'
                    semanas_expandidas = []
                    for s in semanas:
                        s_limpia = s.strip()
                        if not s_limpia:
                            continue
                        
                        # Agregar el valor original
                        semanas_expandidas.append(s_limpia)
                        
                        # Si es un solo dígito, agregar versión con cero (ej: '2' -> '02')
                        if len(s_limpia) == 1 and s_limpia.isdigit():
                            semanas_expandidas.append(f"0{s_limpia}")
                        
                        # Si tiene cero delante, agregar versión sin cero (ej: '02' -> '2')
                        elif len(s_limpia) == 2 and s_limpia.startswith('0') and s_limpia[1].isdigit():
                            semanas_expandidas.append(s_limpia[1])
                    
                    # Eliminar duplicados manteniendo orden
                    semanas_validas = list(dict.fromkeys(semanas_expandidas))
                    
                    if semanas_validas:
                        placeholders_semanas = ','.join(['?' for _ in semanas_validas])
                        condiciones_adicionales.append(f"NumSemana IN ({placeholders_semanas})")
                        parametros.extend(semanas_validas)
                
                # Construir SQL final
                if condiciones_adicionales:
                    sql_final = sql_base + " AND " + " AND ".join(condiciones_adicionales)
                else:
                    sql_final = sql_base
                
                # Agregar ordenamiento para asegurar que se muestren los datos más recientes (2025-2026)
                # Esto soluciona el problema de que el TOP 1000 oculte los registros nuevos
                sql_final += " ORDER BY [Año] DESC, [NumSemana] DESC, [NumeroPedido] DESC"
                
                print(f"SQL a ejecutar: {sql_final}")
                print(f"Parámetros: {parametros}")
                
                cursor.execute(sql_final, parametros)
                resultados = cursor.fetchall()
                
                # Obtener los nombres de las columnas directamente del cursor
                nombres_columnas = [column[0] for column in cursor.description]
                print(f"Nombres de columnas de la BD: {nombres_columnas}")
                
                # Convertir resultados a formato JSON usando nombres exactos de columnas
                ordenes = []
                for row in resultados:
                    orden = {}
                    for i, valor in enumerate(row):
                        nombre_columna = nombres_columnas[i]
                        orden[nombre_columna] = valor
                    
                    ordenes.append(orden)
                
                print(f"Órdenes encontradas: {len(ordenes)}")
                
                # ============================================================
                # Enriquecer órdenes con datos de DatosPedidos (JOIN por NumeroPedido = Pedido)
                # ============================================================
                numeros_pedido = list(set(
                    str(o.get('NumeroPedido', '')) for o in ordenes 
                    if o.get('NumeroPedido')
                ))
                
                if numeros_pedido:
                    try:
                        from decimal import Decimal
                        cursor2 = conn.cursor()
                        
                        # Obtener columnas de DatosPedidos
                        cursor2.execute("""
                            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = 'CAB' AND TABLE_NAME = 'DatosPedidos'
                            ORDER BY ORDINAL_POSITION
                        """)
                        columnas_dp = [row[0] for row in cursor2.fetchall()]
                        
                        if not columnas_dp:
                            cursor2.execute("SELECT TOP 1 * FROM [Digitalizacion].[CAB].[DatosPedidos]")
                            columnas_dp = [col[0] for col in cursor2.description]
                        
                        if columnas_dp:
                            placeholders = ','.join(['?' for _ in numeros_pedido])
                            columnas_sql = ', '.join([f'[{c}]' for c in columnas_dp])
                            
                            cursor2.execute(f"""
                                SELECT {columnas_sql}
                                FROM [Digitalizacion].[CAB].[DatosPedidos]
                                WHERE Pedido IN ({placeholders})
                            """, numeros_pedido)
                            
                            dp_rows = cursor2.fetchall()
                            print(f"📦 PuestosCAB - DatosPedidos: {len(dp_rows)} filas para {len(numeros_pedido)} pedidos")
                            
                            datos_por_pedido = {}
                            for row in dp_rows:
                                pedido_key = str(row[0]) if row[0] is not None else None
                                if pedido_key:
                                    datos_por_pedido[pedido_key] = {}
                                    for i, col_name in enumerate(columnas_dp):
                                        val = row[i]
                                        if val is None:
                                            pass
                                        elif isinstance(val, Decimal):
                                            val = float(val)
                                        elif isinstance(val, (bytes, bytearray)):
                                            val = str(val)
                                        elif hasattr(val, 'isoformat'):
                                            val = val.isoformat()
                                        elif isinstance(val, (str, int, float, bool)):
                                            pass
                                        else:
                                            val = str(val)
                                        datos_por_pedido[pedido_key][col_name] = val
                            
                            for orden in ordenes:
                                num = str(orden.get('NumeroPedido', ''))
                                dp_data = datos_por_pedido.get(num, None)
                                orden['DatosPedido'] = dp_data
                                # También copiar campos al nivel superior para acceso directo
                                if dp_data:
                                    for k, v in dp_data.items():
                                        if k not in orden:  # No sobrescribir campos existentes
                                            orden[k] = v
                            
                            print(f"📦 Enriquecidas {sum(1 for o in ordenes if o.get('DatosPedido'))} órdenes con DatosPedidos")
                        
                        cursor2.close()
                    except Exception as e:
                        print(f"⚠️ Error enriqueciendo órdenes con DatosPedidos (no crítico): {e}")
                        import traceback
                        traceback.print_exc()
                        for orden in ordenes:
                            orden['DatosPedido'] = None
                
                return jsonify({
                    'success': True,
                    'ordenes': ordenes,
                    'total': len(ordenes),
                    'filtros_aplicados': {
                        'puesto': puesto,
                        'anos': anos,
                        'semanas': semanas
                    }
                })
                
            except Exception as e:
                print(f"Error en consulta de órdenes: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error en consulta de base de datos: {str(e)}'
                }), 500
            
    except Exception as e:
        print(f"Error general obteniendo órdenes: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

@app.route('/api/puestos-mapping', methods=['GET'])
def obtener_puestos_mapping():
    """Obtener mapeo de Nombre_Puesto → Codigo_Puesto desde tabla Puestos"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT Nombre_Puesto, Codigo_Puesto 
                    FROM [Digitalizacion].[CAB].[Puestos]
                    WHERE Nombre_Puesto IS NOT NULL AND Codigo_Puesto IS NOT NULL
                    ORDER BY Nombre_Puesto
                """)
                
                resultados = cursor.fetchall()
                
                # Crear diccionario de mapeo
                mapping = {}
                puestos_info = []
                
                for row in resultados:
                    nombre = row[0]
                    codigo = row[1]
                    mapping[nombre] = codigo
                    puestos_info.append({
                        'nombre': nombre,
                        'codigo': codigo
                    })
                
                print(f"Mapeo de puestos obtenido: {mapping}")
                
                return jsonify({
                    'success': True,
                    'mapping': mapping,
                    'puestos': puestos_info,
                    'total': len(puestos_info)
                })
                
            except Exception as e:
                print(f"Error en consulta de mapeo de puestos: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error del servidor: {str(e)}'
                }), 500
            
    except Exception as e:
        print(f"Error general obteniendo mapeo de puestos: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

@app.route('/api/crear-puesto', methods=['POST'])
def crear_puesto():
    """Crear un nuevo puesto CAB con configuración de columnas"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        nombre_puesto = data.get('nombre_puesto', '').strip()
        codigo_puesto = data.get('codigo_puesto', '').strip()
        columnas_seleccionadas = data.get('columnas', [])  # Lista de columnas a mostrar
        color_pantalla = data.get('color_pantalla', '#87CEEB')  # Color por defecto azul claro
        
        if not nombre_puesto or not codigo_puesto:
            return jsonify({'success': False, 'message': 'Nombre y código de puesto son requeridos'}), 400
        
        # Guardar en la tabla CAB.Puestos
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Verificar si ya existe un puesto con ese código
            cursor.execute("""
                SELECT COUNT(*) 
                FROM [Digitalizacion].[CAB].[Puestos] 
                WHERE Codigo_Puesto = ?
            """, (codigo_puesto,))
            
            if cursor.fetchone()[0] > 0:
                return jsonify({'success': False, 'message': 'Ya existe un puesto con ese código'}), 400
            
            # Insertar el nuevo puesto
            cursor.execute("""
                INSERT INTO [Digitalizacion].[CAB].[Puestos] 
                (Nombre_Puesto, Codigo_Puesto, ColorPantalla)
                VALUES (?, ?, ?)
            """, (nombre_puesto, codigo_puesto, color_pantalla))
            
            # Obtener el ID del puesto recién creado
            cursor.execute("SELECT @@IDENTITY")
            nuevo_id = cursor.fetchone()[0]
            
            # Guardar las columnas seleccionadas en la tabla PuestosColumnas con orden y nombres personalizados
            if columnas_seleccionadas:
                for index, columna_item in enumerate(columnas_seleccionadas):
                    # Manejar tanto formato string (compatibilidad) como objeto (nuevo)
                    if isinstance(columna_item, str):
                        # Formato anterior - solo código
                        columna_codigo = columna_item
                        columna_nombre = columna_item  # Nombre igual al código
                        columna_tabla = 'Fact_Procesos_Tiempos_Cabinas'  # Default
                    elif isinstance(columna_item, dict):
                        # Nuevo formato - objeto con código y nombre
                        columna_codigo = columna_item.get('codigo', '')
                        columna_nombre = columna_item.get('nombre', columna_codigo)  # Si no hay nombre, usar código
                        columna_tabla = columna_item.get('tabla', 'Fact_Procesos_Tiempos_Cabinas')  # Tabla de origen
                    else:
                        continue  # Saltar elementos inválidos
                    
                    cursor.execute("""
                        INSERT INTO [Digitalizacion].[CAB].[PuestosColumnas] 
                        (ID_Puesto, Columna, Orden, Nombre, Tabla)
                        VALUES (?, ?, ?, ?, ?)
                    """, (nuevo_id, columna_codigo, index + 1, columna_nombre, columna_tabla))
            
            conn.commit()
            
            print(f"Nuevo puesto creado - ID: {nuevo_id}, Nombre: {nombre_puesto}, Código: {codigo_puesto}, Color: {color_pantalla}")
            print(f"Columnas configuradas: {columnas_seleccionadas}")
            
            return jsonify({
                'success': True,
                'message': 'Puesto creado exitosamente',
                'puesto': {
                    'id': nuevo_id,
                    'nombre': nombre_puesto,
                    'codigo': codigo_puesto,
                    'columnas': columnas_seleccionadas,
                    'color_pantalla': color_pantalla
                }
            })
        
    except Exception as e:
        print(f"Error creando puesto: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/modificar-puesto', methods=['PUT'])
def modificar_puesto():
    """Modificar un puesto CAB existente con configuración de columnas"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        id_puesto = data.get('id_puesto')
        nombre_puesto = data.get('nombre_puesto', '').strip()
        codigo_puesto = data.get('codigo_puesto', '').strip()
        columnas_seleccionadas = data.get('columnas', [])
        color_pantalla = data.get('color_pantalla', '#87CEEB')  # Color por defecto azul claro
        
        if not id_puesto or not nombre_puesto or not codigo_puesto:
            return jsonify({'success': False, 'message': 'ID, nombre y código de puesto son requeridos'}), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Verificar que el puesto existe
            cursor.execute("""
                SELECT ID_Puesto 
                FROM [Digitalizacion].[CAB].[Puestos] 
                WHERE ID_Puesto = ?
            """, (id_puesto,))
            
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': 'Puesto no encontrado'}), 404
            
            # Verificar que no exista otro puesto con el mismo código (excepto el actual)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM [Digitalizacion].[CAB].[Puestos] 
                WHERE Codigo_Puesto = ? AND ID_Puesto != ?
            """, (codigo_puesto, id_puesto))
            
            if cursor.fetchone()[0] > 0:
                return jsonify({'success': False, 'message': 'Ya existe otro puesto con ese código'}), 400
            
            # Actualizar los datos del puesto
            cursor.execute("""
                UPDATE [Digitalizacion].[CAB].[Puestos] 
                SET Nombre_Puesto = ?, Codigo_Puesto = ?, ColorPantalla = ?
                WHERE ID_Puesto = ?
            """, (nombre_puesto, codigo_puesto, color_pantalla, id_puesto))
            
            # Eliminar las columnas existentes del puesto
            cursor.execute("""
                DELETE FROM [Digitalizacion].[CAB].[PuestosColumnas] 
                WHERE ID_Puesto = ?
            """, (id_puesto,))
            
            # Insertar las nuevas columnas seleccionadas con orden y nombres personalizados
            if columnas_seleccionadas:
                for index, columna_item in enumerate(columnas_seleccionadas):
                    # Manejar tanto formato string (compatibilidad) como objeto (nuevo)
                    if isinstance(columna_item, str):
                        # Formato anterior - solo código
                        columna_codigo = columna_item
                        columna_nombre = columna_item  # Nombre igual al código
                        columna_tabla = 'Fact_Procesos_Tiempos_Cabinas'  # Default
                    elif isinstance(columna_item, dict):
                        # Nuevo formato - objeto con código y nombre
                        columna_codigo = columna_item.get('codigo', '')
                        columna_nombre = columna_item.get('nombre', columna_codigo)  # Si no hay nombre, usar código
                        columna_tabla = columna_item.get('tabla', 'Fact_Procesos_Tiempos_Cabinas')  # Tabla de origen
                    else:
                        continue  # Saltar elementos inválidos
                    
                    cursor.execute("""
                        INSERT INTO [Digitalizacion].[CAB].[PuestosColumnas] 
                        (ID_Puesto, Columna, Orden, Nombre, Tabla)
                        VALUES (?, ?, ?, ?, ?)
                    """, (id_puesto, columna_codigo, index + 1, columna_nombre, columna_tabla))
            
            conn.commit()
            
            print(f"Puesto modificado - ID: {id_puesto}, Nombre: {nombre_puesto}, Código: {codigo_puesto}, Color: {color_pantalla}")
            print(f"Columnas configuradas: {columnas_seleccionadas}")
            
            return jsonify({
                'success': True,
                'message': 'Puesto modificado exitosamente',
                'puesto': {
                    'id': id_puesto,
                    'nombre': nombre_puesto,
                    'codigo': codigo_puesto,
                    'columnas': columnas_seleccionadas,
                    'color_pantalla': color_pantalla
                }
            })
        
    except Exception as e:
        print(f"Error modificando puesto: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/puesto-datos/<nombre_puesto>', methods=['GET'])
def obtener_datos_puesto(nombre_puesto):
    """Obtener datos completos de un puesto específico para modificación"""
    try:
        print(f"🔍 Buscando datos para puesto: {nombre_puesto}")
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Obtener datos del puesto incluyendo columnas configuradas
            cursor.execute("""
                SELECT p.ID_Puesto, p.Nombre_Puesto, p.Codigo_Puesto, p.ColorPantalla
                FROM [Digitalizacion].[CAB].[Puestos] p
                WHERE p.Nombre_Puesto = ?
            """, (nombre_puesto,))
            
            puesto_data = cursor.fetchone()
            if not puesto_data:
                return jsonify({'success': False, 'message': 'Puesto no encontrado'}), 404
            
            id_puesto, nombre, codigo, color_pantalla = puesto_data
            
            # Obtener columnas configuradas para este puesto con nombres personalizados
            cursor.execute("""
                SELECT Columna, Nombre, ISNULL(Tabla, 'Fact_Procesos_Tiempos_Cabinas') as Tabla
                FROM [Digitalizacion].[CAB].[PuestosColumnas] 
                WHERE ID_Puesto = ?
                ORDER BY Orden
            """, (id_puesto,))
            
            columnas_result = cursor.fetchall()
            # Crear objetos con código, nombre personalizado y tabla de origen
            columnas = []
            for row in columnas_result:
                columna_codigo = row[0]
                columna_nombre = row[1] if row[1] else columna_codigo  # Si no hay nombre personalizado, usar el código
                columna_tabla = row[2] if len(row) > 2 else 'Fact_Procesos_Tiempos_Cabinas'
                columnas.append({
                    'codigo': columna_codigo,
                    'nombre': columna_nombre,
                    'tabla': columna_tabla
                })
            
            print(f"✅ Datos del puesto obtenidos - ID: {id_puesto}, Código: {codigo}, Color: {color_pantalla}")
            
            return jsonify({
                'success': True,
                'puesto': {
                    'id': id_puesto,
                    'nombre': nombre,
                    'codigo': codigo,
                    'columnas': columnas,
                    'color_pantalla': color_pantalla or '#87CEEB'  # Color por defecto si es NULL
                }
            })
            
    except Exception as e:
        print(f"❌ Error obteniendo datos del puesto: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

@app.route('/api/eliminar-puesto/<int:id_puesto>', methods=['DELETE'])
def eliminar_puesto(id_puesto):
    """Eliminar un puesto CAB y su configuración de columnas"""
    try:
        if not id_puesto:
            return jsonify({'success': False, 'message': 'ID de puesto es requerido'}), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Verificar que el puesto existe y obtener su información
            cursor.execute("""
                SELECT Nombre_Puesto, Codigo_Puesto 
                FROM [Digitalizacion].[CAB].[Puestos] 
                WHERE ID_Puesto = ?
            """, (id_puesto,))
            
            puesto_info = cursor.fetchone()
            if not puesto_info:
                return jsonify({'success': False, 'message': 'Puesto no encontrado'}), 404
            
            nombre_puesto = puesto_info[0]
            codigo_puesto = puesto_info[1]
            
            # Primero eliminar las columnas asociadas al puesto
            cursor.execute("""
                DELETE FROM [Digitalizacion].[CAB].[PuestosColumnas] 
                WHERE ID_Puesto = ?
            """, (id_puesto,))
            
            columnas_eliminadas = cursor.rowcount
            
            # Luego eliminar el puesto
            cursor.execute("""
                DELETE FROM [Digitalizacion].[CAB].[Puestos] 
                WHERE ID_Puesto = ?
            """, (id_puesto,))
            
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': 'No se pudo eliminar el puesto'}), 500
            
            conn.commit()
            
            print(f"Puesto eliminado - ID: {id_puesto}, Nombre: {nombre_puesto}, Código: {codigo_puesto}")
            print(f"Columnas eliminadas: {columnas_eliminadas}")
            
            return jsonify({
                'success': True,
                'message': f'Puesto "{nombre_puesto}" eliminado exitosamente',
                'puesto_eliminado': {
                    'id': id_puesto,
                    'nombre': nombre_puesto,
                    'codigo': codigo_puesto,
                    'columnas_eliminadas': columnas_eliminadas
                }
            })
        
    except Exception as e:
        print(f"Error eliminando puesto: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/columnas-disponibles', methods=['GET'])
def obtener_columnas_disponibles():
    """Obtener lista de columnas disponibles desde Fact_Procesos_Tiempos_Cabinas y DatosPedidos"""
    try:
        # Primero, intentar agregar la columna Orden a PuestosColumnas si no existe
        try:
            with ConexionODBC('Digitalizacion') as conn:
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                                     WHERE TABLE_NAME = 'PuestosColumnas' 
                                     AND COLUMN_NAME = 'Orden'
                                     AND TABLE_SCHEMA = 'CAB')
                        BEGIN
                            ALTER TABLE [Digitalizacion].[CAB].[PuestosColumnas] 
                            ADD Orden INT NULL
                        END
                    """)
                    conn.commit()
                    print("✅ Columna 'Orden' verificada/creada en PuestosColumnas")
        except Exception as e:
            print(f"⚠️ Error verificando columna Orden: {e}")
        
        # Agregar columna Tabla a PuestosColumnas si no existe
        try:
            with ConexionODBC('Digitalizacion') as conn:
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                                     WHERE TABLE_NAME = 'PuestosColumnas' 
                                     AND COLUMN_NAME = 'Tabla'
                                     AND TABLE_SCHEMA = 'CAB')
                        BEGIN
                            ALTER TABLE [Digitalizacion].[CAB].[PuestosColumnas] 
                            ADD Tabla NVARCHAR(128) NULL
                        END
                    """)
                    conn.commit()
                    print("✅ Columna 'Tabla' verificada/creada en PuestosColumnas")
        except Exception as e:
            print(f"⚠️ Error verificando columna Tabla: {e}")
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            columnas_por_nombre = {}  # Diccionario para merge y deduplicación
            
            # ============================================================
            # 1. Obtener columnas de Fact_Procesos_Tiempos_Cabinas (PRIORITARIAS)
            # ============================================================
            try:
                cursor.execute("""
                    SELECT 
                        COLUMN_NAME,
                        DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'CAB' 
                    AND TABLE_NAME = 'Fact_Procesos_Tiempos_Cabinas'
                    ORDER BY ORDINAL_POSITION
                """)
                
                resultados_fact = cursor.fetchall()
                
                if not resultados_fact:
                    # Fallback: obtener desde cursor.description
                    cursor.execute("""
                        SELECT TOP 1 * FROM [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas]
                    """)
                    for col in cursor.description:
                        nombre_columna = col[0]
                        columnas_por_nombre[nombre_columna] = {
                            'codigo': nombre_columna,
                            'nombre': nombre_columna,
                            'tabla': 'Fact_Procesos_Tiempos_Cabinas',
                            'origen': 'Fact_Procesos_Tiempos_Cabinas'
                        }
                else:
                    for row in resultados_fact:
                        nombre_columna = row[0]
                        columnas_por_nombre[nombre_columna] = {
                            'codigo': nombre_columna,
                            'nombre': nombre_columna,
                            'tabla': 'Fact_Procesos_Tiempos_Cabinas',
                            'origen': 'Fact_Procesos_Tiempos_Cabinas'
                        }
                
                print(f"📊 Columnas Fact_Procesos_Tiempos_Cabinas: {len(columnas_por_nombre)}")
            except Exception as e:
                print(f"⚠️ Error obteniendo columnas de Fact_Procesos_Tiempos_Cabinas: {e}")
            
            # ============================================================
            # 2. Obtener columnas de DatosPedidos (complementarias, sin duplicar)
            # ============================================================
            try:
                cursor.execute("""
                    SELECT 
                        COLUMN_NAME,
                        DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = 'CAB' 
                    AND TABLE_NAME = 'DatosPedidos'
                    ORDER BY ORDINAL_POSITION
                """)
                
                resultados_datos = cursor.fetchall()
                
                if not resultados_datos:
                    # Fallback: obtener desde cursor.description
                    cursor.execute("""
                        SELECT TOP 1 * FROM [Digitalizacion].[CAB].[DatosPedidos]
                    """)
                    for col in cursor.description:
                        nombre_columna = col[0]
                        if nombre_columna not in columnas_por_nombre:
                            columnas_por_nombre[nombre_columna] = {
                                'codigo': nombre_columna,
                                'nombre': nombre_columna,
                                'tabla': 'DatosPedidos',
                                'origen': 'DatosPedidos'
                            }
                else:
                    for row in resultados_datos:
                        nombre_columna = row[0]
                        if nombre_columna not in columnas_por_nombre:
                            columnas_por_nombre[nombre_columna] = {
                                'codigo': nombre_columna,
                                'nombre': nombre_columna,
                                'tabla': 'DatosPedidos',
                                'origen': 'DatosPedidos'
                            }
                
                print(f"📊 Columnas DatosPedidos nuevas (no duplicadas): {len(columnas_por_nombre) - len([c for c in columnas_por_nombre.values() if c['tabla'] == 'Fact_Procesos_Tiempos_Cabinas'])}")
            except Exception as e:
                print(f"⚠️ Error obteniendo columnas de DatosPedidos: {e}")
            
            # Convertir diccionario a lista
            columnas_disponibles = list(columnas_por_nombre.values())
            
            print(f"📊 Total columnas disponibles (merge): {len(columnas_disponibles)}")
            
            return jsonify({
                'success': True,
                'columnas': columnas_disponibles,
                'total': len(columnas_disponibles),
                'tablas': ['Fact_Procesos_Tiempos_Cabinas', 'DatosPedidos']
            })
                
    except Exception as e:
        print(f"Error obteniendo columnas disponibles: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/puestos-creados', methods=['GET'])
def obtener_puestos_creados():
    """Obtener todos los puestos creados desde la tabla CAB.Puestos"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Obtener todos los puestos de la tabla
            cursor.execute("""
                SELECT ID_Puesto, Nombre_Puesto, Codigo_Puesto
                FROM [Digitalizacion].[CAB].[Puestos]
                ORDER BY ID_Puesto DESC
            """)
            
            resultados = cursor.fetchall()
            puestos = []
            
            for row in resultados:
                puestos.append({
                    'id': row[0],
                    'nombre': row[1],
                    'codigo': row[2]
                })
            
            return jsonify({
                'success': True,
                'puestos': puestos,
                'total': len(puestos)
            })
            
    except Exception as e:
        print(f"Error obteniendo puestos creados: {e}")
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500

@app.route('/api/lista-puestos-cab', methods=['GET'])
def obtener_lista_puestos_cab():
    """Obtener todos los nombres de puestos para mostrar como tarjetas en ListaPuestosCAB"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Obtener nombres únicos de puestos para mostrar como tarjetas
            cursor.execute("""
                SELECT DISTINCT Nombre_Puesto
                FROM [Digitalizacion].[CAB].[Puestos]
                WHERE Nombre_Puesto IS NOT NULL
                ORDER BY Nombre_Puesto
            """)
            
            resultados = cursor.fetchall()
            puestos = [row[0] for row in resultados if row[0]]  # Filtrar valores NULL
            
            print(f"Puestos para ListaPuestosCAB encontrados: {len(puestos)}")
            
            return jsonify({
                'success': True,
                'puestos': puestos,
                'total': len(puestos)
            })
            
    except Exception as e:
        print(f"Error obteniendo lista puestos CAB: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500

@app.route('/api/filtros-tiempos', methods=['GET'])
def obtener_filtros_tiempos():
    """Obtener años y semanas disponibles para filtros"""
    try:
        conexion = ConexionODBC()
        
        # Consulta para obtener años y semanas únicos
        query = """
        SELECT DISTINCT 
            [Año],
            [NumSemana]
        FROM [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas]
        WHERE [Año] IS NOT NULL AND [NumSemana] IS NOT NULL
        ORDER BY [Año] DESC, [NumSemana] ASC
        """
        
        results = conexion.ejecutar_consulta(query)
        
        if results:
            # Organizar datos por año
            datos_por_ano = {}
            for row in results:
                ano = str(row[0])
                semana = int(row[1])
                
                if ano not in datos_por_ano:
                    datos_por_ano[ano] = []
                
                if semana not in datos_por_ano[ano]:
                    datos_por_ano[ano].append(semana)
            
            # Ordenar semanas dentro de cada año
            for ano in datos_por_ano:
                datos_por_ano[ano].sort()
            
            return jsonify({
                'success': True,
                'total_registros': len(results),
                'filtros': datos_por_ano,
                'anos_disponibles': sorted(datos_por_ano.keys(), reverse=True),
                'message': f'Filtros cargados: {len(datos_por_ano)} años disponibles'
            })
        else:
            return jsonify({
                'success': False,
                'filtros': {},
                'anos_disponibles': [],
                'message': 'No se encontraron datos de filtros'
            })
            
    except Exception as e:
        print(f"Error al obtener filtros: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'filtros': {},
            'anos_disponibles': [],
            'message': 'Error al cargar filtros desde la base de datos'
        })

@app.route('/api/procesos-tiempos-filtrados', methods=['POST'])
def obtener_procesos_filtrados():
    """Obtener datos filtrados por años y semanas seleccionadas"""
    try:
        data = request.get_json()
        anos_seleccionados = data.get('anos', [])
        semanas_seleccionadas = data.get('semanas', [])
        
        if not anos_seleccionados or not semanas_seleccionadas:
            return jsonify({
                'success': False,
                'message': 'Debe seleccionar al menos un año y una semana'
            })
        
        conexion = ConexionODBC()
        
        # Construir placeholders para la consulta
        anos_placeholders = ','.join(['?' for _ in anos_seleccionados])
        semanas_placeholders = ','.join(['?' for _ in semanas_seleccionadas])
        
        query = f"""
        SELECT TOP (1000) 
            [Año],
            [NumSemana],
            [NumeroPedido],
            [CodigoPieza],
            [CODLINEA],
            [CODPIEZA],
            [DESCRIPCIONPIEZA],
            [MODELO],
            [TIPOENVIO],
            [GFH],
            [FICHADO],
            [PUESTO],
            [TIEMPO_TOTAL]
        FROM [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas]
        WHERE [Año] IN ({anos_placeholders})
        AND [NumSemana] IN ({semanas_placeholders})
        ORDER BY [Año] DESC, [NumSemana] DESC, [NumeroPedido]
        """
        
        # Combinar parámetros
        parametros = anos_seleccionados + semanas_seleccionadas
        
        results = conexion.ejecutar_consulta(query, parametros)
        
        if results:
            # Convertir resultados a formato JSON
            datos = []
            for row in results:
                datos.append({
                    'ano': row[0],
                    'numSemana': row[1],
                    'numeroPedido': row[2],
                    'codigoPieza': row[3],
                    'codLinea': row[4],
                    'codPieza': row[5],
                    'descripcionPieza': row[6],
                    'modelo': row[7],
                    'tipoEnvio': row[8],
                    'gfh': row[9],
                    'fichado': row[10],
                    'puesto': row[11],
                    'tiempoTotal': row[12]
                })
            
            return jsonify({
                'success': True,
                'total_registros': len(datos),
                'datos': datos,
                'filtros_aplicados': {
                    'anos': anos_seleccionados,
                    'semanas': semanas_seleccionadas
                },
                'message': f'Datos cargados: {len(datos)} registros encontrados'
            })
        else:
            return jsonify({
                'success': False,
                'datos': [],
                'message': 'No se encontraron datos con los filtros seleccionados'
            })
            
    except Exception as e:
        print(f"Error al obtener datos filtrados: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'datos': [],
            'message': 'Error al cargar datos filtrados desde la base de datos'
        })


# ====================================================================================
# ENDPOINT PARA REGISTRAR CAPACIDADES
# ====================================================================================

@app.route('/api/registrar-capacidad', methods=['POST'])
def registrar_capacidad():
    """Registrar nueva capacidad en la tabla Capacidades"""
    try:
        data = request.get_json()
        print(f"📥 Datos recibidos en /api/registrar-capacidad: {data}")
        
        if not data:
            print("❌ Error: Datos inválidos (data es None)")
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        turno = data.get('turno', '').strip()
        capacidad = data.get('capacidad')
        nombre_puesto = data.get('puesto', '').strip()  # Recibimos Nombre_Puesto del frontend
        fecha = data.get('fecha', '').strip()
        
        print(f"📋 Valores extraídos - Turno: '{turno}', Capacidad: {capacidad}, Nombre_Puesto: '{nombre_puesto}', Fecha: '{fecha}'")
        
        # Validar datos requeridos
        if not turno or capacidad is None or not nombre_puesto or not fecha:
            print(f"❌ Error: Faltan datos requeridos - Turno: {bool(turno)}, Capacidad: {capacidad is not None}, Nombre_Puesto: {bool(nombre_puesto)}, Fecha: {bool(fecha)}")
            return jsonify({
                'success': False, 
                'message': 'Turno, Capacidad, Puesto y Fecha son requeridos'
            }), 400
        
        # Validar que la capacidad sea un número válido
        try:
            capacidad = int(capacidad)
            if capacidad < 0:
                raise ValueError("La capacidad no puede ser negativa")
        except (ValueError, TypeError):
            print(f"❌ Error: Capacidad inválida '{capacidad}'. Debe ser un número entero positivo")
            return jsonify({
                'success': False, 
                'message': 'La capacidad debe ser un número entero positivo'
            }), 400
        
        # Validar formato de fecha
        try:
            datetime.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            print(f"❌ Error: Formato de fecha inválido '{fecha}'. Debe ser YYYY-MM-DD")
            return jsonify({
                'success': False, 
                'message': 'Formato de fecha inválido. Debe ser YYYY-MM-DD'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Primero, obtener el Codigo_Puesto correspondiente al Nombre_Puesto
            print(f"🔍 Buscando Codigo_Puesto para Nombre_Puesto: '{nombre_puesto}'")
            cursor.execute("""
                SELECT Codigo_Puesto FROM [Digitalizacion].[CAB].[Puestos]
                WHERE Nombre_Puesto = ?
            """, (nombre_puesto,))
            
            puesto_result = cursor.fetchone()
            if not puesto_result:
                print(f"❌ Error: No se encontró Codigo_Puesto para Nombre_Puesto: '{nombre_puesto}'")
                return jsonify({
                    'success': False, 
                    'message': f'No se encontró el puesto: {nombre_puesto}'
                }), 400
            
            codigo_puesto = puesto_result[0]
            print(f"✅ Codigo_Puesto encontrado: '{codigo_puesto}' para Nombre_Puesto: '{nombre_puesto}'")
            
            # Verificar si ya existe una capacidad para el mismo puesto, fecha y turno
            print(f"🔍 Verificando si ya existe capacidad para Codigo_Puesto: {codigo_puesto}, Fecha: {fecha}, Turno: {turno}")
            cursor.execute("""
                SELECT ID_Capacidad FROM [Digitalizacion].[CAB].[Capacidades]
                WHERE Puesto = ? AND Fecha = ? AND Turno = ?
            """, (codigo_puesto, fecha, turno))
            
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Actualizar registro existente
                print(f"🔄 Actualizando registro existente ID: {existing_record[0]}")
                cursor.execute("""
                    UPDATE [Digitalizacion].[CAB].[Capacidades]
                    SET Capacidad = ?
                    WHERE ID_Capacidad = ?
                """, (capacidad, existing_record[0]))
                
                registro_id = existing_record[0]
                accion = "actualizada"
            else:
                # Insertar nuevo registro
                print(f"💾 Insertando nuevo registro de capacidad")
                cursor.execute("""
                    INSERT INTO [Digitalizacion].[CAB].[Capacidades] 
                    (Turno, Capacidad, Puesto, Fecha)
                    VALUES (?, ?, ?, ?)
                """, (turno, capacidad, codigo_puesto, fecha))
                
                # Obtener el ID del registro recién creado
                cursor.execute("SELECT @@IDENTITY")
                registro_id = cursor.fetchone()[0]
                accion = "registrada"
            
            conn.commit()
            print(f"✅ Capacidad {accion} exitosamente con ID: {registro_id}")
            
            return jsonify({
                'success': True,
                'message': f'Capacidad {accion} exitosamente',
                'registro': {
                    'id': registro_id,
                    'turno': turno,
                    'capacidad': capacidad,
                    'puesto': codigo_puesto,  # Guardamos el Codigo_Puesto
                    'nombre_puesto': nombre_puesto,  # También devolvemos el Nombre_Puesto para referencia
                    'fecha': fecha,
                    'accion': accion
                }
            })
            
    except Exception as e:
        print(f"💥 Error registrando capacidad: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/consultar-capacidad', methods=['GET'])
def consultar_capacidad():
    """Consultar capacidad existente para un puesto, fecha y turno específicos"""
    try:
        turno = request.args.get('turno', '').strip()
        fecha = request.args.get('fecha', '').strip()
        nombre_puesto = request.args.get('puesto', '').strip()  # Recibimos Nombre_Puesto del frontend
        
        print(f"📥 Consultando capacidad - Turno: '{turno}', Fecha: '{fecha}', Nombre_Puesto: '{nombre_puesto}'")
        
        # Validar parámetros requeridos
        if not turno or not fecha or not nombre_puesto:
            print(f"❌ Error: Faltan parámetros requeridos")
            return jsonify({
                'success': False, 
                'message': 'Turno, Fecha y Puesto son requeridos'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Primero, obtener el Codigo_Puesto correspondiente al Nombre_Puesto
            print(f"🔍 Buscando Codigo_Puesto para Nombre_Puesto: '{nombre_puesto}'")
            cursor.execute("""
                SELECT Codigo_Puesto FROM [Digitalizacion].[CAB].[Puestos]
                WHERE Nombre_Puesto = ?
            """, (nombre_puesto,))
            
            puesto_result = cursor.fetchone()
            if not puesto_result:
                print(f"❌ Error: No se encontró Codigo_Puesto para Nombre_Puesto: '{nombre_puesto}'")
                return jsonify({
                    'success': False, 
                    'message': f'No se encontró el puesto: {nombre_puesto}'
                }), 400
            
            codigo_puesto = puesto_result[0]
            print(f"✅ Codigo_Puesto encontrado: '{codigo_puesto}' para Nombre_Puesto: '{nombre_puesto}'")
            
            # Buscar capacidad existente usando el Codigo_Puesto
            print(f"🔍 Buscando capacidad para Codigo_Puesto: {codigo_puesto}, Fecha: {fecha}, Turno: {turno}")
            cursor.execute("""
                SELECT ID_Capacidad, Turno, Capacidad, Puesto, Fecha
                FROM [Digitalizacion].[CAB].[Capacidades]
                WHERE Puesto = ? AND Fecha = ? AND Turno = ?
            """, (codigo_puesto, fecha, turno))
            
            result = cursor.fetchone()
            
            if result:
                capacidad_data = {
                    'id': result[0],
                    'turno': result[1].strip() if result[1] else '',
                    'capacidad': result[2],
                    'puesto': result[3].strip() if result[3] else '',
                    'fecha': result[4].strftime('%Y-%m-%d') if result[4] else ''
                }
                
                print(f"✅ Capacidad encontrada: {capacidad_data}")
                
                return jsonify({
                    'success': True,
                    'found': True,
                    'capacidad': capacidad_data
                })
            else:
                print(f"ℹ️ No se encontró capacidad para los parámetros dados")
                
                return jsonify({
                    'success': True,
                    'found': False,
                    'message': 'No existe capacidad registrada para estos parámetros'
                })
            
    except Exception as e:
        print(f"💥 Error consultando capacidad: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/obtener-operarios', methods=['GET'])
def obtener_operarios():
    """Obtener lista de operarios únicos de DatosUserCAB filtrados por fecha y turno"""
    try:
        turno = request.args.get('turno', '').strip()
        fecha = request.args.get('fecha', '').strip()
        
        print(f"📥 Consultando operarios - Turno: '{turno}', Fecha: '{fecha}'")
        
        # Validar parámetros requeridos
        if not turno or not fecha:
            print(f"❌ Error: Faltan parámetros requeridos")
            return jsonify({
                'success': False, 
                'message': 'Turno y Fecha son requeridos'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Consultar operarios únicos no NULL para el turno y fecha especificados
            print(f"🔍 Buscando operarios para Turno: '{turno}', Fecha: '{fecha}'")
            print(f"📋 Tipos de datos - Turno: {type(turno)}, Fecha: {type(fecha)}")
            
            cursor.execute("""
                SELECT DISTINCT 
                    d.Operario,
                    u.Nombre
                FROM [Digitalizacion].[CAB].[DatosUserCAB] d
                INNER JOIN [Digitalizacion].[General].[Usuarios] u 
                  ON d.Operario = u.Num_Operario
                WHERE d.Turno = ? AND d.Fecha = ? AND d.Operario IS NOT NULL AND d.Operario != ''
                ORDER BY d.Operario
            """, (turno, fecha))
            
            resultados = cursor.fetchall()
            print(f"📊 Consulta ejecutada - Se encontraron {len(resultados)} resultados")
            
            # Log adicional para depuración
            if len(resultados) == 0:
                print("🔍 Verificando registros similares en la tabla...")
                cursor.execute("""
                    SELECT TOP 5 d.Turno, d.Fecha, d.Operario, u.Nombre
                    FROM [Digitalizacion].[CAB].[DatosUserCAB] d
                    LEFT JOIN [Digitalizacion].[General].[Usuarios] u 
                      ON d.Operario = u.Num_Operario
                    WHERE d.Operario IS NOT NULL AND d.Operario != ''
                    ORDER BY d.Fecha DESC, d.Turno
                """)
                registros_muestra = cursor.fetchall()
                print(f"📋 Muestra de registros recientes con operario:")
                for reg in registros_muestra:
                    nombre = reg[3] if reg[3] else "SIN NOMBRE"
                    print(f"   - Turno: '{reg[0]}', Fecha: '{reg[1]}', Operario: '{reg[2]}', Nombre: '{nombre}'")
            
            if resultados:
                # Procesar resultados - crear lista con número y nombre del operario
                operarios = []
                for row in resultados:
                    if row[0] is not None and row[1] is not None:
                        # Asegurar que el operario sea string para consistencia
                        operario_num = str(row[0]).strip()
                        operario_nombre = str(row[1]).strip()
                        # Formato: "123 - NOMBRE APELLIDO"
                        operario_display = f"{operario_num} - {operario_nombre}"
                        operarios.append({
                            'value': operario_num,  # Valor para envío (número como string)
                            'text': operario_display  # Texto para mostrar
                        })
                
                print(f"✅ Se encontraron {len(operarios)} operarios")
                for op in operarios:
                    print(f"   - {op['value']}: {op['text']}")
                
                return jsonify({
                    'success': True,
                    'operarios': operarios
                })
            else:
                print(f"ℹ️ No se encontraron operarios para Turno: '{turno}', Fecha: '{fecha}'")
                
                return jsonify({
                    'success': True,
                    'operarios': [],
                    'message': 'No hay operarios registrados para el turno y fecha seleccionados'
                })
            
    except Exception as e:
        print(f"💥 Error obteniendo operarios: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/obtener-operarios-seccion', methods=['GET'])
def obtener_operarios_seccion():
    """Obtener lista de operarios únicos filtrados por IDSECCION de la vista V_CalendarioOperario"""
    try:
        seccion = request.args.get('seccion', '').strip()
        
        print(f"📥 Consultando operarios por sección - IDSECCION: '{seccion}'")
        
        # Validar parámetro requerido
        if not seccion:
            print(f"❌ Error: Falta parámetro seccion")
            return jsonify({
                'success': False, 
                'message': 'Sección es requerida'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Consultar operarios únicos de la vista V_CalendarioOperario filtrados por IDSECCION
            print(f"🔍 Buscando operarios para IDSECCION: '{seccion}'")
            
            cursor.execute("""
                SELECT DISTINCT
                  CAST(v.NUMOPE AS int) AS Operario,
                  u.Nombre
                FROM [Digitalizacion].[AR].[V_CalendarioOperario] v
                INNER JOIN [Digitalizacion].[General].[Usuarios] u 
                  ON CAST(v.NUMOPE AS int) = u.Num_Operario
                WHERE v.IDSECCION = ?
                ORDER BY CAST(v.NUMOPE AS int)
            """, (seccion,))
            
            resultados = cursor.fetchall()
            print(f"📊 Consulta ejecutada - Se encontraron {len(resultados)} operarios para IDSECCION {seccion}")
            
            # Log adicional para depuración
            if len(resultados) == 0:
                print("🔍 Verificando registros en la vista...")
                cursor.execute("""
                    SELECT TOP 5 v.[IDSECCION], CAST(v.[NUMOPE] AS int) AS Operario, u.Nombre, v.[DESCRIPCION_PUESTO]
                    FROM [Digitalizacion].[AR].[V_CalendarioOperario] v
                    LEFT JOIN [Digitalizacion].[General].[Usuarios] u 
                      ON CAST(v.NUMOPE AS int) = u.Num_Operario
                    WHERE v.[NUMOPE] IS NOT NULL AND v.[NUMOPE] != ''
                    ORDER BY v.[IDSECCION], v.[NUMOPE]
                """)
                registros_muestra = cursor.fetchall()
                print(f"📋 Muestra de registros disponibles:")
                for reg in registros_muestra:
                    nombre = reg[2] if reg[2] else "SIN NOMBRE"
                    print(f"   - IDSECCION: '{reg[0]}', NUMOPE: {reg[1]}, NOMBRE: '{nombre}', PUESTO: '{reg[3]}'")
            
            if resultados:
                # Procesar resultados - crear lista con número y nombre del operario
                operarios = []
                for row in resultados:
                    if row[0] is not None and row[1] is not None:
                        # Formato: "123 - NOMBRE APELLIDO"
                        operario_display = f"{row[0]} - {row[1].strip()}"
                        operarios.append({
                            'value': str(row[0]),  # Valor para envío (número)
                            'text': operario_display  # Texto para mostrar
                        })
                
                print(f"✅ Se encontraron {len(operarios)} operarios para IDSECCION {seccion}")
                for op in operarios:
                    print(f"   - {op['value']}: {op['text']}")
                
                return jsonify({
                    'success': True,
                    'operarios': operarios
                })
            else:
                print(f"ℹ️ No se encontraron operarios para IDSECCION: '{seccion}'")
                
                return jsonify({
                    'success': True,
                    'operarios': [],
                    'message': f'No hay operarios registrados para la sección {seccion}'
                })
            
    except Exception as e:
        print(f"💥 Error obteniendo operarios por sección: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/registrar-capacidad-operario', methods=['POST'])
def registrar_capacidad_operario():
    """Registrar nueva capacidad por operario en la tabla CapacidadesOperarios"""
    try:
        data = request.get_json()
        print(f"📥 Datos recibidos en /api/registrar-capacidad-operario: {data}")
        
        if not data:
            print("❌ Error: Datos inválidos (data es None)")
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        turno = data.get('turno', '').strip()
        capacidad = data.get('capacidad')
        operario = data.get('operario', '').strip()
        fecha = data.get('fecha', '').strip()
        
        print(f"📋 Valores extraídos - Turno: '{turno}', Capacidad: {capacidad}, Operario: '{operario}', Fecha: '{fecha}'")
        
        # Validar datos requeridos
        if not turno or capacidad is None or not operario or not fecha:
            print(f"❌ Error: Faltan datos requeridos - Turno: {bool(turno)}, Capacidad: {capacidad is not None}, Operario: {bool(operario)}, Fecha: {bool(fecha)}")
            return jsonify({
                'success': False, 
                'message': 'Turno, Capacidad, Operario y Fecha son requeridos'
            }), 400
        
        # Validar que la capacidad sea un número válido
        try:
            capacidad = int(capacidad)
            if capacidad < 0:
                raise ValueError("La capacidad no puede ser negativa")
        except (ValueError, TypeError):
            print(f"❌ Error: Capacidad inválida '{capacidad}'. Debe ser un número entero positivo")
            return jsonify({
                'success': False, 
                'message': 'La capacidad debe ser un número entero positivo'
            }), 400
        
        # Validar formato de fecha
        try:
            datetime.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            print(f"❌ Error: Formato de fecha inválido '{fecha}'. Debe ser YYYY-MM-DD")
            return jsonify({
                'success': False, 
                'message': 'Formato de fecha inválido. Debe ser YYYY-MM-DD'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Verificar si ya existe un registro para este operario, turno y fecha
            print(f"🔍 Verificando si existe registro para Operario: '{operario}', Turno: '{turno}', Fecha: '{fecha}'")
            cursor.execute("""
                SELECT ID_Capacidad, Capacidad
                FROM [Digitalizacion].[CAB].[CapacidadesOperarios]
                WHERE Operario = ? AND Turno = ? AND Fecha = ?
            """, (operario, turno, fecha))
            
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Actualizar registro existente
                print(f"🔄 Actualizando registro existente ID: {existing_record[0]}")
                cursor.execute("""
                    UPDATE [Digitalizacion].[CAB].[CapacidadesOperarios]
                    SET Capacidad = ?
                    WHERE ID_Capacidad = ?
                """, (capacidad, existing_record[0]))
                
                registro_id = existing_record[0]
                accion = "actualizada"
            else:
                # Insertar nuevo registro
                print(f"💾 Insertando nuevo registro de capacidad por operario")
                cursor.execute("""
                    INSERT INTO [Digitalizacion].[CAB].[CapacidadesOperarios] 
                    (Turno, Capacidad, Operario, Fecha)
                    VALUES (?, ?, ?, ?)
                """, (turno, capacidad, operario, fecha))
                
                # Obtener el ID del registro recién creado
                cursor.execute("SELECT @@IDENTITY")
                registro_id = cursor.fetchone()[0]
                accion = "registrada"
            
            conn.commit()
            print(f"✅ Capacidad por operario {accion} exitosamente con ID: {registro_id}")
            
            return jsonify({
                'success': True,
                'message': f'Capacidad por operario {accion} exitosamente',
                'registro': {
                    'id': registro_id,
                    'turno': turno,
                    'capacidad': capacidad,
                    'operario': operario,
                    'fecha': fecha,
                    'accion': accion
                }
            })
            
    except Exception as e:
        print(f"💥 Error registrando capacidad por operario: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/consultar-capacidad-operario', methods=['GET'])
def consultar_capacidad_operario():
    """Consultar capacidad existente para un operario, fecha y turno específicos"""
    try:
        turno = request.args.get('turno', '').strip()
        fecha = request.args.get('fecha', '').strip()
        operario = request.args.get('operario', '').strip()
        
        print(f"📥 Consultando capacidad operario - Turno: '{turno}', Fecha: '{fecha}', Operario: '{operario}'")
        
        # Validar parámetros requeridos
        if not turno or not fecha or not operario:
            print(f"❌ Error: Faltan parámetros requeridos")
            return jsonify({
                'success': False, 
                'message': 'Turno, Fecha y Operario son requeridos'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Buscar capacidad existente
            print(f"🔍 Buscando capacidad para Operario: '{operario}', Turno: '{turno}', Fecha: '{fecha}'")
            cursor.execute("""
                SELECT ID_Capacidad, Turno, Capacidad, Operario, Fecha
                FROM [Digitalizacion].[CAB].[CapacidadesOperarios]
                WHERE Operario = ? AND Turno = ? AND Fecha = ?
            """, (operario, turno, fecha))
            
            result = cursor.fetchone()
            
            if result:
                capacidad_data = {
                    'id': result[0],
                    'turno': result[1].strip() if result[1] else '',
                    'capacidad': result[2] if result[2] is not None else 0,
                    'operario': result[3].strip() if result[3] else '',
                    'fecha': result[4].strftime('%Y-%m-%d') if result[4] else ''
                }
                
                print(f"✅ Capacidad operario encontrada: {capacidad_data}")
                
                return jsonify({
                    'success': True,
                    'found': True,
                    'capacidad': capacidad_data
                })
            else:
                print(f"ℹ️ No se encontró capacidad para el operario y parámetros dados")
                
                return jsonify({
                    'success': True,
                    'found': False,
                    'message': 'No existe capacidad registrada para este operario en la fecha y turno especificados'
                })
            
    except Exception as e:
        print(f"💥 Error consultando capacidad operario: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/consultar-capacidad-operario-jornada', methods=['GET'])
def consultar_capacidad_operario_jornada():
    """Consultar capacidad existente para un operario en modo jornada fija (TURNO='JORNADA', FECHA='1999-01-01')"""
    try:
        operario = request.args.get('operario', '').strip()
        
        print(f"📥 Consultando capacidad operario JORNADA FIJA - Operario: '{operario}'")
        
        # Validar parámetro requerido
        if not operario:
            print(f"❌ Error: Falta parámetro operario")
            return jsonify({
                'success': False, 
                'message': 'Operario es requerido'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Buscar capacidad existente para jornada fija
            print(f"🔍 Buscando capacidad JORNADA FIJA para Operario: '{operario}'")
            cursor.execute("""
                SELECT ID_Capacidad, Turno, Capacidad, Operario, Fecha
                FROM [Digitalizacion].[CAB].[CapacidadesOperarios]
                WHERE Operario = ? AND Turno = 'JORNADA' AND Fecha = '1999-01-01'
            """, (operario,))
            
            result = cursor.fetchone()
            
            if result:
                capacidad_data = {
                    'id': result[0],
                    'turno': result[1].strip() if result[1] else '',
                    'capacidad': result[2],
                    'operario': result[3].strip() if result[3] else '',
                    'fecha': result[4].strftime('%Y-%m-%d') if result[4] else ''
                }
                
                print(f"✅ Capacidad JORNADA FIJA encontrada: {capacidad_data}")
                
                return jsonify({
                    'success': True,
                    'found': True,
                    'capacidad': capacidad_data
                })
            else:
                print(f"ℹ️ No se encontró capacidad JORNADA FIJA para operario: '{operario}'")
                
                return jsonify({
                    'success': True,
                    'found': False,
                    'message': 'No existe capacidad registrada para este operario en modo jornada fija'
                })
            
    except Exception as e:
        print(f"💥 Error consultando capacidad operario jornada fija: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/indicadores-puestos', methods=['GET'])
def indicadores_puestos():
    """Obtener indicadores de rendimiento por puesto para un turno y fecha específicos"""
    try:
        turno = request.args.get('turno', '').strip()
        fecha = request.args.get('fecha', '').strip()
        
        print(f"📊 Consultando indicadores - Turno: '{turno}', Fecha: '{fecha}'")
        
        # Validar parámetros requeridos
        if not turno or not fecha:
            print(f"❌ Error: Faltan parámetros requeridos")
            return jsonify({
                'success': False, 
                'message': 'Turno y Fecha son requeridos'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Obtener puestos usando el mismo endpoint que ListaPuestosCAB
            print(f"🔍 Obteniendo puestos desde /api/lista-puestos-cab...")
            
            # Usar la misma consulta que lista-puestos-cab para garantizar consistencia
            cursor.execute("""
                SELECT DISTINCT Nombre_Puesto
                FROM [Digitalizacion].[CAB].[Puestos]
                WHERE Nombre_Puesto IS NOT NULL
                ORDER BY Nombre_Puesto
            """)
            
            puestos_rows = cursor.fetchall()
            puestos_nombres = [row[0] for row in puestos_rows if row[0]]
            
            print(f"📊 Puestos encontrados (idéntico a ListaPuestosCAB): {len(puestos_nombres)}")
            for i, nombre in enumerate(puestos_nombres):
                print(f"  {i+1}. '{nombre}'")
            
            indicadores = []
            
            # Para cada puesto, obtener sus datos de Codigo_Puesto para las consultas
            for nombre_puesto in puestos_nombres:
                print(f"  🔍 Procesando puesto: {nombre_puesto}")
                
                # Obtener Codigo_Puesto para este Nombre_Puesto
                cursor.execute("""
                    SELECT Codigo_Puesto FROM [Digitalizacion].[CAB].[Puestos]
                    WHERE Nombre_Puesto = ?
                """, (nombre_puesto,))
                
                codigo_result = cursor.fetchone()
                codigo_puesto = codigo_result[0] if codigo_result else nombre_puesto
                
                print(f"  🔍 Procesando puesto: {nombre_puesto} ({codigo_puesto})")
                
                # Obtener capacidad configurada para este puesto, turno y fecha
                # IMPORTANTE: En Capacidades el campo Puesto debe corresponder al Codigo_Puesto
                print(f"    📋 Buscando capacidad: Puesto={codigo_puesto}, Turno={turno}, Fecha={fecha}")
                cursor.execute("""
                    SELECT Capacidad
                    FROM [Digitalizacion].[CAB].[Capacidades]
                    WHERE Puesto = ? AND Turno = ? AND Fecha = ?
                """, (codigo_puesto, turno, fecha))
                
                capacidad_row = cursor.fetchone()
                
                if capacidad_row:
                    min_capacidad = capacidad_row[0]
                    print(f"    ✅ Capacidad encontrada: {min_capacidad}")
                else:
                    print(f"    ❌ No se encontró capacidad para {codigo_puesto}, {turno}, {fecha}")
                    # Buscar cualquier capacidad para este puesto para debug
                    cursor.execute("""
                        SELECT TOP 3 Turno, Fecha, Capacidad
                        FROM [Digitalizacion].[CAB].[Capacidades]
                        WHERE Puesto = ?
                        ORDER BY Fecha DESC
                    """, (codigo_puesto,))
                    debug_rows = cursor.fetchall()
                    if debug_rows:
                        print(f"    🔍 Capacidades disponibles para {codigo_puesto}:")
                        for debug_row in debug_rows:
                            print(f"      - Turno: {debug_row[0]}, Fecha: {debug_row[1]}, Capacidad: {debug_row[2]}")
                    else:
                        print(f"    ❌ No hay capacidades configuradas para {codigo_puesto}")
                    
                    min_capacidad = 0  # Sin capacidad configurada
                
                # Obtener minutos teóricos REALES desde la vista TiempoTeorico
                # IMPORTANTE: Ahora usamos TTG en lugar de TIEMPO_TOTAL
                print(f"    🕒 Buscando tiempos teóricos (TTG) en vista TiempoTeorico...")
                print(f"    🔍 Probando con Nombre_Puesto: '{nombre_puesto}'")
                
                try:
                    cursor.execute("""
                        SELECT SUM(
                            CASE 
                                WHEN TTG IS NOT NULL 
                                THEN CAST(TTG AS FLOAT)
                                ELSE 0 
                            END
                        ) as TotalMinutos
                        FROM [Digitalizacion].[CAB].[TiempoTeorico]
                        WHERE Nombre_Puesto = ? AND Fecha = ? AND Turno = ?
                    """, (nombre_puesto, fecha, turno))
                    
                    tiempo_row = cursor.fetchone()
                    
                    if tiempo_row and tiempo_row[0] is not None and tiempo_row[0] > 0:
                        min_teoricos = int(tiempo_row[0])
                        print(f"    ✅ Tiempo teórico (TTG) encontrado con Nombre_Puesto: {min_teoricos} minutos")
                    else:
                        print(f"    ❌ No se encontró con Nombre_Puesto. Probando con Codigo_Puesto: '{codigo_puesto}'")
                        # Intentar con el código del puesto en caso de que la vista use códigos
                        cursor.execute("""
                            SELECT SUM(
                                CASE 
                                    WHEN TTG IS NOT NULL 
                                    THEN CAST(TTG AS FLOAT)
                                    ELSE 0 
                                END
                            ) as TotalMinutos
                            FROM [Digitalizacion].[CAB].[TiempoTeorico]
                            WHERE Nombre_Puesto = ? AND Fecha = ? AND Turno = ?
                        """, (codigo_puesto, fecha, turno))
                        
                        tiempo_row2 = cursor.fetchone()
                        if tiempo_row2 and tiempo_row2[0] is not None and tiempo_row2[0] > 0:
                            min_teoricos = int(tiempo_row2[0])
                            print(f"    ✅ Tiempo teórico (TTG) encontrado con Codigo_Puesto: {min_teoricos} minutos")
                        else:
                            print(f"    ❌ No se encontraron tiempos teóricos TTG ni con nombre ni con código")
                            # Buscar datos para debug - ver qué valores tiene realmente Nombre_Puesto
                            cursor.execute("""
                                SELECT TOP 5 DISTINCT Nombre_Puesto, TTG
                                FROM [Digitalizacion].[CAB].[TiempoTeorico]
                                WHERE Fecha = ? AND Turno = ?
                                ORDER BY Nombre_Puesto
                            """, (fecha, turno))
                            debug_puestos = cursor.fetchall()
                            if debug_puestos:
                                print(f"    🔍 Puestos disponibles en TiempoTeorico para {fecha}, {turno}:")
                                for debug_puesto in debug_puestos:
                                    print(f"      - '{debug_puesto[0]}' -> TTG: '{debug_puesto[1]}'")
                            else:
                                print(f"    ❌ No hay datos en TiempoTeorico para {fecha}, {turno}")
                            
                            min_teoricos = 0  # Sin datos teóricos
                
                except Exception as tiempo_error:
                    print(f"    💥 Error en consulta de tiempos teóricos: {tiempo_error}")
                    min_teoricos = 0  # Sin datos teóricos en caso de error
                
                # MOSTRAR TODAS LAS TARJETAS SIEMPRE (para debug y verificación)
                # Calcular eficiencia solo si hay datos válidos
                if min_teoricos > 0 and min_capacidad > 0:
                    eficiencia = round((min_teoricos / min_capacidad) * 100, 1)
                    color = 'verde' if eficiencia >= 85 else 'amarillo' if eficiencia >= 70 else 'rojo'
                    status = 'OK'
                else:
                    eficiencia = 0
                    color = 'gris'
                    status = f'SIN_DATOS (T:{min_teoricos}, C:{min_capacidad})'
                
                indicador = {
                    'puesto': nombre_puesto,
                    'codigo': codigo_puesto,
                    'minTeoricos': min_teoricos,
                    'minCapacidad': min_capacidad,
                    'eficiencia': eficiencia,
                    'color': color,
                    'status': status
                }
                
                indicadores.append(indicador)
                
                # Log detallado
                if min_teoricos > 0 and min_capacidad > 0:
                    print(f"    ✅ Tarjeta agregada: {nombre_puesto} - {min_teoricos}/{min_capacidad} min ({eficiencia}%)")
                else:
                    print(f"    ⚠️ Tarjeta agregada SIN DATOS: {nombre_puesto} - (Teóricos: {min_teoricos}, Capacidad: {min_capacidad})")
            
            print(f"✅ Procesamiento completado:")
            print(f"   📊 Total puestos desde /api/lista-puestos-cab: {len(puestos_nombres)}")
            print(f"   📋 Todas las tarjetas mostradas: {len(indicadores)}")
            tarjetas_con_datos = len([i for i in indicadores if i['minTeoricos'] > 0 and i['minCapacidad'] > 0])
            tarjetas_sin_datos = len(indicadores) - tarjetas_con_datos
            print(f"   ✅ Tarjetas con datos válidos: {tarjetas_con_datos}")
            print(f"   ⚠️ Tarjetas sin datos: {tarjetas_sin_datos}")
            
            return jsonify({
                'success': True,
                'indicadores': indicadores,
                'turno': turno,
                'fecha': fecha,
                'total_puestos': len(puestos_nombres),
                'tarjetas_mostradas': len(indicadores),
                'tarjetas_con_datos': tarjetas_con_datos,
                'tarjetas_sin_datos': tarjetas_sin_datos,
                'fuente_puestos': 'mismo_endpoint_que_lista_puestos_cab'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500

@app.route('/api/debug-indicadores', methods=['GET'])
def debug_indicadores():
    """Endpoint de debug para diagnosticar problemas con indicadores"""
    try:
        turno = request.args.get('turno', '').strip()
        fecha = request.args.get('fecha', '').strip()
        
        if not turno or not fecha:
            return jsonify({
                'success': False,
                'message': 'Turno y Fecha son requeridos para debug'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            debug_info = {
                'parametros': {'turno': turno, 'fecha': fecha},
                'puestos': [],
                'capacidades': [],
                'tiempos_teoricos': []
            }
            
            # 1. Verificar puestos en la tabla
            cursor.execute("""
                SELECT ID_Puesto, Nombre_Puesto, Codigo_Puesto
                FROM [Digitalizacion].[CAB].[Puestos]
                ORDER BY Nombre_Puesto
            """)
            puestos_rows = cursor.fetchall()
            debug_info['puestos'] = [
                {'id': row[0], 'nombre': row[1], 'codigo': row[2]} 
                for row in puestos_rows
            ]
            
            # 2. Verificar capacidades para la fecha/turno
            cursor.execute("""
                SELECT Puesto, Capacidad, Fecha, Turno
                FROM [Digitalizacion].[CAB].[Capacidades]
                WHERE Fecha = ? AND Turno = ?
                ORDER BY Puesto
            """, (fecha, turno))
            capacidades_rows = cursor.fetchall()
            debug_info['capacidades'] = [
                {'puesto': row[0], 'capacidad': row[1], 'fecha': str(row[2]), 'turno': row[3]}
                for row in capacidades_rows
            ]
            
            # 3. Verificar tiempos teóricos
            cursor.execute("""
                SELECT Nombre_Puesto, COUNT(*) as Registros, SUM(TIEMPO_TOTAL) as Total_Minutos
                FROM [Digitalizacion].[CAB].[TiempoTeorico]
                WHERE Fecha = ? AND Turno = ?
                GROUP BY Nombre_Puesto
                ORDER BY Nombre_Puesto
            """, (fecha, turno))
            tiempos_rows = cursor.fetchall()
            debug_info['tiempos_teoricos'] = [
                {'puesto': row[0], 'registros': row[1], 'total_minutos': int(row[2]) if row[2] else 0}
                for row in tiempos_rows
            ]
            
            # 4. Análisis de coincidencias
            puestos_nombres = {p['nombre'] for p in debug_info['puestos']}
            puestos_codigos = {p['codigo'] for p in debug_info['puestos']}
            capacidades_puestos = {c['puesto'] for c in debug_info['capacidades']}
            tiempos_puestos = {t['puesto'] for t in debug_info['tiempos_teoricos']}
            
            debug_info['analisis'] = {
                'total_puestos_configurados': len(debug_info['puestos']),
                'total_capacidades_encontradas': len(debug_info['capacidades']),
                'total_tiempos_encontrados': len(debug_info['tiempos_teoricos']),
                'puestos_con_capacidad': list(capacidades_puestos),
                'puestos_con_tiempos': list(tiempos_puestos),
                'puestos_sin_capacidad': list(puestos_codigos - capacidades_puestos),
                'puestos_sin_tiempos': list(puestos_nombres - tiempos_puestos),
                'coincidencias_completas': list(puestos_nombres & tiempos_puestos & capacidades_puestos)
            }
            
            return jsonify({
                'success': True,
                'debug': debug_info
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error en debug: {str(e)}'
        }), 500


@app.route('/api/indicadores-operarios', methods=['GET'])
def indicadores_operarios():
    """Obtener indicadores de rendimiento por operario para un turno y fecha específicos"""
    try:
        turno = request.args.get('turno', '').strip()
        fecha = request.args.get('fecha', '').strip()
        
        print(f"📊 Consultando indicadores operarios - Turno: '{turno}', Fecha: '{fecha}'")
        
        # Validar parámetros requeridos
        if not turno or not fecha:
            print(f"❌ Error: Faltan parámetros requeridos")
            return jsonify({
                'success': False, 
                'message': 'Turno y Fecha son requeridos'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error: No se pudo conectar a la base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # 1. Obtener tiempos teóricos agrupados por operario
            print(f"🔍 Buscando tiempos teóricos para operarios en Turno: '{turno}', Fecha: '{fecha}'")
            cursor.execute("""
                SELECT 
                    Operario,
                    SUM(TTG) as Total_TTG_Minutos
                FROM [Digitalizacion].[CAB].[TiempoTeorico]
                WHERE Fecha = ? AND Turno = ? AND Operario IS NOT NULL AND Operario != ''
                GROUP BY Operario
                ORDER BY Operario
            """, (fecha, turno))
            
            tiempos_operarios = cursor.fetchall()
            print(f"📋 Encontrados {len(tiempos_operarios)} operarios con tiempos teóricos")
            
            if not tiempos_operarios:
                print(f"ℹ️ No se encontraron tiempos teóricos para operarios en Turno: '{turno}', Fecha: '{fecha}'")
                return jsonify({
                    'success': True,
                    'indicadores': [],
                    'turno': turno,
                    'fecha': fecha,
                    'total_operarios': 0,
                    'tarjetas_mostradas': 0,
                    'tarjetas_con_datos': 0,
                    'tarjetas_sin_capacidad': 0,
                    'message': 'No hay datos de tiempos teóricos para operarios en la fecha y turno especificados'
                })
            
            # 2. Obtener capacidades de operarios con lógica de prioridad condicional
            print(f"🔍 Buscando capacidades de operarios con lógica de prioridad")
            print(f"   📋 Prioridad 1: Turno='{turno}', Fecha='{fecha}'")
            print(f"   📋 Prioridad 2: Turno='JORNADA', Fecha='1999-01-01'")
            
            cursor.execute("""
                WITH CapacidadesPriorizadas AS (
                    -- Prioridad 1: Capacidades específicas para turno y fecha
                    SELECT 
                        Operario,
                        Capacidad,
                        1 as Prioridad,
                        'ESPECIFICA' as Tipo
                    FROM [Digitalizacion].[CAB].[CapacidadesOperarios]
                    WHERE Fecha = ? AND Turno = ?
                    
                    UNION ALL
                    
                    -- Prioridad 2: Capacidades por defecto (JORNADA)
                    SELECT 
                        Operario,
                        Capacidad,
                        2 as Prioridad,
                        'JORNADA' as Tipo
                    FROM [Digitalizacion].[CAB].[CapacidadesOperarios]
                    WHERE Fecha = '1999-01-01' AND Turno = 'JORNADA'
                ),
                CapacidadesFinales AS (
                    SELECT 
                        Operario,
                        Capacidad,
                        Tipo,
                        ROW_NUMBER() OVER (PARTITION BY Operario ORDER BY Prioridad ASC) as rn
                    FROM CapacidadesPriorizadas
                )
                SELECT 
                    Operario,
                    Capacidad,
                    Tipo
                FROM CapacidadesFinales
                WHERE rn = 1
            """, (fecha, turno))
            
            capacidades_rows = cursor.fetchall()
            capacidades_dict = {}
            
            # Procesar capacidades con información de tipo
            for row in capacidades_rows:
                operario = row[0]
                capacidad = int(row[1]) if row[1] is not None else 0
                tipo = row[2]
                capacidades_dict[operario] = capacidad
                print(f"   📋 Operario {operario}: {capacidad} min (Tipo: {tipo})")
                
            print(f"📋 Encontradas {len(capacidades_dict)} capacidades de operarios con lógica de prioridad")
            
            # 3. Construir indicadores
            indicadores = []
            tarjetas_con_datos = 0
            tarjetas_sin_capacidad = 0
            
            for operario, ttg_minutos in tiempos_operarios:
                operario = operario.strip() if operario else ''
                min_teoricos = int(ttg_minutos) if ttg_minutos is not None else 0
                min_capacidad = capacidades_dict.get(operario, 0)
                
                # Calcular eficiencia
                if min_capacidad > 0 and min_teoricos > 0:
                    eficiencia = round((min_teoricos / min_capacidad) * 100, 1)
                    if eficiencia >= 100:
                        color = 'ok'
                    elif eficiencia >= 85:
                        color = 'warn' 
                    else:
                        color = 'bad'
                    status = 'CON_DATOS'
                    tarjetas_con_datos += 1
                elif min_teoricos > 0:
                    # Operario con TTG pero sin capacidad - mostrar en rojo
                    eficiencia = 0
                    color = 'bad'
                    status = 'SIN_CAPACIDAD'
                    tarjetas_sin_capacidad += 1
                else:
                    eficiencia = 0
                    color = 'gris'
                    status = 'SIN_DATOS'
                
                indicador = {
                    'operario': operario,
                    'minTeoricos': min_teoricos,
                    'minCapacidad': min_capacidad,
                    'eficiencia': eficiencia,
                    'color': color,
                    'status': status
                }
                
                indicadores.append(indicador)
                
                # Log detallado
                if status == 'CON_DATOS':
                    print(f"    ✅ Tarjeta agregada: {operario} - {min_teoricos}/{min_capacidad} min ({eficiencia}%)")
                elif status == 'SIN_CAPACIDAD':
                    print(f"    🔴 Tarjeta agregada SIN CAPACIDAD: {operario} - (Teóricos: {min_teoricos}, Sin capacidad definida)")
                else:
                    print(f"    ⚠️ Tarjeta agregada SIN DATOS: {operario} - (Teóricos: {min_teoricos}, Capacidad: {min_capacidad})")
            
            print(f"✅ Procesamiento de operarios completado:")
            print(f"   📊 Total operarios con tiempos teóricos: {len(tiempos_operarios)}")
            print(f"   📋 Todas las tarjetas mostradas: {len(indicadores)}")
            print(f"   ✅ Tarjetas con datos válidos: {tarjetas_con_datos}")
            print(f"   🔴 Tarjetas sin capacidad: {tarjetas_sin_capacidad}")
            
            return jsonify({
                'success': True,
                'indicadores': indicadores,
                'turno': turno,
                'fecha': fecha,
                'total_operarios': len(tiempos_operarios),
                'tarjetas_mostradas': len(indicadores),
                'tarjetas_con_datos': tarjetas_con_datos,
                'tarjetas_sin_capacidad': tarjetas_sin_capacidad
            })
            
    except Exception as e:
        print(f"💥 Error obteniendo indicadores de operarios: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/resumen-pedidos', methods=['GET'])
def obtener_resumen_pedidos():
    """Obtener resumen de pedidos agrupados por puesto para la pantalla de resumen"""
    try:
        # Obtener parámetros de filtros
        anos = request.args.getlist('anos[]')  # Lista de años
        semanas = request.args.getlist('semanas[]')  # Lista de semanas
        
        print(f"Filtros recibidos para resumen - Años: {anos}, Semanas: {semanas}")
        
        # Validar que tengamos al menos un filtro
        if not anos and not semanas:
            return jsonify({
                'success': False, 
                'message': 'Debe seleccionar al menos un año o semana'
            }), 400

        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            try:
                # 1. Obtener lista completa de puestos
                cursor.execute("SELECT Nombre_Puesto FROM [Digitalizacion].[CAB].[Puestos] ORDER BY Nombre_Puesto")
                puestos_result = cursor.fetchall()
                puestos = [row[0] for row in puestos_result]
                print(f"Puestos encontrados: {puestos}")
                
                # Debug: Verificar qué registros existen en DatosUserCAB
                cursor.execute("""
                    SELECT TOP 10 CODLINEA, GFH, ESTADO, Activo, Fecha, Turno
                    FROM [Digitalizacion].[CAB].[DatosUserCAB]
                    WHERE Activo = 1
                    ORDER BY Fecha DESC
                """)
                debug_estados = cursor.fetchall()
                print(f"Muestra de estados activos en DatosUserCAB:")
                for debug_row in debug_estados:
                    print(f"  CODLINEA={debug_row[0]}, GFH={debug_row[1]}, ESTADO={debug_row[2]}, Activo={debug_row[3]}, Fecha={debug_row[4]}, Turno={debug_row[5]}")
                
                # 2. Construir la consulta principal con filtros dinámicos
                sql_base = """
                    SELECT 
                        fpt.NumeroPedido,
                        p.Nombre_Puesto,
                        fpt.DESCRIPCIONPIEZA,
                        fpt.CODLINEA,
                        fpt.GFH,
                        duc.ESTADO
                    FROM [Digitalizacion].[CAB].[Fact_Procesos_Tiempos_Cabinas] fpt
                    INNER JOIN [Digitalizacion].[CAB].[Puestos] p 
                        ON fpt.PUESTO = p.Codigo_Puesto
                    LEFT JOIN [Digitalizacion].[CAB].[DatosUserCAB] duc 
                        ON fpt.CODLINEA = duc.CODLINEA 
                        AND fpt.GFH = duc.GFH 
                        AND duc.Activo = 1
                    WHERE 1=1
                """
                
                parametros = []
                condiciones_adicionales = []
                
                # Agregar filtro de años si está presente
                if anos:
                    anos_validos = [ano for ano in anos if ano.strip()]
                    if anos_validos:
                        placeholders_anos = ','.join(['?' for _ in anos_validos])
                        condiciones_adicionales.append(f"fpt.Año IN ({placeholders_anos})")
                        parametros.extend(anos_validos)
                
                # Agregar filtro de semanas si está presente
                if semanas:
                    semanas_validas = [semana for semana in semanas if semana.strip()]
                    if semanas_validas:
                        placeholders_semanas = ','.join(['?' for _ in semanas_validas])
                        condiciones_adicionales.append(f"fpt.NumSemana IN ({placeholders_semanas})")
                        parametros.extend(semanas_validas)
                
                # Construir SQL final
                if condiciones_adicionales:
                    sql_final = sql_base + " AND " + " AND ".join(condiciones_adicionales)
                else:
                    sql_final = sql_base
                
                sql_final += " ORDER BY fpt.NumeroPedido, p.Nombre_Puesto"
                
                print(f"SQL a ejecutar: {sql_final}")
                print(f"Parámetros: {parametros}")
                
                cursor.execute(sql_final, parametros)
                resultados = cursor.fetchall()
                
                # 3. Procesar los resultados en Python para agrupar por pedido
                pedidos_dict = {}
                
                for row in resultados:
                    numero_pedido = row[0]
                    nombre_puesto = row[1] 
                    descripcion_pieza = row[2]
                    codlinea = row[3]
                    gfh = row[4]
                    estado = row[5]
                    
                    # Debug: Mostrar información sobre cada registro
                    print(f"Procesando: Pedido={numero_pedido}, Puesto={nombre_puesto}, "
                          f"Pieza={descripcion_pieza}, CODLINEA={codlinea}, GFH={gfh}, Estado={estado}")
                    
                    # Inicializar pedido si no existe
                    if numero_pedido not in pedidos_dict:
                        pedidos_dict[numero_pedido] = {
                            'numeroPedido': numero_pedido,
                            'puestos_data': {}
                        }
                    
                    # Inicializar puesto si no existe
                    if nombre_puesto not in pedidos_dict[numero_pedido]['puestos_data']:
                        pedidos_dict[numero_pedido]['puestos_data'][nombre_puesto] = []
                    
                    # Agregar la pieza al puesto
                    pedidos_dict[numero_pedido]['puestos_data'][nombre_puesto].append({
                        'descripcion': descripcion_pieza,
                        'estado': estado,
                        'debug_info': {
                            'codlinea': codlinea,
                            'gfh': gfh
                        }
                    })
                
                # Convertir el diccionario a lista
                pedidos_list = list(pedidos_dict.values())
                
                print(f"Pedidos procesados: {len(pedidos_list)}")
                
                # ============================================================
                # 4. Enriquecer pedidos con datos de DatosPedidos
                # ============================================================
                numeros_pedido = [p['numeroPedido'] for p in pedidos_list if p['numeroPedido']]
                
                if numeros_pedido:
                    try:
                        from decimal import Decimal
                        # Usar cursor nuevo para evitar interferencias con la consulta principal
                        cursor2 = conn.cursor()
                        
                        # Obtener columnas de DatosPedidos dinámicamente
                        cursor2.execute("""
                            SELECT COLUMN_NAME
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = 'CAB' 
                            AND TABLE_NAME = 'DatosPedidos'
                            ORDER BY ORDINAL_POSITION
                        """)
                        columnas_dp = [row[0] for row in cursor2.fetchall()]
                        
                        if not columnas_dp:
                            # Fallback: obtener desde cursor.description
                            cursor2.execute("SELECT TOP 1 * FROM [Digitalizacion].[CAB].[DatosPedidos]")
                            columnas_dp = [col[0] for col in cursor2.description]
                        
                        if columnas_dp:
                            # Construir consulta dinámica con los números de pedido
                            placeholders = ','.join(['?' for _ in numeros_pedido])
                            columnas_sql = ', '.join([f'[{c}]' for c in columnas_dp])
                            
                            print(f"📦 Consultando DatosPedidos con {len(columnas_dp)} columnas para {len(numeros_pedido)} pedidos")
                            
                            cursor2.execute(f"""
                                SELECT {columnas_sql}
                                FROM [Digitalizacion].[CAB].[DatosPedidos]
                                WHERE Pedido IN ({placeholders})
                            """, numeros_pedido)
                            
                            datos_pedidos_rows = cursor2.fetchall()
                            print(f"📦 DatosPedidos: {len(datos_pedidos_rows)} filas obtenidas")
                            
                            # Construir diccionario: Pedido -> {columna: valor}
                            datos_por_pedido = {}
                            for row in datos_pedidos_rows:
                                pedido_key = str(row[0]) if row[0] is not None else None
                                if pedido_key:
                                    datos_por_pedido[pedido_key] = {}
                                    for i, col_name in enumerate(columnas_dp):
                                        val = row[i]
                                        # Convertir tipos no serializables a JSON
                                        if val is None:
                                            pass  # mantener None
                                        elif isinstance(val, Decimal):
                                            val = float(val)
                                        elif isinstance(val, (bytes, bytearray)):
                                            val = str(val)
                                        elif hasattr(val, 'isoformat'):  # date/datetime/time
                                            val = val.isoformat()
                                        elif isinstance(val, (str, int, float, bool)):
                                            pass  # tipos nativos JSON
                                        else:
                                            val = str(val)
                                        datos_por_pedido[pedido_key][col_name] = val
                            
                            # Merge: añadir datosPedido a cada pedido
                            for pedido in pedidos_list:
                                num = str(pedido['numeroPedido'])
                                if num in datos_por_pedido:
                                    pedido['datosPedido'] = datos_por_pedido[num]
                                else:
                                    pedido['datosPedido'] = None
                            
                            print(f"📦 Enriquecidos {sum(1 for p in pedidos_list if p.get('datosPedido'))} pedidos con datos de DatosPedidos")
                        else:
                            print("⚠️ No se pudieron obtener columnas de DatosPedidos")
                            for pedido in pedidos_list:
                                pedido['datosPedido'] = None
                                
                        cursor2.close()
                    except Exception as e:
                        print(f"⚠️ Error enriqueciendo con DatosPedidos (no crítico): {e}")
                        import traceback
                        traceback.print_exc()
                        # No fallar - continuar sin datos de DatosPedidos
                        for pedido in pedidos_list:
                            pedido['datosPedido'] = None
                else:
                    # Sin pedidos, inicializar campo vacío
                    for pedido in pedidos_list:
                        pedido['datosPedido'] = None
                
                return jsonify({
                    'success': True,
                    'puestos': puestos,
                    'pedidos': pedidos_list,
                    'total_pedidos': len(pedidos_list),
                    'filtros_aplicados': {
                        'anos': anos,
                        'semanas': semanas
                    }
                })
                
            except Exception as e:
                print(f"Error en consulta de resumen pedidos: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Error en consulta de base de datos: {str(e)}'
                }), 500
            
    except Exception as e:
        print(f"Error general obteniendo resumen pedidos: {e}")
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500


# ====================================================================================
# ENDPOINT PARA GUARDAR NOTAS DE PEDIDO (EDITABLE DESDE RESUMEN PEDIDOS)
# ====================================================================================

@app.route('/api/guardar-nota-pedido', methods=['POST'])
def guardar_nota_pedido():
    """Guardar/actualizar cualquier campo de un pedido en DatosPedidos.
    Soporta tanto campos específicos (notas, operario) como campo genérico (campo + valor).
    Campos permitidos: Notas, Operario, Clinchado, Suelos, Techos, Bajotecho, Especiales,
                       EMB, TipoDecoracion, Modelo, FechaEntrega"""
    CAMPOS_PERMITIDOS = [
        'Notas', 'Operario', 'Clinchado', 'Suelos', 'Techos', 'Bajotecho', 'Especiales',
        'EMB', 'TipoDecoracion', 'Modelo', 'FechaEntrega'
    ]
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        pedido = str(data.get('pedido', '')).strip()
        notas = data.get('notas')
        operario = data.get('operario')
        campo = data.get('campo')  # Nuevo: campo genérico
        valor = data.get('valor')  # Nuevo: valor para el campo genérico
        
        if not pedido:
            return jsonify({'success': False, 'message': 'Número de pedido requerido'}), 400
        
        # ── Modo genérico: actualizar cualquier campo permitido ──
        if campo is not None:
            if campo not in CAMPOS_PERMITIDOS:
                return jsonify({
                    'success': False, 
                    'message': f'Campo "{campo}" no permitido. Permitidos: {", ".join(CAMPOS_PERMITIDOS)}'
                }), 400
            
            # Normalizar: si el valor es string vacío, guardar como None (NULL en BD)
            valor_final = valor if valor != '' else None
            
            with ConexionODBC('Digitalizacion') as conn:
                if not conn:
                    return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
                
                cursor = conn.cursor()
                
                # Verificar si existe el pedido
                cursor.execute("""
                    SELECT COUNT(*) FROM [Digitalizacion].[CAB].[DatosPedidos]
                    WHERE Pedido = ?
                """, (pedido,))
                existe = cursor.fetchone()[0] > 0
                
                if existe:
                    cursor.execute(f"""
                        UPDATE [Digitalizacion].[CAB].[DatosPedidos]
                        SET [{campo}] = ?, FechaImport = SYSDATETIME()
                        WHERE Pedido = ?
                    """, (valor_final, pedido))
                else:
                    # Insertar nuevo registro con FechaEntrega por defecto
                    try:
                        anio_pedido = int(pedido) // 100000
                        fecha_entrega_default = f"{anio_pedido}-01-01"
                    except (ValueError, TypeError):
                        fecha_entrega_default = None
                    
                    cursor.execute(f"""
                        INSERT INTO [Digitalizacion].[CAB].[DatosPedidos] (Pedido, FechaEntrega, [{campo}])
                        VALUES (?, ?, ?)
                    """, (pedido, fecha_entrega_default, valor_final))
                
                conn.commit()
                print(f"✅ Campo '{campo}' actualizado para pedido {pedido}: {valor_final}")
            
            return jsonify({
                'success': True,
                'message': f'Campo {campo} guardado correctamente',
                'pedido': pedido,
                'campo': campo,
                'valor': valor_final
            })
        
        # ── Modo legacy: notas y operario (compatibilidad hacia atrás) ──
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Verificar si existe el pedido en DatosPedidos
            cursor.execute("""
                SELECT COUNT(*) FROM [Digitalizacion].[CAB].[DatosPedidos]
                WHERE Pedido = ?
            """, (pedido,))
            
            existe = cursor.fetchone()[0] > 0
            
            # Construir SET dinámico según lo que se envía
            # Derivar FechaEntrega del número de pedido (primeros 4 dígitos = año)
            try:
                anio_pedido = int(pedido) // 100000
                fecha_entrega_default = f"{anio_pedido}-01-01"
            except (ValueError, TypeError):
                fecha_entrega_default = None
            
            if notas is not None and operario is not None:
                if existe:
                    cursor.execute("""
                        UPDATE [Digitalizacion].[CAB].[DatosPedidos]
                        SET Notas = ?, Operario = ?, FechaImport = SYSDATETIME()
                        WHERE Pedido = ?
                    """, (notas if notas else None, operario if operario else None, pedido))
                else:
                    cursor.execute("""
                        INSERT INTO [Digitalizacion].[CAB].[DatosPedidos] (Pedido, FechaEntrega, Notas, Operario)
                        VALUES (?, ?, ?, ?)
                    """, (pedido, fecha_entrega_default, notas if notas else None, operario if operario else None))
                print(f"✅ Notas y Operario actualizados para pedido {pedido}")
            elif notas is not None:
                if existe:
                    cursor.execute("""
                        UPDATE [Digitalizacion].[CAB].[DatosPedidos]
                        SET Notas = ?, FechaImport = SYSDATETIME()
                        WHERE Pedido = ?
                    """, (notas if notas else None, pedido))
                else:
                    cursor.execute("""
                        INSERT INTO [Digitalizacion].[CAB].[DatosPedidos] (Pedido, FechaEntrega, Notas)
                        VALUES (?, ?, ?)
                    """, (pedido, fecha_entrega_default, notas if notas else None))
                print(f"✅ Nota actualizada para pedido {pedido}")
            elif operario is not None:
                if existe:
                    cursor.execute("""
                        UPDATE [Digitalizacion].[CAB].[DatosPedidos]
                        SET Operario = ?, FechaImport = SYSDATETIME()
                        WHERE Pedido = ?
                    """, (operario if operario else None, pedido))
                else:
                    cursor.execute("""
                        INSERT INTO [Digitalizacion].[CAB].[DatosPedidos] (Pedido, FechaEntrega, Operario)
                        VALUES (?, ?, ?)
                    """, (pedido, fecha_entrega_default, operario if operario else None))
                print(f"✅ Operario actualizado para pedido {pedido}")
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Guardado correctamente',
                'pedido': pedido
            })
            
    except Exception as e:
        print(f"Error guardando nota de pedido: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500


# ====================================================================================
# ENDPOINT PARA IMPORTAR DATOS DE PEDIDOS (datospedidos.html)
# ====================================================================================

@app.route('/api/importar-datospedidos', methods=['POST'])
def importar_datos_pedidos():
    """Importar filas en la tabla DatosPedidos desde Excel o pegado manual"""
    try:
        data = request.get_json()
        if not data or 'filas' not in data:
            return jsonify({'success': False, 'message': 'No se recibieron datos para importar'}), 400
        
        filas = data['filas']
        if not filas or not isinstance(filas, list):
            return jsonify({'success': False, 'message': 'Formato de datos inválido'}), 400
        
        print(f"📥 Recibidas {len(filas)} filas para importar en DatosPedidos")
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            insertadas = 0
            actualizadas = 0
            errores = []
            
            for i, fila in enumerate(filas):
                try:
                    pedido = fila.get('Pedido')
                    fecha_entrega = fila.get('FechaEntrega')
                    # Convertir fecha DD/MM/YYYY → YYYY-MM-DD (formato español)
                    if fecha_entrega and '/' in str(fecha_entrega):
                        partes = str(fecha_entrega).replace('-','/').split('/')
                        if len(partes) == 3:
                            # Siempre DD/MM/YYYY (formato español)
                            d = partes[0].zfill(2)
                            m = partes[1].zfill(2)
                            a = partes[2]
                            if len(a) == 2:
                                a = '20' + a
                            fecha_entrega = f"{a}-{m}-{d}"
                    emb = fila.get('EMB')
                    tipo_decoracion = fila.get('TipoDecoracion')
                    notas = fila.get('Notas')
                    operario = fila.get('Operario')
                    modelo = fila.get('Modelo')
                    
                    # Validar campos obligatorios
                    if not pedido or not fecha_entrega:
                        errores.append(f"Fila {i+1}: Pedido y FechaEntrega son obligatorios")
                        continue
                    
                    # Validar formato del pedido (9 dígitos)
                    try:
                        pedido_int = int(pedido)
                        if pedido_int < 100000000 or pedido_int > 999999999:
                            errores.append(f"Fila {i+1}: Pedido {pedido} debe tener 9 dígitos")
                            continue
                    except (ValueError, TypeError):
                        errores.append(f"Fila {i+1}: Pedido {pedido} no es un número válido")
                        continue
                    
                    # Verificar si ya existe
                    cursor.execute("""
                        SELECT COUNT(*) FROM [Digitalizacion].[CAB].[DatosPedidos]
                        WHERE Pedido = ?
                    """, (pedido_int,))
                    
                    existe = cursor.fetchone()[0] > 0
                    
                    if existe:
                        # UPDATE
                        cursor.execute("""
                            UPDATE [Digitalizacion].[CAB].[DatosPedidos]
                            SET FechaEntrega = ?,
                                EMB = ?,
                                TipoDecoracion = ?,
                                Notas = ?,
                                Operario = ?,
                                Modelo = ?,
                                FechaImport = SYSDATETIME()
                            WHERE Pedido = ?
                        """, (
                            fecha_entrega,
                            emb if emb else None,
                            int(tipo_decoracion) if tipo_decoracion else None,
                            notas if notas else None,
                            operario if operario else None,
                            modelo if modelo else None,
                            pedido_int
                        ))
                        actualizadas += 1
                        print(f"   ✅ Actualizado: Pedido {pedido_int}")
                    else:
                        # INSERT
                        cursor.execute("""
                            INSERT INTO [Digitalizacion].[CAB].[DatosPedidos]
                            (Pedido, FechaEntrega, EMB, TipoDecoracion, Notas, Operario, Modelo)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            pedido_int,
                            fecha_entrega,
                            emb if emb else None,
                            int(tipo_decoracion) if tipo_decoracion else None,
                            notas if notas else None,
                            operario if operario else None,
                            modelo if modelo else None
                        ))
                        insertadas += 1
                        print(f"   ✅ Insertado: Pedido {pedido_int}")
                        
                except Exception as e:
                    errores.append(f"Fila {i+1}: {str(e)}")
                    print(f"   ❌ Error fila {i+1}: {e}")
            
            conn.commit()
            
            print(f"📥 Importación completada: {insertadas} insertadas, {actualizadas} actualizadas, {len(errores)} errores")
            
            return jsonify({
                'success': True,
                'insertadas': insertadas,
                'actualizadas': actualizadas,
                'errores': len(errores),
                'detalle_errores': errores[:10],  # Máximo 10 errores
                'message': f'{insertadas} insertadas, {actualizadas} actualizadas'
            })
            
    except Exception as e:
        print(f"💥 Error importando datos pedidos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500


@app.route('/api/datospedidos-listado', methods=['GET'])
def obtener_datospedidos_listado():
    """Obtener listado de DatosPedidos para visualizar en la pantalla de importación"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT TOP 1000 [Pedido], [FechaEntrega], [EMB], [TipoDecoracion], [Modelo], [FechaImport]
                FROM [Digitalizacion].[CAB].[DatosPedidos]
                ORDER BY [FechaImport] DESC, [Pedido] DESC
            """)
            
            rows = cursor.fetchall()
            
            pedidos = []
            for row in rows:
                pedidos.append({
                    'Pedido': row[0],
                    'FechaEntrega': row[1].isoformat() if hasattr(row[1], 'isoformat') else str(row[1]) if row[1] else None,
                    'EMB': row[2],
                    'TipoDecoracion': row[3],
                    'Modelo': row[4],
                    'FechaImport': row[5].isoformat() if hasattr(row[5], 'isoformat') else str(row[5]) if row[5] else None
                })
            
            print(f"📋 Listado DatosPedidos: {len(pedidos)} registros")
            
            return jsonify({
                'success': True,
                'pedidos': pedidos,
                'total': len(pedidos)
            })
            
    except Exception as e:
        print(f"💥 Error obteniendo listado DatosPedidos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500


# ====================================================================================
# ENDPOINTS PARA TIEMPOS PICKING
# ====================================================================================

@app.route('/api/tiempos-picking', methods=['GET'])
def obtener_tiempos_picking():
    """Obtener todos los tiempos de picking registrados"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({
                    'success': False,
                    'message': 'Error de conexión a la base de datos'
                }), 500

            cursor = conn.cursor()
            
            # Obtener todos los registros de tiempos picking
            query = """
                SELECT 
                    CODIGOPICKING,
                    DESCRIPCION,
                    TIEMPO_PICKING
                FROM [CAB].[TiemposPicking]
                ORDER BY CODIGOPICKING
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            tiempos = []
            for row in rows:
                tiempos.append({
                    'CODIGOPICKING': row[0],
                    'DESCRIPCION': row[1],
                    'TIEMPO_PICKING': float(row[2])
                })
            
            return jsonify({
                'success': True,
                'tiempos': tiempos,
                'total': len(tiempos)
            })
            
    except Exception as e:
        print(f"Error en obtener_tiempos_picking: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener tiempos: {str(e)}'
        }), 500


@app.route('/api/tiempos-picking', methods=['POST'])
def crear_tiempo_picking():
    """Crear un nuevo tiempo de picking"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No se enviaron datos'
            }), 400
        
        codigo = data.get('CODIGOPICKING', '').strip()
        descripcion = data.get('DESCRIPCION', '').strip()
        tiempo = data.get('TIEMPO_PICKING')
        
        # Validaciones
        if not codigo or not descripcion or tiempo is None:
            return jsonify({
                'success': False,
                'message': 'Todos los campos son obligatorios'
            }), 400
        
        if len(codigo) > 20:
            return jsonify({
                'success': False,
                'message': 'El código no puede exceder 20 caracteres'
            }), 400
        
        if len(descripcion) > 400:
            return jsonify({
                'success': False,
                'message': 'La descripción no puede exceder 400 caracteres'
            }), 400
        
        try:
            tiempo = float(tiempo)
            if tiempo <= 0:
                return jsonify({
                    'success': False,
                    'message': 'El tiempo debe ser mayor que 0'
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'El tiempo debe ser un número válido'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({
                    'success': False,
                    'message': 'Error de conexión a la base de datos'
                }), 500

            cursor = conn.cursor()
            
            # Verificar si ya existe el código
            check_query = "SELECT COUNT(*) FROM [CAB].[TiemposPicking] WHERE CODIGOPICKING = ?"
            cursor.execute(check_query, (codigo,))
            if cursor.fetchone()[0] > 0:
                return jsonify({
                    'success': False,
                    'message': f'Ya existe un tiempo de picking con el código {codigo}'
                }), 400
            
            # Insertar nuevo registro
            insert_query = """
                INSERT INTO [CAB].[TiemposPicking] (CODIGOPICKING, DESCRIPCION, TIEMPO_PICKING)
                VALUES (?, ?, ?)
            """
            
            cursor.execute(insert_query, (codigo, descripcion, tiempo))
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Tiempo de picking creado exitosamente',
                'data': {
                    'CODIGOPICKING': codigo,
                    'DESCRIPCION': descripcion,
                    'TIEMPO_PICKING': tiempo
                }
            })
            
    except Exception as e:
        print(f"Error en crear_tiempo_picking: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al crear tiempo: {str(e)}'
        }), 500


@app.route('/api/tiempos-picking/batch', methods=['POST'])
def crear_tiempos_picking_batch():
    """Crear múltiples tiempos de picking de una vez"""
    try:
        data = request.get_json()
        if not data or 'tiempos' not in data:
            return jsonify({
                'success': False,
                'message': 'No se enviaron datos o falta el array de tiempos'
            }), 400
        
        tiempos_list = data['tiempos']
        if not isinstance(tiempos_list, list) or len(tiempos_list) == 0:
            return jsonify({
                'success': False,
                'message': 'El array de tiempos está vacío o no es válido'
            }), 400
        
        # Validar todos los registros antes de insertar
        for i, tiempo_data in enumerate(tiempos_list):
            codigo = tiempo_data.get('CODIGOPICKING', '').strip()
            descripcion = tiempo_data.get('DESCRIPCION', '').strip()
            tiempo = tiempo_data.get('TIEMPO_PICKING')
            
            if not codigo or not descripcion or tiempo is None:
                return jsonify({
                    'success': False,
                    'message': f'Registro {i+1}: Todos los campos son obligatorios'
                }), 400
            
            if len(codigo) > 20:
                return jsonify({
                    'success': False,
                    'message': f'Registro {i+1}: El código no puede exceder 20 caracteres'
                }), 400
            
            if len(descripcion) > 400:
                return jsonify({
                    'success': False,
                    'message': f'Registro {i+1}: La descripción no puede exceder 400 caracteres'
                }), 400
            
            try:
                tiempo = float(tiempo)
                if tiempo <= 0:
                    return jsonify({
                        'success': False,
                        'message': f'Registro {i+1}: El tiempo debe ser mayor que 0'
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'message': f'Registro {i+1}: El tiempo debe ser un número válido'
                }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({
                    'success': False,
                    'message': 'Error de conexión a la base de datos'
                }), 500

            cursor = conn.cursor()
            
            # Verificar códigos duplicados en la base de datos
            codigos = [t['CODIGOPICKING'].strip() for t in tiempos_list]
            placeholders = ','.join(['?' for _ in codigos])
            check_query = f"SELECT CODIGOPICKING FROM [CAB].[TiemposPicking] WHERE CODIGOPICKING IN ({placeholders})"
            cursor.execute(check_query, codigos)
            existing_codes = [row[0] for row in cursor.fetchall()]
            
            if existing_codes:
                return jsonify({
                    'success': False,
                    'message': f'Los siguientes códigos ya existen: {", ".join(existing_codes)}'
                }), 400
            
            # Verificar códigos duplicados dentro del mismo batch
            codigo_set = set()
            for tiempo_data in tiempos_list:
                codigo = tiempo_data['CODIGOPICKING'].strip()
                if codigo in codigo_set:
                    return jsonify({
                        'success': False,
                        'message': f'Código duplicado en el batch: {codigo}'
                    }), 400
                codigo_set.add(codigo)
            
            # Insertar todos los registros
            insert_query = """
                INSERT INTO [CAB].[TiemposPicking] (CODIGOPICKING, DESCRIPCION, TIEMPO_PICKING)
                VALUES (?, ?, ?)
            """
            
            registros_insertados = []
            for tiempo_data in tiempos_list:
                codigo = tiempo_data['CODIGOPICKING'].strip()
                descripcion = tiempo_data['DESCRIPCION'].strip()
                tiempo = float(tiempo_data['TIEMPO_PICKING'])
                
                cursor.execute(insert_query, (codigo, descripcion, tiempo))
                registros_insertados.append({
                    'CODIGOPICKING': codigo,
                    'DESCRIPCION': descripcion,
                    'TIEMPO_PICKING': tiempo
                })
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'{len(registros_insertados)} tiempos de picking creados exitosamente',
                'data': registros_insertados
            })
            
    except Exception as e:
        print(f"Error en crear_tiempos_picking_batch: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al crear tiempos: {str(e)}'
        }), 500


@app.route('/api/tiempos-picking/<codigo_picking>', methods=['PUT'])
def actualizar_tiempo_picking(codigo_picking):
    """Actualizar un tiempo de picking existente"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No se enviaron datos'
            }), 400
        
        nuevo_codigo = data.get('CODIGOPICKING', '').strip()
        descripcion = data.get('DESCRIPCION', '').strip()
        tiempo = data.get('TIEMPO_PICKING')
        
        # Validaciones
        if not nuevo_codigo or not descripcion or tiempo is None:
            return jsonify({
                'success': False,
                'message': 'Todos los campos son obligatorios'
            }), 400
        
        if len(nuevo_codigo) > 20:
            return jsonify({
                'success': False,
                'message': 'El código no puede exceder 20 caracteres'
            }), 400
        
        if len(descripcion) > 400:
            return jsonify({
                'success': False,
                'message': 'La descripción no puede exceder 400 caracteres'
            }), 400
        
        try:
            tiempo = float(tiempo)
            if tiempo <= 0:
                return jsonify({
                    'success': False,
                    'message': 'El tiempo debe ser mayor que 0'
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'El tiempo debe ser un número válido'
            }), 400
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({
                    'success': False,
                    'message': 'Error de conexión a la base de datos'
                }), 500

            cursor = conn.cursor()
            
            # Verificar si existe el registro original
            check_query = "SELECT COUNT(*) FROM [CAB].[TiemposPicking] WHERE CODIGOPICKING = ?"
            cursor.execute(check_query, (codigo_picking,))
            if cursor.fetchone()[0] == 0:
                return jsonify({
                    'success': False,
                    'message': f'No existe un tiempo de picking con el código {codigo_picking}'
                }), 404
            
            # Si se cambió el código, verificar que el nuevo no exista
            if nuevo_codigo != codigo_picking:
                cursor.execute(check_query, (nuevo_codigo,))
                if cursor.fetchone()[0] > 0:
                    return jsonify({
                        'success': False,
                        'message': f'Ya existe un tiempo de picking con el código {nuevo_codigo}'
                    }), 400
            
            # Actualizar registro
            update_query = """
                UPDATE [CAB].[TiemposPicking] 
                SET CODIGOPICKING = ?, DESCRIPCION = ?, TIEMPO_PICKING = ?
                WHERE CODIGOPICKING = ?
            """
            
            cursor.execute(update_query, (nuevo_codigo, descripcion, tiempo, codigo_picking))
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Tiempo de picking actualizado exitosamente',
                'data': {
                    'CODIGOPICKING': nuevo_codigo,
                    'DESCRIPCION': descripcion,
                    'TIEMPO_PICKING': tiempo
                }
            })
            
    except Exception as e:
        print(f"Error en actualizar_tiempo_picking: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al actualizar tiempo: {str(e)}'
        }), 500


@app.route('/api/tiempos-picking/<codigo_picking>', methods=['DELETE'])
def eliminar_tiempo_picking(codigo_picking):
    """Eliminar un tiempo de picking"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({
                    'success': False,
                    'message': 'Error de conexión a la base de datos'
                }), 500

            cursor = conn.cursor()
            
            # Verificar si existe el registro
            check_query = "SELECT CODIGOPICKING, DESCRIPCION FROM [CAB].[TiemposPicking] WHERE CODIGOPICKING = ?"
            cursor.execute(check_query, (codigo_picking,))
            registro = cursor.fetchone()
            
            if not registro:
                return jsonify({
                    'success': False,
                    'message': f'No existe un tiempo de picking con el código {codigo_picking}'
                }), 404
            
            # Eliminar registro
            delete_query = "DELETE FROM [CAB].[TiemposPicking] WHERE CODIGOPICKING = ?"
            cursor.execute(delete_query, (codigo_picking,))
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Tiempo de picking {codigo_picking} eliminado exitosamente',
                'data': {
                    'CODIGOPICKING': registro[0],
                    'DESCRIPCION': registro[1]
                }
            })
            
    except Exception as e:
        print(f"Error en eliminar_tiempo_picking: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al eliminar tiempo: {str(e)}'
        }), 500

# ====================================================================================
# ENDPOINT PARA VERIFICAR ESTRUCTURA DE LA TABLA
# ====================================================================================

@app.route('/api/verificar-estructura-tabla', methods=['GET'])
def verificar_estructura_tabla():
    """Verificar si el campo Faltante existe en la tabla DatosUserCAB"""
    try:
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Verificar estructura de la tabla
            cursor.execute("""
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    CHARACTER_MAXIMUM_LENGTH,
                    IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = 'CAB' 
                AND TABLE_NAME = 'DatosUserCAB'
                ORDER BY ORDINAL_POSITION
            """)
            
            columnas = []
            campo_faltante_existe = False
            
            for row in cursor.fetchall():
                columna_info = {
                    'nombre': row[0],
                    'tipo': row[1],
                    'longitud': row[2],
                    'nulo': row[3]
                }
                columnas.append(columna_info)
                
                if row[0].lower() == 'faltante':
                    campo_faltante_existe = True
            
            return jsonify({
                'success': True,
                'campo_faltante_existe': campo_faltante_existe,
                'columnas': columnas
            })
            
    except Exception as e:
        print(f"Error verificando estructura de tabla: {e}")
        return jsonify({
            'success': False,
            'message': f'Error verificando estructura: {str(e)}'
        }), 500

# ====================================================================================
# ENDPOINT PARA ACTUALIZAR TEXTO DE FALTANTE
# ====================================================================================

@app.route('/api/actualizar-texto-faltante', methods=['POST'])
def actualizar_texto_faltante():
    """Actualizar el texto del faltante en la tabla DatosUserCAB"""
    try:
        data = request.get_json()
        print(f"📥 Datos recibidos en /api/actualizar-texto-faltante: {data}")
        
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        codlinea = data.get('codlinea', '').strip()
        gfh = data.get('gfh', '').strip()
        texto_faltante = data.get('texto_faltante', '').strip()
        
        # Validar datos requeridos
        if not codlinea or not gfh:
            return jsonify({
                'success': False, 
                'message': 'CODLINEA y GFH son requeridos'
            }), 400
        
        # Validar longitud del texto (máximo 200 caracteres)
        if len(texto_faltante) > 200:
            return jsonify({
                'success': False, 
                'message': 'El texto del faltante no puede exceder 200 caracteres'
            }), 400
        
        print(f"📋 Actualizando texto faltante - CODLINEA: '{codlinea}', GFH: '{gfh}', TEXTO: '{texto_faltante}'")
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Actualizar el registro activo más reciente que tenga estado 'Faltante'
            cursor.execute("""
                UPDATE [Digitalizacion].[CAB].[DatosUserCAB]
                SET Faltante = ?
                WHERE CODLINEA = ? 
                AND GFH = ? 
                AND ESTADO = 'Faltante' 
                AND Activo = 1
            """, (texto_faltante, codlinea, gfh))
            
            affected_rows = cursor.rowcount
            conn.commit()
            
            if affected_rows > 0:
                print(f"✅ Texto del faltante actualizado exitosamente - Filas afectadas: {affected_rows}")
                return jsonify({
                    'success': True,
                    'message': 'Texto del faltante actualizado exitosamente',
                    'updated_rows': affected_rows
                })
            else:
                print(f"⚠️ No se encontró registro activo con estado 'Faltante' para {codlinea}_{gfh}")
                return jsonify({
                    'success': False,
                    'message': 'No se encontró un registro activo con estado Faltante para actualizar'
                }), 404
                
    except Exception as e:
        print(f"💥 Error actualizando texto del faltante: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': f'Error del servidor: {str(e)}'
        }), 500

# ====================================================================================
# ENDPOINT PARA OBTENER PERMISOS DEL USUARIO
# ====================================================================================

@app.route('/api/obtener-permisos-usuario', methods=['GET'])
def obtener_permisos_usuario():
    """Obtener el nivel de permisos del usuario logueado"""
    try:
        # Obtener usuario de la sesión
        usuario_logueado = obtener_usuario_sesion()
        
        if not usuario_logueado:
            print("❌ Usuario no autenticado en sesión")
            return jsonify({
                'success': False, 
                'message': 'Usuario no autenticado'
            }), 401
        
        print(f"🔍 Obteniendo permisos para usuario: {usuario_logueado}")
        
        with ConexionODBC('Digitalizacion') as conn:
            if not conn:
                print("❌ Error de conexión a base de datos")
                return jsonify({'success': False, 'message': 'Error de conexión a base de datos'}), 500
            
            cursor = conn.cursor()
            
            # Consultar permisos del usuario en la tabla Usuarios
            print(f"🔍 Ejecutando consulta SQL para usuario: {usuario_logueado}")
            cursor.execute("""
                SELECT 
                    Id_Usuario,
                    Num_Operario,
                    Nombre,
                    Nivel_Permisos,
                    Roles
                FROM [Digitalizacion].[General].[Usuarios]
                WHERE Num_Operario = ?
            """, (usuario_logueado,))
            
            resultado = cursor.fetchone()
            print(f"🔍 Resultado de la consulta: {resultado}")
            
            if resultado:
                permisos_usuario = {
                    'Id_Usuario': resultado[0],
                    'Num_Operario': resultado[1],
                    'Nombre': resultado[2],
                    'Nivel_Permisos': resultado[3],
                    'Roles': resultado[4]
                }
                
                print(f"✅ Permisos encontrados para {resultado[2]}:")
                print(f"   - Num_Operario: {resultado[1]}")
                print(f"   - Nivel_Permisos: {resultado[3]} (tipo: {type(resultado[3])})")
                print(f"   - Roles: {resultado[4]}")
                
                return jsonify({
                    'success': True,
                    'usuario': permisos_usuario,
                    'nivel_permisos': resultado[3],  # ⭐ AGREGAR ESTE CAMPO DIRECTO
                    'puede_ver_configuracion': resultado[3] > 1,
                    'puede_ver_jefe_equipo': resultado[3] > 1,
                    'puede_acceder_pantallas_restringidas': resultado[3] > 1
                })
            else:
                print(f"❌ Usuario no encontrado en tabla Usuarios: {usuario_logueado}")
                return jsonify({
                    'success': False,
                    'message': 'Usuario no encontrado en el sistema de permisos'
                }), 404
                
    except Exception as e:
        print(f"💥 Error obteniendo permisos del usuario: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': f'Error del servidor: {str(e)}'
        }), 500

# ====================================================================================
# MIDDLEWARE PARA VALIDAR PERMISOS EN PANTALLAS RESTRINGIDAS
# ====================================================================================

@app.route('/api/validar-acceso-pantalla', methods=['POST'])
def validar_acceso_pantalla():
    """Validar si el usuario tiene permisos para acceder a una pantalla específica"""
    try:
        data = request.get_json()
        if not data:
            print("❌ Datos JSON inválidos o vacíos")
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
        
        pantalla = data.get('pantalla', '').strip()
        if not pantalla:
            print("❌ Nombre de pantalla vacío")
            return jsonify({'success': False, 'message': 'Pantalla es requerida'}), 400
        
        print(f"🔍 Validando acceso a pantalla: {pantalla}")
        
        # Pantallas que requieren Nivel_Permisos > 1 (Jefe de Equipo o superior)
        pantallas_restringidas = [
            'resumenpedidos.html',
            'indicadores.html', 
            'control.html',
            'configuracion.html',
            'CapacidadesCAB.html',
            'Crearpuesto.html',
            'datospedidos.html'
        ]
        
        print(f"🔍 Pantallas restringidas: {pantallas_restringidas}")
        print(f"🔍 Es pantalla restringida: {pantalla in pantallas_restringidas}")
        
        # Obtener usuario de la sesión
        usuario_logueado = obtener_usuario_sesion()
        
        print(f"🔍 Usuario en sesión: {usuario_logueado}")
        
        # Si no hay usuario real (Sistema o vacío), permitir acceso por defecto
        if not usuario_logueado or usuario_logueado == 'Sistema':
            print("⚠️ Usuario no autenticado o es 'Sistema' - Permitiendo acceso por defecto")
            return jsonify({
                'success': True,
                'acceso_permitido': True,
                'message': 'Acceso permitido por defecto (usuario no autenticado)'
            })
        
        # Si la pantalla no está en la lista restringida, permitir acceso
        if pantalla not in pantallas_restringidas:
            print(f"✅ Pantalla {pantalla} no restringida - Acceso permitido")
            return jsonify({
                'success': True,
                'acceso_permitido': True,
                'message': 'Pantalla no restringida'
            })
        
        # Para pantallas restringidas, verificar nivel de permisos
        print(f"🔐 Pantalla {pantalla} RESTRINGIDA - Verificando permisos...")
        try:
            with ConexionODBC('Digitalizacion') as conn:
                if not conn:
                    print("❌ Error de conexión a base de datos en validación - Permitiendo por defecto")
                    return jsonify({
                        'success': True,
                        'acceso_permitido': True,
                        'message': 'Acceso permitido por defecto (error de conexión DB)'
                    })
                
                cursor = conn.cursor()
                
                print(f"🔍 Ejecutando consulta de permisos para usuario: {usuario_logueado}")
                cursor.execute("""
                    SELECT Nivel_Permisos, Nombre
                    FROM [Digitalizacion].[General].[Usuarios]
                    WHERE Num_Operario = ?
                """, (usuario_logueado,))
                
                resultado = cursor.fetchone()
                print(f"🔍 Resultado consulta permisos: {resultado}")
                
                if resultado:
                    nivel_permisos = resultado[0]
                    nombre_usuario = resultado[1]
                    acceso_permitido = nivel_permisos > 1
                    
                    print(f"🔐 VALIDACIÓN DE ACCESO:")
                    print(f"   - Usuario: {nombre_usuario} ({usuario_logueado})")
                    print(f"   - Pantalla: {pantalla}")
                    print(f"   - Nivel_Permisos: {nivel_permisos} (tipo: {type(nivel_permisos)})")
                    print(f"   - Condición (nivel > 1): {nivel_permisos > 1}")
                    print(f"   - Acceso permitido: {acceso_permitido}")
                    
                    return jsonify({
                        'success': True,
                        'acceso_permitido': acceso_permitido,
                        'nivel_permisos': nivel_permisos,
                        'message': 'Acceso permitido' if acceso_permitido else 'Acceso denegado - Permisos insuficientes'
                    })
                else:
                    print(f"❌ Usuario {usuario_logueado} no encontrado en tabla Usuarios - Permitiendo por defecto")
                    return jsonify({
                        'success': True,
                        'acceso_permitido': True,
                        'message': 'Acceso permitido por defecto (usuario no encontrado en DB)'
                    })
        except Exception as db_error:
            print(f"❌ Error de base de datos en validación: {db_error} - Permitiendo por defecto")
            return jsonify({
                'success': True,
                'acceso_permitido': True,
                'message': f'Acceso permitido por defecto (error DB: {str(db_error)})'
            })
                
    except Exception as e:
        print(f"💥 Error validando acceso a pantalla: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'acceso_permitido': False,
            'message': f'Error del servidor: {str(e)}'
        }), 500


# ====================================================================================
# EJECUCIÓN DE LA APLICACIÓN
# ====================================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', '3020'))  # Puerto 3020 para no interferir con tu app principal
    
    # Obtener IP automáticamente
    def obtener_ip_local():
        try:
            # Conectar a un servidor externo para obtener la IP local
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"  # Fallback a localhost
    
    ip_local = obtener_ip_local()
    
    print("="*50)
    print("INICIALIZANDO API...")
    print("="*50)
    print(f"  Local:   http://127.0.0.1:{port}")
    print(f"  Red:     http://{ip_local}:{port}")
    print("="*50)
    
    import logging
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Silenciar los logs de peticiones de Werkzeug
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='0.0.0.0', port=port, debug=False)