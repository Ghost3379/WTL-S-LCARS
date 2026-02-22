"""
Minecraft server control API endpoints
PaperMC server on Raspberry Pi
"""

from flask import Blueprint, jsonify, request
import subprocess
import os
import psutil
import re

bp = Blueprint('minecraft', __name__)

# Minecraft server configuration
MC_SERVER_DIR = os.environ.get('MC_SERVER_DIR', '/opt/minecraft')
MC_SERVER_JAR = os.environ.get('MC_SERVER_JAR', 'paper.jar')
MC_SERVER_USER = os.environ.get('MC_SERVER_USER', 'minecraft')
MC_SERVER_SCREEN = os.environ.get('MC_SERVER_SCREEN', 'mcserver')
MC_SERVER_SERVICE = 'minecraft'
MC_RCON_HOST = '127.0.0.1'
MC_RCON_PORT = 25575
MC_RCON_PASSWORD = os.environ.get('MC_RCON_PASSWORD', '')

def get_local_ip():
    """Get the local IP address of the machine"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
        s.close()
        return IP
    except Exception:
        return '127.0.0.1'

def is_server_running():
    """Check if Minecraft server is running"""
    try:
        # Check systemd service first
        result = subprocess.run(
            ['systemctl', 'is-active', '--quiet', MC_SERVER_SERVICE],
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            return True
        
        # Check for screen session
        result = subprocess.run(
            ['screen', '-ls', MC_SERVER_SCREEN],
            capture_output=True,
            text=True,
            timeout=2
        )
        if MC_SERVER_SCREEN in result.stdout:
            return True
        
        # Check for java process with paper.jar
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'java' in proc.info['name'].lower():
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('paper.jar' in str(arg) for arg in cmdline):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except:
        pass
    return False

def get_server_pid():
    """Get Minecraft server PID"""
    try:
        # Find java process running paper.jar
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'java' in proc.info['name'].lower():
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('paper.jar' in str(arg) for arg in cmdline):
                        return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except:
        pass
    return None

def get_server_ram_usage():
    """Get RAM usage of Minecraft server"""
    try:
        pid = get_server_pid()
        if pid and psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            mem_info = proc.memory_info()
            return f"{mem_info.rss / (1024**3):.2f} GB"
    except:
        pass
    return "--"

def get_player_count():
    """Get player count from server using RCON or log parsing"""
    try:
        # Try RCON first
        if os.path.exists('/usr/bin/mcrcon') or os.path.exists('/usr/local/bin/mcrcon'):
            mcrcon_cmd = '/usr/bin/mcrcon' if os.path.exists('/usr/bin/mcrcon') else '/usr/local/bin/mcrcon'
            result = subprocess.run(
                [mcrcon_cmd, '-H', MC_RCON_HOST, '-P', str(MC_RCON_PORT), '-p', MC_RCON_PASSWORD, 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse output like "There are 2 of a max of 20 players online: player1, player2"
                match = re.search(r'There are (\d+) of a max of (\d+)', result.stdout)
                if match:
                    return int(match.group(1)), int(match.group(2))
        
        # Fallback: parse latest.log
        log_file = os.path.join(MC_SERVER_DIR, 'logs', 'latest.log')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Look for recent player count messages
                for line in reversed(lines[-100:]):  # Check last 100 lines
                    match = re.search(r'There are (\d+) of a max of (\d+)', line)
                    if match:
                        return int(match.group(1)), int(match.group(2))
    except:
        pass
    
    # Default fallback
    return 0, 20

@bp.route('/status', methods=['GET'])
def get_status():
    """Get Minecraft server status"""
    try:
        running = is_server_running()
        ram_usage = get_server_ram_usage() if running else "--"
        players, max_players = get_player_count() if running else (0, 0)
        ip = get_local_ip()
        
        return jsonify({
            'running': running,
            'ramUsage': ram_usage,
            'players': players,
            'maxPlayers': max_players,
            'ip': ip
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/start', methods=['POST'])
def start():
    """Start Minecraft server"""
    try:
        if is_server_running():
            return jsonify({'error': 'Server is already running'}), 400
        
        # Try systemd service first
        result = subprocess.run(
            ['sudo', 'systemctl', 'start', MC_SERVER_SERVICE],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'starting'})
        
        # Fallback: start in screen session
        jar_path = os.path.join(MC_SERVER_DIR, MC_SERVER_JAR)
        if not os.path.exists(jar_path):
            return jsonify({'error': f'Server jar not found: {jar_path}'}), 404
        
        # Start in screen session as minecraft user
        screen_cmd = f'screen -dmS {MC_SERVER_SCREEN} bash -c "cd {MC_SERVER_DIR} && java -Xms1G -Xmx4G -jar {MC_SERVER_JAR} nogui"'
        result = subprocess.run(
            ['sudo', '-u', MC_SERVER_USER, 'bash', '-c', screen_cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'starting'})
        else:
            return jsonify({'error': f'Failed to start server: {result.stderr}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/stop', methods=['POST'])
def stop():
    """Stop Minecraft server"""
    try:
        if not is_server_running():
            return jsonify({'error': 'Server is not running'}), 400
        
        # Try systemd service first
        result = subprocess.run(
            ['sudo', 'systemctl', 'stop', MC_SERVER_SERVICE],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'stopped'})
        
        # Try RCON stop command
        try:
            mcrcon_cmd = '/usr/bin/mcrcon' if os.path.exists('/usr/bin/mcrcon') else '/usr/local/bin/mcrcon'
            if os.path.exists(mcrcon_cmd):
                subprocess.run(
                    [mcrcon_cmd, '-H', MC_RCON_HOST, '-P', str(MC_RCON_PORT), '-p', MC_RCON_PASSWORD, 'stop'],
                    timeout=10
                )
                import time
                time.sleep(3)  # Wait for server to stop
                if not is_server_running():
                    return jsonify({'status': 'stopped'})
        except:
            pass
        
        # Fallback: send stop to screen session
        try:
            subprocess.run(
                ['sudo', '-u', MC_SERVER_USER, 'screen', '-S', MC_SERVER_SCREEN, '-X', 'stuff', 'stop\n'],
                timeout=5
            )
            import time
            time.sleep(3)
            if not is_server_running():
                return jsonify({'status': 'stopped'})
        except:
            pass
        
        # Last resort: kill process
        pid = get_server_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=10)
            except:
                try:
                    proc.kill()
                except:
                    pass
        
        return jsonify({'status': 'stopped'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/restart', methods=['POST'])
def restart():
    """Restart Minecraft server"""
    try:
        # Stop first
        if is_server_running():
            stop()
            import time
            time.sleep(2)  # Wait a bit
        
        # Start again
        start()
        return jsonify({'status': 'restarting'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/backup', methods=['POST'])
def backup():
    """Trigger Minecraft server backup"""
    try:
        backup_dir = os.path.join(MC_SERVER_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Run backup script if it exists
        backup_script = os.path.join(MC_SERVER_DIR, 'backup.sh')
        if os.path.exists(backup_script):
            subprocess.Popen(
                ['sudo', '-u', MC_SERVER_USER, 'bash', backup_script],
                cwd=MC_SERVER_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return jsonify({'status': 'backup started'})
        
        # Fallback: create backup manually
        world_dir = os.path.join(MC_SERVER_DIR, 'world')
        if os.path.exists(world_dir):
            backup_name = f'world-backup-$(date +%Y-%m-%d-%H%M%S).tar.gz'
            backup_path = os.path.join(backup_dir, backup_name)
            subprocess.Popen(
                ['sudo', '-u', MC_SERVER_USER, 'bash', '-c', 
                 f'cd {MC_SERVER_DIR} && tar -czf {backup_path} world'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return jsonify({'status': 'backup started'})
        else:
            return jsonify({'error': 'World directory not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/console', methods=['POST'])
def send_console_command():
    """Send command to Minecraft server console via RCON"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({'error': 'Command is required'}), 400
        
        mcrcon_cmd = '/usr/bin/mcrcon' if os.path.exists('/usr/bin/mcrcon') else '/usr/local/bin/mcrcon'
        if not os.path.exists(mcrcon_cmd):
            return jsonify({'error': 'mcrcon not found'}), 404
        
        result = subprocess.run(
            [mcrcon_cmd, '-H', MC_RCON_HOST, '-P', str(MC_RCON_PORT), '-p', MC_RCON_PASSWORD, command],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'ok', 'output': result.stdout})
        else:
            return jsonify({'error': result.stderr or 'Command failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/log', methods=['GET'])
def get_log():
    """Get recent server log entries"""
    try:
        log_file = os.path.join(MC_SERVER_DIR, 'logs', 'latest.log')
        if not os.path.exists(log_file):
            return jsonify({'error': 'Log file not found'}), 404
        
        lines = int(request.args.get('lines', 50))
        lines = min(lines, 500)  # Limit to 500 lines max
        
        with open(log_file, 'r') as f:
            log_lines = f.readlines()
            recent_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines
        
        return jsonify({
            'status': 'ok',
            'lines': recent_lines,
            'total_lines': len(log_lines)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
