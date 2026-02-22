"""
System API endpoints - CPU, RAM, disk, network, uptime, etc.
"""

from flask import Blueprint, jsonify, request
import psutil
import platform
import subprocess
import socket
import os
from datetime import datetime, timedelta
import json

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'settings.json')

bp = Blueprint('system', __name__)

def get_cpu_temp():
    """Get CPU temperature from Raspberry Pi"""
    try:
        # Try reading from thermal zone
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000.0
            return round(temp, 1)
    except:
        try:
            # Try vcgencmd (Raspberry Pi specific)
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                temp_str = result.stdout.strip()
                temp = float(temp_str.split('=')[1].split("'")[0])
                return round(temp, 1)
        except:
            pass
    return None

def get_uptime():
    """Get system uptime"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            return uptime_seconds
    except:
        return None

def format_uptime(seconds):
    """Format uptime as human-readable string"""
    if seconds is None:
        return "00:00:00", "--"
    
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    formatted = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    detailed = f"{days}d {hours}h {minutes}m {secs}s"
    
    return formatted, detailed

def get_disk_usage():
    """Get disk usage"""
    try:
        disk = psutil.disk_usage('/')
        total_gb = disk.total / (1024**3)
        used_gb = disk.used / (1024**3)
        percent = disk.percent
        
        return {
            'total': f"{total_gb:.1f} GB",
            'used': f"{used_gb:.1f} GB",
            'percent': round(percent, 1)
        }
    except:
        return {'total': '--', 'used': '--', 'percent': 0}

def get_network_info():
    """Get network interface information"""
    try:
        # Get WLAN interface (usually wlan0 or similar)
        # We can find it by looking for wireless extensions in /proc/net/wireless or just trying common names
        wlan_interface = None
        
        # Try to find wireless interface using psutil first
        interfaces = psutil.net_if_addrs()
        for interface_name, addresses in interfaces.items():
            if 'wlan' in interface_name.lower() or 'wifi' in interface_name.lower():
                wlan_interface = interface_name
                break
        
        # If not found via name, try iwconfig on all interfaces
        if not wlan_interface:
            try:
                # List all interfaces
                result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=2)
                for line in result.stdout.split('\n'):
                    if 'IEEE 802.11' in line:
                        wlan_interface = line.split()[0]
                        break
            except:
                pass
        
        # Fallback to wlan0 if still not found
        if not wlan_interface:
            wlan_interface = 'wlan0'

        # Get IP address for this interface
        ip = None
        if wlan_interface in interfaces:
            for addr in interfaces[wlan_interface]:
                if addr.family == socket.AF_INET:  # IPv4
                    ip = addr.address
                    break
                    
        # Get RSSI and SSID using iwconfig
        rssi = None
        ssid = None
        
        try:
            # Try using full path to iwconfig if possible
            iwconfig_cmd = '/usr/sbin/iwconfig' if os.path.exists('/usr/sbin/iwconfig') else 'iwconfig'
            result = subprocess.run([iwconfig_cmd, wlan_interface], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                output = result.stdout
                
                # Parse SSID
                # ESSID:"WTL-S-Core"
                import re
                ssid_match = re.search(r'ESSID:"([^"]+)"', output)
                if ssid_match:
                    ssid = ssid_match.group(1)
                
                # Parse RSSI / Signal Level
                # Link Quality=42/70  Signal level=-68 dBm
                # Or: Signal level=60/100
                signal_match = re.search(r'Signal level=(-\d+|\d+)', output)
                if signal_match:
                    rssi = int(signal_match.group(1))
        except:
            pass
            
        # If iwconfig didn't work for SSID, try iwgetid
        if not ssid:
            try:
                result = subprocess.run(['iwgetid', '-r', wlan_interface], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    ssid = result.stdout.strip()
            except:
                pass
                
        return {
            'connected': ip is not None and ssid is not None,
            'ip': ip,
            'rssi': rssi,
            'ssid': ssid,
            'interface': wlan_interface
        }
    except Exception as e:
        print(f"Error getting network info: {e}")
        return {'connected': False, 'ip': None, 'rssi': None, 'ssid': None}

def check_printer_online():
    """Check if printer is reachable on network"""
    # TODO: Replace with actual printer IP/hostname
    printer_host = os.environ.get('PRINTER_HOST', '127.0.0.1')
    printer_port = int(os.environ.get('PRINTER_PORT', 8888))
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((printer_host, printer_port))
        sock.close()
        return result == 0
    except:
        return False

@bp.route('/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        # CPU usage
        cpu_load = psutil.cpu_percent(interval=1)
        
        # RAM usage
        ram = psutil.virtual_memory()
        ram_usage = ram.percent
        
        # CPU temperature
        cpu_temp = get_cpu_temp()
        if cpu_temp is None:
            cpu_temp = 0  # Fallback
        
        # Disk usage
        disk = get_disk_usage()
        
        # Network info
        wlan = get_network_info()
        
        # Printer online status
        printer_online = check_printer_online()
        
        return jsonify({
            'cpuLoad': round(cpu_load, 1),
            'ramUsage': round(ram_usage, 1),
            'cpuTemp': cpu_temp,
            'diskUsed': disk['used'],
            'diskTotal': disk['total'],
            'diskPercent': disk['percent'],
            'wlan': wlan,
            'printerOnline': printer_online
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/uptime', methods=['GET'])
def get_uptime_endpoint():
    """Get system uptime"""
    try:
        uptime_seconds = get_uptime()
        formatted, detailed = format_uptime(uptime_seconds)
        
        return jsonify({
            'formatted': formatted,
            'detailed': detailed,
            'seconds': uptime_seconds
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/time-status', methods=['GET'])
def get_time_status():
    """Check if system time is synchronized"""
    try:
        # Check if NTP is synchronized (on Linux)
        result = subprocess.run(['timedatectl', 'status'], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            status = 'ok' if 'synchronized: yes' in result.stdout.lower() else 'not synchronized'
        else:
            # Fallback: assume OK if we can't check
            status = 'ok'
        
        return jsonify({'status': status})
    except:
        # If timedatectl is not available, assume OK
        return jsonify({'status': 'ok'})

@bp.route('/reboot', methods=['POST'])
def reboot():
    """Reboot the system"""
    try:
        # Use sudo to reboot (requires proper permissions)
        subprocess.Popen(['sudo', 'reboot'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        return jsonify({'status': 'rebooting'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the system"""
    try:
        # Use sudo to shutdown (requires proper permissions)
        subprocess.Popen(['sudo', 'shutdown', '-h', 'now'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        return jsonify({'status': 'shutting down'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/standby', methods=['POST'])
def standby():
    """Put system in standby mode"""
    # This is handled by the frontend, but we can add backend logic here
    return jsonify({'status': 'standby'})

@bp.route('/settings', methods=['GET'])
def get_settings():
    """Get system settings"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/settings', methods=['POST'])
def save_settings():
    """Save system settings"""
    try:
        data = request.json
        # Ensure data directory exists
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        return jsonify({'status': 'saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/restart-server', methods=['POST'])
def restart_server():
    """Restart the Flask backend server and nginx"""
    try:
        # Restart the backend service and nginx asynchronously
        # Using a slight delay ensures the HTTP response can be sent before the process dies
        subprocess.Popen("sleep 0.5 && sudo systemctl restart nginx wtl-s-lcars-backend.service", 
                         shell=True,
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
        return jsonify({'status': 'restarting'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
