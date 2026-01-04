"""
IPAL Water Quality Monitoring System - Backend
RS Khusus Mata Purwokerto
"""

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ipal-monitoring-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ipal_monitoring.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# ==================== DATABASE MODELS ====================

class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ph = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    tds = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='normal')
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'ph': self.ph,
            'temperature': self.temperature,
            'tds': self.tds,
            'status': self.status
        }


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    parameter = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    message = db.Column(db.String(200), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'parameter': self.parameter,
            'value': self.value,
            'message': self.message,
            'severity': self.severity,
            'is_read': self.is_read
        }


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }


class Threshold(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parameter = db.Column(db.String(50), unique=True, nullable=False)
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    unit = db.Column(db.String(20))
    
    def to_dict(self):
        return {
            'id': self.id,
            'parameter': self.parameter,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'unit': self.unit
        }


class DeviceStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='offline')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    signal_strength = db.Column(db.Integer, default=0)
    ip_address = db.Column(db.String(20))
    
    def to_dict(self):
        return {
            'id': self.id,
            'device_name': self.device_name,
            'status': self.status,
            'last_seen': self.last_seen.isoformat(),
            'signal_strength': self.signal_strength,
            'ip_address': self.ip_address
        }


# ==================== AUTHENTICATION DECORATOR ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated_function


# ==================== HELPER FUNCTIONS ====================

def check_threshold(ph, temp, tds):
    """Cek apakah parameter melebihi threshold dan buat alert"""
    alerts = []
    status = "normal"
    
    thresholds = {
        'ph': Threshold.query.filter_by(parameter='ph').first(),
        'temperature': Threshold.query.filter_by(parameter='temperature').first(),
        'tds': Threshold.query.filter_by(parameter='tds').first()
    }
    
    # Cek pH
    if thresholds['ph']:
        if ph < thresholds['ph'].min_value or ph > thresholds['ph'].max_value:
            severity = "danger" if abs(ph - 7) > 2 else "warning"
            if severity == "danger":
                status = "danger"
            elif status != "danger":
                status = "warning"
            
            alerts.append({
                'parameter': 'pH',
                'value': ph,
                'message': f'pH {ph:.2f} diluar batas normal ({thresholds["ph"].min_value}-{thresholds["ph"].max_value})',
                'severity': severity
            })
    
    # Cek Temperature
    if thresholds['temperature']:
        if temp > thresholds['temperature'].max_value:
            if status == "normal":
                status = "warning"
            
            alerts.append({
                'parameter': 'Suhu',
                'value': temp,
                'message': f'Suhu {temp:.1f}°C melebihi batas maksimal {thresholds["temperature"].max_value}°C',
                'severity': 'warning'
            })
    
    # Cek TDS
    if thresholds['tds']:
        if tds > thresholds['tds'].max_value:
            if status == "normal":
                status = "warning"
            
            alerts.append({
                'parameter': 'TDS',
                'value': tds,
                'message': f'TDS {tds:.0f} ppm melebihi batas maksimal {thresholds["tds"].max_value} ppm',
                'severity': 'warning'
            })
    
    return status, alerts


# ==================== AUTHENTICATION ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return jsonify({'success': True, 'role': user.role})
        
        return jsonify({'success': False, 'message': 'Username atau password salah'}), 401
    
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ==================== PAGE ROUTES ====================

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/history')
@login_required
def history():
    return render_template('history.html')


@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')


@app.route('/settings')
@login_required
def settings():
    # Inject user role ke template untuk JavaScript
    return render_template('settings.html', user_role=session.get('role', 'viewer'))


# ==================== API ENDPOINTS - SENSOR DATA ====================

@app.route('/api/sensor/current', methods=['GET'])
@login_required
def get_current_data():
    """Ambil data sensor terbaru"""
    latest = SensorData.query.order_by(SensorData.timestamp.desc()).first()
    
    if latest:
        return jsonify(latest.to_dict())
    
    return jsonify({'message': 'No data available'}), 404


@app.route('/api/sensor/data', methods=['POST'])
def receive_sensor_data():
    """Terima data dari ESP32 (tanpa auth untuk IoT)"""
    try:
        data = request.get_json()
        
        ph = float(data.get('ph', 0))
        temp = float(data.get('temperature', 0))
        tds = float(data.get('tds', 0))
        
        # Validasi data
        if not (0 <= ph <= 14) or not (-10 <= temp <= 100) or not (0 <= tds <= 10000):
            return jsonify({'error': 'Invalid sensor data'}), 400
        
        # Cek threshold
        status, alerts = check_threshold(ph, temp, tds)
        
        # Simpan data sensor
        sensor_data = SensorData(
            ph=ph,
            temperature=temp,
            tds=tds,
            status=status
        )
        db.session.add(sensor_data)
        
        # Simpan alerts jika ada
        for alert in alerts:
            alert_record = Alert(
                parameter=alert['parameter'],
                value=alert['value'],
                message=alert['message'],
                severity=alert['severity']
            )
            db.session.add(alert_record)
        
        # Update status device
        device = DeviceStatus.query.first()
        if device:
            device.status = 'online'
            device.last_seen = datetime.utcnow()
            device.ip_address = request.remote_addr
        
        db.session.commit()
        
        # Kirim ke semua client via WebSocket
        socketio.emit('sensor_update', {
            'timestamp': sensor_data.timestamp.isoformat(),
            'ph': ph,
            'temperature': temp,
            'tds': tds,
            'status': status,
            'alerts': alerts
        })
        
        return jsonify({'success': True, 'status': status, 'alerts_count': len(alerts)})
    
    except Exception as e:
        print(f"Error receiving sensor data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sensor/history', methods=['GET'])
@login_required
def get_history():
    """Ambil data historis dengan filter"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 100, type=int)
        
        query = SensorData.query
        
        if start_date:
            query = query.filter(SensorData.timestamp >= datetime.fromisoformat(start_date.replace('Z', '+00:00')))
        if end_date:
            query = query.filter(SensorData.timestamp <= datetime.fromisoformat(end_date.replace('Z', '+00:00')))
        
        data = query.order_by(SensorData.timestamp.desc()).limit(limit).all()
        
        return jsonify([d.to_dict() for d in data])
    
    except Exception as e:
        print(f"Error getting history: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== API ENDPOINTS - ALERTS ====================

@app.route('/api/alerts', methods=['GET'])
@login_required
def get_alerts():
    """Ambil alert terbaru"""
    try:
        limit = request.args.get('limit', 10, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        query = Alert.query
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        alerts = query.order_by(Alert.timestamp.desc()).limit(limit).all()
        
        return jsonify([a.to_dict() for a in alerts])
    
    except Exception as e:
        print(f"Error getting alerts: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/alerts/<int:alert_id>/read', methods=['PUT'])
@login_required
def mark_alert_read(alert_id):
    """Tandai alert sudah dibaca"""
    try:
        alert = Alert.query.get(alert_id)
        if alert:
            alert.is_read = True
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'error': 'Alert not found'}), 404
    
    except Exception as e:
        print(f"Error marking alert: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== API ENDPOINTS - THRESHOLDS ====================

@app.route('/api/thresholds', methods=['GET', 'POST'])
@login_required
def manage_thresholds():
    """Ambil atau update threshold"""
    try:
        if request.method == 'GET':
            thresholds = Threshold.query.all()
            return jsonify([t.to_dict() for t in thresholds])
        
        elif request.method == 'POST':
            # Cek permission
            if session.get('role') not in ['admin', 'operator']:
                return jsonify({'error': 'Unauthorized'}), 403
            
            data = request.get_json()
            parameter = data.get('parameter')
            
            threshold = Threshold.query.filter_by(parameter=parameter).first()
            
            if threshold:
                threshold.min_value = data.get('min_value')
                threshold.max_value = data.get('max_value')
                threshold.unit = data.get('unit')
            else:
                threshold = Threshold(
                    parameter=parameter,
                    min_value=data.get('min_value'),
                    max_value=data.get('max_value'),
                    unit=data.get('unit')
                )
                db.session.add(threshold)
            
            db.session.commit()
            return jsonify({'success': True, 'threshold': threshold.to_dict()})
    
    except Exception as e:
        print(f"Error managing thresholds: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== API ENDPOINTS - DEVICE ====================

@app.route('/api/device/status', methods=['GET'])
@login_required
def get_device_status():
    """Ambil status device"""
    try:
        device = DeviceStatus.query.first()
        
        if device:
            # Cek apakah offline (tidak ada data 5 menit terakhir)
            if (datetime.utcnow() - device.last_seen).total_seconds() > 300:
                device.status = 'offline'
                db.session.commit()
            
            return jsonify(device.to_dict())
        
        return jsonify({'status': 'offline', 'device_name': 'ESP32-IPAL-01'})
    
    except Exception as e:
        print(f"Error getting device status: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== API ENDPOINTS - STATISTICS ====================

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    """Ambil statistik untuk laporan"""
    try:
        period = request.args.get('period', 'today')
        
        if period == 'today':
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start = datetime.now() - timedelta(days=7)
        elif period == 'month':
            start = datetime.now() - timedelta(days=30)
        else:
            start = datetime.now() - timedelta(days=1)
        
        data = SensorData.query.filter(SensorData.timestamp >= start).all()
        
        if not data:
            return jsonify({'message': 'No data available for this period'})
        
        ph_values = [d.ph for d in data]
        temp_values = [d.temperature for d in data]
        tds_values = [d.tds for d in data]
        
        stats = {
            'period': period,
            'data_points': len(data),
            'start_date': start.isoformat(),
            'end_date': datetime.now().isoformat(),
            'ph': {
                'avg': sum(ph_values) / len(ph_values),
                'min': min(ph_values),
                'max': max(ph_values)
            },
            'temperature': {
                'avg': sum(temp_values) / len(temp_values),
                'min': min(temp_values),
                'max': max(temp_values)
            },
            'tds': {
                'avg': sum(tds_values) / len(tds_values),
                'min': min(tds_values),
                'max': max(tds_values)
            }
        }
        
        return jsonify(stats)
    
    except Exception as e:
        print(f"Error getting statistics: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connection_response', {'status': 'connected'})


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


# ==================== DATABASE INITIALIZATION ====================

def init_db():
    """Inisialisasi database dengan data default"""
    with app.app_context():
        db.create_all()
        
        # Buat default admin user
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password='admin123',
                role='admin',
                email='admin@rsmatapwt.com'
            )
            db.session.add(admin)
            print("✓ Default admin user created (username: admin, password: admin123)")
        
        # Buat default thresholds
        default_thresholds = [
            {'parameter': 'ph', 'min_value': 6.0, 'max_value': 9.0, 'unit': 'pH'},
            {'parameter': 'temperature', 'min_value': 0.0, 'max_value': 30.0, 'unit': '°C'},
            {'parameter': 'tds', 'min_value': 0.0, 'max_value': 2000.0, 'unit': 'ppm'}
        ]
        
        for thresh in default_thresholds:
            if not Threshold.query.filter_by(parameter=thresh['parameter']).first():
                threshold = Threshold(**thresh)
                db.session.add(threshold)
        
        print("✓ Default thresholds created")
        
        # Buat device status
        if not DeviceStatus.query.first():
            device = DeviceStatus(
                device_name='ESP32-IPAL-01',
                status='offline',
                signal_strength=0
            )
            db.session.add(device)
            print("✓ Device status initialized")
        
        db.session.commit()
        print("✓ Database initialized successfully!")


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return "Page not found", 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return "Internal server error", 500


# ==================== MAIN ====================

if __name__ == '__main__':
    init_db()
    
    print("\n" + "="*50)
    print("IPAL Monitoring System - Server Starting")
    print("="*50)
    print("Access the application at: http://localhost:5000")
    print("Default login - Username: admin, Password: admin123")
    print("="*50 + "\n")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)