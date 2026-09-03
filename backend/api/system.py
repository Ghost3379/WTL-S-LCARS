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
import threading
import time
import re

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'settings.json')
REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

bp = Blueprint('system', __name__)

update_lock = threading.Lock()

UPDATE_STATE = {
    'status': 'idle',  # 'idle', 'checking', 'updating', 'completed', 'error'
    'progress': 'Idle',
    'log': [],
    'reboot_required': False,
    'last_check': None,
    'system_updates': {
        'available': False,
        'count': 0,
        'packages': []
    },
    'ui_updates': {
        'available': False,
        'current_commit': '--',
        'remote_commit': '--',
        'commits_behind': 0,
        'changelog': [],
        'has_local_changes': False
    }
}

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


def log_update_msg(msg):
    """Add a timestamped message to the update log"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted = f"[{timestamp}] {msg}"
    with update_lock:
        UPDATE_STATE['log'].append(formatted)
        if len(UPDATE_STATE['log']) > 500:
            UPDATE_STATE['log'] = UPDATE_STATE['log'][-500:]


def perform_check_updates():
    """Worker function to check for Raspberry Pi system & WTL UI updates"""
    with update_lock:
        UPDATE_STATE['status'] = 'checking'
        UPDATE_STATE['progress'] = 'Checking Raspberry Pi system package updates...'
        UPDATE_STATE['log'] = []
    
    log_update_msg("=== LCARS TELEMETRY: UPDATE CHECK INITIATED ===")
    
    # 1. Check Raspberry Pi System Package Updates (apt)
    try:
        log_update_msg("Updating apt package lists (sudo apt-get update)...")
        res_apt_upd = subprocess.run(['sudo', '-n', 'apt-get', 'update'], 
                                     capture_output=True, text=True, timeout=45)
        if res_apt_upd.returncode != 0 and res_apt_upd.stderr:
            log_update_msg(f"Apt update notice: {res_apt_upd.stderr.strip()[:200]}")
            
        log_update_msg("Querying upgradable packages (apt list --upgradable)...")
        res_apt_list = subprocess.run(['apt', 'list', '--upgradable'], 
                                      capture_output=True, text=True, timeout=20)
        
        packages = []
        if res_apt_list.returncode == 0:
            lines = res_apt_list.stdout.splitlines()
            for line in lines:
                if 'upgradable from:' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        pkg_info = parts[0]
                        pkg_name = pkg_info.split('/')[0]
                        new_ver = parts[1]
                        
                        old_ver = '--'
                        match = re.search(r'upgradable from:\s*([^\]]+)', line)
                        if match:
                            old_ver = match.group(1).strip()
                            
                        packages.append({
                            'name': pkg_name,
                            'new_version': new_ver,
                            'old_version': old_ver,
                            'info': pkg_info
                        })
                        
        with update_lock:
            UPDATE_STATE['system_updates'] = {
                'available': len(packages) > 0,
                'count': len(packages),
                'packages': packages
            }
        log_update_msg(f"System check finished: {len(packages)} upgradable package(s) detected.")
    except Exception as e:
        log_update_msg(f"Error checking system package updates: {e}")
        with update_lock:
            UPDATE_STATE['system_updates'] = {'available': False, 'count': 0, 'packages': []}

    # 2. Check WTL UI Repository Updates (git)
    with update_lock:
        UPDATE_STATE['progress'] = 'Checking WTL UI git repository...'
    try:
        log_update_msg(f"Checking WTL UI repository at {REPO_PATH}...")
        
        subprocess.run(['git', 'fetch', 'origin'], cwd=REPO_PATH, 
                       capture_output=True, text=True, timeout=20)
        
        cur_commit_res = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], 
                                        cwd=REPO_PATH, capture_output=True, text=True, timeout=5)
        cur_commit = cur_commit_res.stdout.strip() if cur_commit_res.returncode == 0 else '--'
        
        branch_res = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                    cwd=REPO_PATH, capture_output=True, text=True, timeout=5)
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else 'main'
        if branch == 'HEAD':
            branch = 'main'
            
        target_remote = f"origin/{branch}"
        
        remote_commit_res = subprocess.run(['git', 'rev-parse', '--short', target_remote], 
                                           cwd=REPO_PATH, capture_output=True, text=True, timeout=5)
        remote_commit = remote_commit_res.stdout.strip() if remote_commit_res.returncode == 0 else cur_commit
        
        behind_res = subprocess.run(['git', 'rev-list', '--count', f"HEAD..{target_remote}"], 
                                    cwd=REPO_PATH, capture_output=True, text=True, timeout=5)
        try:
            commits_behind = int(behind_res.stdout.strip()) if behind_res.returncode == 0 else 0
        except ValueError:
            commits_behind = 0
            
        changelog = []
        if commits_behind > 0:
            log_res = subprocess.run(['git', 'log', f"HEAD..{target_remote}", '--pretty=format:%h - %s (%cr)', '-n', '15'], 
                                     cwd=REPO_PATH, capture_output=True, text=True, timeout=5)
            if log_res.returncode == 0 and log_res.stdout:
                changelog = log_res.stdout.splitlines()
                
        status_res = subprocess.run(['git', 'status', '--porcelain'], 
                                    cwd=REPO_PATH, capture_output=True, text=True, timeout=5)
        has_local_changes = bool(status_res.returncode == 0 and status_res.stdout.strip())
        
        with update_lock:
            UPDATE_STATE['ui_updates'] = {
                'available': commits_behind > 0,
                'current_commit': cur_commit,
                'remote_commit': remote_commit,
                'commits_behind': commits_behind,
                'changelog': changelog,
                'has_local_changes': has_local_changes
            }
        log_update_msg(f"WTL UI check finished: Current={cur_commit}, Remote={remote_commit}, Commits behind={commits_behind}.")
    except Exception as e:
        log_update_msg(f"Error checking WTL UI updates: {e}")

    # 3. Check Reboot Required
    reboot_req = os.path.exists('/var/run/reboot-required')

    with update_lock:
        UPDATE_STATE['reboot_required'] = reboot_req
        UPDATE_STATE['last_check'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        UPDATE_STATE['status'] = 'idle'
        UPDATE_STATE['progress'] = 'Check completed.'
        
    log_update_msg("=== LCARS TELEMETRY: CHECK COMPLETED ===")


def perform_apply_updates(target):
    """Worker function to apply system and/or WTL UI updates"""
    with update_lock:
        UPDATE_STATE['status'] = 'updating'
        UPDATE_STATE['progress'] = f"Applying {target} updates..."
        UPDATE_STATE['log'] = []

    log_update_msg(f"=== LCARS TELEMETRY: APPLYING UPDATES (Target: {target.upper()}) ===")

    if target in ('wtl_ui', 'all'):
        try:
            log_update_msg("Updating WTL UI repository via git...")
            status_res = subprocess.run(['git', 'status', '--porcelain'], 
                                        cwd=REPO_PATH, capture_output=True, text=True, timeout=5)
            if status_res.returncode == 0 and status_res.stdout.strip():
                log_update_msg("Local uncommitted modifications detected. Stashing local changes before pull...")
                subprocess.run(['git', 'stash'], cwd=REPO_PATH, capture_output=True, text=True, timeout=10)

            log_update_msg("Executing git pull origin main...")
            pull_proc = subprocess.Popen(['git', 'pull', 'origin', 'main'], 
                                         cwd=REPO_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in iter(pull_proc.stdout.readline, ''):
                if line:
                    log_update_msg(f"[GIT] {line.strip()}")
            pull_proc.stdout.close()
            pull_proc.wait()
            log_update_msg("WTL UI git update completed.")

            # Sync updated repository files to /var/www/html if web root is separated
            www_path = '/var/www/html'
            if os.path.exists(www_path) and os.path.abspath(www_path) != REPO_PATH:
                log_update_msg("Syncing updated repository files to web server root (/var/www/html)...")
                subprocess.run(f"sudo cp -r {REPO_PATH}/* {www_path}/ && sudo chown -R www-data:www-data {www_path}", 
                               shell=True, capture_output=True, text=True)
                log_update_msg("Web root sync complete.")
        except Exception as e:
            log_update_msg(f"Error during WTL UI update: {e}")

    if target in ('system', 'all'):
        try:
            log_update_msg("Upgrading Raspberry Pi system packages (sudo apt-get upgrade -y)...")
            apt_proc = subprocess.Popen('sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y', 
                                        shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in iter(apt_proc.stdout.readline, ''):
                if line:
                    clean_line = line.strip()
                    if clean_line:
                        log_update_msg(f"[APT] {clean_line}")
            apt_proc.stdout.close()
            apt_proc.wait()
            log_update_msg("Raspberry Pi system packages upgrade completed.")
        except Exception as e:
            log_update_msg(f"Error during system package upgrade: {e}")

    reboot_req = os.path.exists('/var/run/reboot-required')
    with update_lock:
        UPDATE_STATE['reboot_required'] = reboot_req
        UPDATE_STATE['status'] = 'completed'
        UPDATE_STATE['progress'] = 'Updates completed.'

    log_update_msg("=== LCARS TELEMETRY: ALL UPDATES COMPLETED ===")
    if reboot_req:
        log_update_msg("[ALERT] System restart is recommended to finalize kernel/system updates.")

    perform_check_updates()


@bp.route('/updates/status', methods=['GET'])
def get_updates_status():
    """Get current update status, progress, logs, and update info"""
    with update_lock:
        return jsonify(UPDATE_STATE)


@bp.route('/updates/check', methods=['POST'])
def check_updates_endpoint():
    """Trigger background check for available system & UI updates"""
    with update_lock:
        if UPDATE_STATE['status'] in ('checking', 'updating'):
            return jsonify({'status': UPDATE_STATE['status'], 'message': 'Operation already in progress'}), 409

    t = threading.Thread(target=perform_check_updates, daemon=True)
    t.start()
    return jsonify({'status': 'checking', 'message': 'Update check initiated'})


@bp.route('/updates/apply', methods=['POST'])
def apply_updates_endpoint():
    """Trigger background execution of system and/or UI updates"""
    data = request.json or {}
    target = data.get('target', 'all')
    if target not in ('system', 'wtl_ui', 'all'):
        return jsonify({'error': 'Invalid target specified'}), 400

    with update_lock:
        if UPDATE_STATE['status'] in ('checking', 'updating'):
            return jsonify({'status': UPDATE_STATE['status'], 'message': 'Operation already in progress'}), 409

    t = threading.Thread(target=perform_apply_updates, args=(target,), daemon=True)
    t.start()
    return jsonify({'status': 'updating', 'target': target, 'message': f"Update process initiated for {target}"})

