"""
Printer API endpoints - BambuLab H2D integration
Supports both LAN Only Mode (MQTT) and Cloud Mode (via Bambu Studio local connection)

For Cloud Mode: We'll try to detect printer status through local network discovery
or provide a manual status update option.
"""

from flask import Blueprint, jsonify, request
import os
import json
import time
import socket
from datetime import datetime, timedelta

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("Warning: paho-mqtt not installed. Install with: pip install paho-mqtt")

bp = Blueprint('printer', __name__)

# BambuLab configuration
PRINTER_IP = os.environ.get('BAMBU_PRINTER_IP', '')
PRINTER_ACCESS_CODE = os.environ.get('BAMBU_ACCESS_CODE', '')
PRINTER_SERIAL = os.environ.get('BAMBU_PRINTER_SERIAL', '')
MQTT_PORT = 8883  # BambuLab uses port 8883 for MQTT over TLS
HTTP_PORT = 80    # Try HTTP port for cloud mode

# Cache for printer status
_printer_cache = {
    'status': 'IDLE',
    'jobName': None,
    'progress': 0,
    'eta': None,
    'nozzleTemp': 0,
    'bedTemp': 0,
    'filament': None,
    'alert': None,
    'last_update': None,
    'connected': False,
    'mode': 'unknown'  # 'lan', 'cloud', or 'unknown'
}

# MQTT client instance
_mqtt_client = None
_mqtt_connected = False

def on_mqtt_connect(client, userdata, flags, rc):
    """Callback when MQTT connects"""
    global _mqtt_connected
    if rc == 0:
        _mqtt_connected = True
        _printer_cache['mode'] = 'lan'
        print(f"Connected to BambuLab printer at {PRINTER_IP} (LAN Mode)")
        # Subscribe to printer status topics
        if PRINTER_SERIAL:
            client.subscribe(f"device/{PRINTER_SERIAL}/report")
            client.subscribe(f"device/{PRINTER_SERIAL}/status")
    else:
        _mqtt_connected = False
        print(f"Failed to connect to MQTT broker: {rc}")

def on_mqtt_message(client, userdata, msg):
    """Callback when MQTT message is received"""
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        update_printer_status_from_mqtt(payload)
    except Exception as e:
        print(f"Error parsing MQTT message: {e}")

def on_mqtt_disconnect(client, userdata, rc):
    """Callback when MQTT disconnects"""
    global _mqtt_connected
    _mqtt_connected = False
    print("Disconnected from MQTT broker")

def update_printer_status_from_mqtt(data):
    """Update printer cache from MQTT data"""
    global _printer_cache
    
    if 'print' in data:
        print_data = data['print']
        _printer_cache['status'] = print_data.get('mc_print_stage', 'IDLE')
        _printer_cache['progress'] = print_data.get('mc_percent', 0)
        _printer_cache['jobName'] = print_data.get('subtask_name', None)
        
        remaining = print_data.get('mc_remaining_time', 0)
        if remaining > 0:
            eta_minutes = remaining
            hours = eta_minutes // 60
            minutes = eta_minutes % 60
            _printer_cache['eta'] = f"{hours:02d}:{minutes:02d}"
        else:
            _printer_cache['eta'] = None
    
    if 'temperature' in data:
        temp_data = data['temperature']
        _printer_cache['nozzleTemp'] = temp_data.get('nozzle_temper', 0)
        _printer_cache['bedTemp'] = temp_data.get('bed_temper', 0)
    
    if 'ams' in data:
        ams_data = data['ams']
        _printer_cache['filament'] = ams_data.get('tray_now', '--')
    
    _printer_cache['last_update'] = datetime.now().isoformat()
    _printer_cache['connected'] = True

def check_printer_reachable(ip, port=80, timeout=2):
    """Check if printer is reachable on the network"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def try_http_status(ip):
    """Try to get status via HTTP (for cloud mode printers)"""
    try:
        import requests
        
        # Try common endpoints that might work even in cloud mode
        endpoints = [
            f"http://{ip}/api/v1/status",
            f"http://{ip}/status",
            f"http://{ip}/api/status",
        ]
        
        for url in endpoints:
            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    update_printer_status_from_http(data)
                    _printer_cache['mode'] = 'cloud'
                    return True
            except:
                continue
    except ImportError:
        pass
    except Exception as e:
        print(f"HTTP status check failed: {e}")
    
    return False

def update_printer_status_from_http(data):
    """Update printer cache from HTTP API response"""
    global _printer_cache
    
    _printer_cache['status'] = data.get('status', 'IDLE')
    _printer_cache['progress'] = data.get('progress', 0)
    _printer_cache['jobName'] = data.get('job_name', None)
    _printer_cache['nozzleTemp'] = data.get('nozzle_temp', 0)
    _printer_cache['bedTemp'] = data.get('bed_temp', 0)
    _printer_cache['last_update'] = datetime.now().isoformat()
    _printer_cache['connected'] = True

def init_mqtt_client():
    """Initialize and connect MQTT client (for LAN Only Mode)"""
    global _mqtt_client, _mqtt_connected
    
    if not MQTT_AVAILABLE:
        return False
    
    if not PRINTER_IP:
        return False
    
    if not PRINTER_SERIAL or not PRINTER_ACCESS_CODE:
        # Can't use MQTT without serial and access code
        return False
    
    if _mqtt_client and _mqtt_connected:
        return True
    
    try:
        client_id = f"wtl-s-lcars-{int(time.time())}"
        _mqtt_client = mqtt.Client(client_id=client_id)
        
        _mqtt_client.on_connect = on_mqtt_connect
        _mqtt_client.on_message = on_mqtt_message
        _mqtt_client.on_disconnect = on_mqtt_disconnect
        
        _mqtt_client.username_pw_set("bblp", PRINTER_ACCESS_CODE)
        _mqtt_client.tls_set()
        _mqtt_client.connect(PRINTER_IP, MQTT_PORT, 60)
        _mqtt_client.loop_start()
        
        time.sleep(2)
        return _mqtt_connected
    except Exception as e:
        print(f"MQTT connection failed (printer may be in cloud mode): {e}")
        return False

def get_printer_status():
    """
    Get printer status - tries multiple methods:
    1. MQTT (if LAN Only Mode)
    2. HTTP API (if cloud mode with local access)
    3. Returns cached data if printer not reachable
    """
    global _printer_cache
    
    # Check if cache is stale
    if _printer_cache.get('last_update'):
        last_update = datetime.fromisoformat(_printer_cache['last_update'])
        if datetime.now() - last_update > timedelta(seconds=60):
            _printer_cache['connected'] = False
    
    if not PRINTER_IP:
        return _printer_cache
    
    # Try MQTT first (LAN Only Mode)
    if not _mqtt_connected:
        init_mqtt_client()
    
    # If MQTT connected, return cached data (updated via callbacks)
    if _mqtt_connected:
        return _printer_cache
    
    # Try HTTP (for cloud mode printers that might expose local endpoints)
    if check_printer_reachable(PRINTER_IP):
        try_http_status(PRINTER_IP)
    
    return _printer_cache

def send_mqtt_command(command, params=None):
    """Send command to printer via MQTT (only works in LAN Only Mode)"""
    if not _mqtt_connected or not _mqtt_client:
        return False
    
    try:
        topic = f"device/{PRINTER_SERIAL}/request"
        payload = {
            "pushing": {
                "sequence_id": str(int(time.time())),
                "command": command
            }
        }
        
        if params:
            payload["pushing"].update(params)
        
        _mqtt_client.publish(topic, json.dumps(payload))
        return True
    except Exception as e:
        print(f"Error sending MQTT command: {e}")
        return False

def control_printer(action):
    """Send control command to printer"""
    # Only works in LAN Only Mode via MQTT
    if not _mqtt_connected:
        return False
    
    command_map = {
        'pause': 'pause',
        'resume': 'resume',
        'stop': 'stop'
    }
    
    command = command_map.get(action)
    if not command:
        return False
    
    return send_mqtt_command(command)

@bp.route('/status', methods=['GET'])
def get_status():
    """Get current printer status"""
    try:
        status = get_printer_status()
        return jsonify({
            'status': status['status'],
            'jobName': status['jobName'],
            'progress': status['progress'],
            'eta': status['eta'],
            'nozzleTemp': status['nozzleTemp'],
            'bedTemp': status['bedTemp'],
            'filament': status['filament'],
            'alert': status.get('alert'),
            'connected': status.get('connected', False),
            'mode': status.get('mode', 'unknown')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/status', methods=['POST'])
def update_status():
    """Manually update printer status (for cloud mode when auto-detection doesn't work)"""
    try:
        data = request.get_json()
        
        if 'status' in data:
            _printer_cache['status'] = data['status']
        if 'jobName' in data:
            _printer_cache['jobName'] = data['jobName']
        if 'progress' in data:
            _printer_cache['progress'] = data['progress']
        if 'eta' in data:
            _printer_cache['eta'] = data['eta']
        if 'nozzleTemp' in data:
            _printer_cache['nozzleTemp'] = data['nozzleTemp']
        if 'bedTemp' in data:
            _printer_cache['bedTemp'] = data['bedTemp']
        if 'filament' in data:
            _printer_cache['filament'] = data['filament']
        
        _printer_cache['last_update'] = datetime.now().isoformat()
        _printer_cache['connected'] = True
        _printer_cache['mode'] = 'manual'
        
        return jsonify({'status': 'updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/pause', methods=['POST'])
def pause():
    """Pause current print job (LAN Only Mode only)"""
    try:
        if not _mqtt_connected:
            return jsonify({
                'error': 'Printer control requires LAN Only Mode. Your printer appears to be in cloud mode.',
                'note': 'To control the printer, enable LAN Only Mode in Settings > Network. You can still monitor status in cloud mode.'
            }), 400
        
        success = control_printer('pause')
        if success:
            return jsonify({'status': 'paused'})
        else:
            return jsonify({'error': 'Failed to pause printer'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/resume', methods=['POST'])
def resume():
    """Resume paused print job (LAN Only Mode only)"""
    try:
        if not _mqtt_connected:
            return jsonify({
                'error': 'Printer control requires LAN Only Mode. Your printer appears to be in cloud mode.',
                'note': 'To control the printer, enable LAN Only Mode in Settings > Network. You can still monitor status in cloud mode.'
            }), 400
        
        success = control_printer('resume')
        if success:
            return jsonify({'status': 'resumed'})
        else:
            return jsonify({'error': 'Failed to resume printer'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/stop', methods=['POST'])
def stop():
    """Stop current print job (LAN Only Mode only)"""
    try:
        if not _mqtt_connected:
            return jsonify({
                'error': 'Printer control requires LAN Only Mode. Your printer appears to be in cloud mode.',
                'note': 'To control the printer, enable LAN Only Mode in Settings > Network. You can still monitor status in cloud mode.'
            }), 400
        
        success = control_printer('stop')
        if success:
            return jsonify({'status': 'stopped'})
        else:
            return jsonify({'error': 'Failed to stop printer'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config', methods=['GET'])
def get_config():
    """Get current printer configuration (for debugging)"""
    return jsonify({
        'printer_ip': PRINTER_IP if PRINTER_IP else 'NOT CONFIGURED',
        'printer_serial': PRINTER_SERIAL if PRINTER_SERIAL else 'NOT CONFIGURED',
        'has_access_code': bool(PRINTER_ACCESS_CODE),
        'mqtt_available': MQTT_AVAILABLE,
        'mqtt_connected': _mqtt_connected,
        'current_mode': _printer_cache.get('mode', 'unknown'),
        'note': 'For cloud mode: Set BAMBU_PRINTER_IP to your printer IP. Status monitoring will work, but control requires LAN Only Mode.'
    })
