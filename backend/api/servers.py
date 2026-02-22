"""
Server control API endpoints
Controls Docker containers for Navidrome and Nextcloud
"""

from flask import Blueprint, jsonify, request
import subprocess
import os

bp = Blueprint('servers', __name__)

# Docker container names
NAVIDROME_CONTAINER = 'navidrome'
NEXTCLOUD_CONTAINER = 'nextcloud-app'
NEXTCLOUD_DB_CONTAINER = 'nextcloud-db'

def is_container_running(container_name):
    """Check if a Docker container is running"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return container_name in result.stdout
    except:
        return False

def get_container_ip(container_name):
    """Get the internal IP address of a Docker container"""
    try:
        result = subprocess.run(
            ['docker', 'inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', container_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip() or 'N/A'
        return 'N/A'
    except:
        return 'unknown'

def get_container_status(container_name):
    """Get detailed container status"""
    try:
        result = subprocess.run(
            ['docker', 'inspect', '--format', '{{.State.Status}}', container_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return 'not_found'
    except:
        return 'unknown'

def get_container_version(container_name):
    """Get container image version"""
    try:
        result = subprocess.run(
            ['docker', 'inspect', '--format', '{{.Config.Image}}', container_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            image = result.stdout.strip()
            # Try to get version from image tag
            if ':' in image:
                return image.split(':')[-1]
            return image
        return None
    except:
        return None

def get_container_logs(container_name, lines=100):
    """Get container logs"""
    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', str(lines), container_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.split('\n')
        return []
    except:
        return []

# Navidrome endpoints
@bp.route('/navidrome/status', methods=['GET'])
def navidrome_status():
    """Get Navidrome container status"""
    try:
        running = is_container_running(NAVIDROME_CONTAINER)
        status = get_container_status(NAVIDROME_CONTAINER)
        version = get_container_version(NAVIDROME_CONTAINER)
        
        ip = get_container_ip(NAVIDROME_CONTAINER) if running else 'N/A'
        
        return jsonify({
            'running': running,
            'status': status,
            'version': version or 'unknown',
            'ip': ip
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/navidrome/start', methods=['POST'])
def navidrome_start():
    """Start Navidrome container"""
    try:
        if is_container_running(NAVIDROME_CONTAINER):
            return jsonify({'error': 'Navidrome is already running'}), 400
        
        result = subprocess.run(
            ['docker', 'start', NAVIDROME_CONTAINER],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'starting'})
        else:
            return jsonify({'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/navidrome/stop', methods=['POST'])
def navidrome_stop():
    """Stop Navidrome container"""
    try:
        if not is_container_running(NAVIDROME_CONTAINER):
            return jsonify({'error': 'Navidrome is not running'}), 400
        
        result = subprocess.run(
            ['docker', 'stop', NAVIDROME_CONTAINER],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'stopped'})
        else:
            return jsonify({'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/navidrome/restart', methods=['POST'])
def navidrome_restart():
    """Restart Navidrome container"""
    try:
        result = subprocess.run(
            ['docker', 'restart', NAVIDROME_CONTAINER],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'restarting'})
        else:
            return jsonify({'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/navidrome/logs', methods=['GET'])
def navidrome_logs():
    """Get Navidrome container logs"""
    try:
        lines = request.args.get('lines', 100, type=int)
        logs = get_container_logs(NAVIDROME_CONTAINER, lines)
        return jsonify({'lines': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Nextcloud endpoints
@bp.route('/nextcloud/status', methods=['GET'])
def nextcloud_status():
    """Get Nextcloud container status"""
    try:
        running = is_container_running(NEXTCLOUD_CONTAINER)
        status = get_container_status(NEXTCLOUD_CONTAINER)
        version = get_container_version(NEXTCLOUD_CONTAINER)
        
        # Also check database status
        db_running = is_container_running(NEXTCLOUD_DB_CONTAINER)
        
        ip = get_container_ip(NEXTCLOUD_CONTAINER) if running else 'N/A'
        
        return jsonify({
            'running': running,
            'status': status,
            'version': version or 'unknown',
            'database_running': db_running,
            'ip': ip
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/nextcloud/start', methods=['POST'])
def nextcloud_start():
    """Start Nextcloud containers"""
    try:
        if is_container_running(NEXTCLOUD_CONTAINER):
            return jsonify({'error': 'Nextcloud is already running'}), 400
        
        # Start database first
        if not is_container_running(NEXTCLOUD_DB_CONTAINER):
            db_result = subprocess.run(
                ['docker', 'start', NEXTCLOUD_DB_CONTAINER],
                capture_output=True,
                text=True,
                timeout=10
            )
            if db_result.returncode != 0:
                return jsonify({'error': f'Failed to start database: {db_result.stderr}'}), 500
        
        # Start Nextcloud app
        result = subprocess.run(
            ['docker', 'start', NEXTCLOUD_CONTAINER],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'starting'})
        else:
            return jsonify({'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/nextcloud/stop', methods=['POST'])
def nextcloud_stop():
    """Stop Nextcloud containers"""
    try:
        if not is_container_running(NEXTCLOUD_CONTAINER):
            return jsonify({'error': 'Nextcloud is not running'}), 400
        
        # Stop Nextcloud app first
        result = subprocess.run(
            ['docker', 'stop', NEXTCLOUD_CONTAINER],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return jsonify({'error': result.stderr}), 500
        
        # Optionally stop database (comment out if you want to keep DB running)
        # subprocess.run(['docker', 'stop', NEXTCLOUD_DB_CONTAINER], timeout=10)
        
        return jsonify({'status': 'stopped'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/nextcloud/restart', methods=['POST'])
def nextcloud_restart():
    """Restart Nextcloud containers"""
    try:
        # Restart database first
        if is_container_running(NEXTCLOUD_DB_CONTAINER):
            subprocess.run(['docker', 'restart', NEXTCLOUD_DB_CONTAINER], timeout=10)
        
        # Restart Nextcloud app
        result = subprocess.run(
            ['docker', 'restart', NEXTCLOUD_CONTAINER],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            return jsonify({'status': 'restarting'})
        else:
            return jsonify({'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/nextcloud/logs', methods=['GET'])
def nextcloud_logs():
    """Get Nextcloud container logs"""
    try:
        lines = request.args.get('lines', 100, type=int)
        logs = get_container_logs(NEXTCLOUD_CONTAINER, lines)
        return jsonify({'lines': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
