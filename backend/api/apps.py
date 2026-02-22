"""
App launcher API endpoints
KiCad, Bambu Studio, PDF viewer, etc.
"""

from flask import Blueprint, jsonify, request
import subprocess
import os
import json

bp = Blueprint('apps', __name__)

# Application paths (adjust based on your system)
KICAD_PATH = os.environ.get('KICAD_PATH', '/usr/bin/kicad')
BAMBU_STUDIO_PATH = os.environ.get('BAMBU_STUDIO_PATH', '/usr/bin/bambu-studio')
PDF_VIEWER_PATH = os.environ.get('PDF_VIEWER_PATH', '/usr/bin/evince')

# Last project tracking
LAST_PROJECTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'last_projects.json')

def ensure_data_dir():
    """Ensure data directory exists"""
    data_dir = os.path.dirname(LAST_PROJECTS_FILE)
    os.makedirs(data_dir, exist_ok=True)

def get_last_project(app_name):
    """Get last opened project for an app"""
    ensure_data_dir()
    try:
        if os.path.exists(LAST_PROJECTS_FILE):
            with open(LAST_PROJECTS_FILE, 'r') as f:
                projects = json.load(f)
                return projects.get(app_name)
    except:
        pass
    return None

def save_last_project(app_name, project_path):
    """Save last opened project for an app"""
    ensure_data_dir()
    try:
        projects = {}
        if os.path.exists(LAST_PROJECTS_FILE):
            with open(LAST_PROJECTS_FILE, 'r') as f:
                projects = json.load(f)
        
        projects[app_name] = project_path
        
        with open(LAST_PROJECTS_FILE, 'w') as f:
            json.dump(projects, f, indent=2)
        return True
    except:
        return False

def launch_app(command, args=None):
    """Launch an application"""
    try:
        cmd = [command]
        if args:
            cmd.extend(args)
        
        # Launch in background (detached)
        subprocess.Popen(cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True)
        return True
    except Exception as e:
        print(f"Error launching app: {e}")
        return False

@bp.route('/kicad', methods=['POST'])
def open_kicad():
    """Open KiCad"""
    try:
        if not os.path.exists(KICAD_PATH):
            return jsonify({'error': 'KiCad not found'}), 404
        
        success = launch_app(KICAD_PATH)
        if success:
            return jsonify({'status': 'opened'})
        else:
            return jsonify({'error': 'Failed to open KiCad'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/kicad/last-project', methods=['POST'])
def open_kicad_last_project():
    """Open KiCad with last project"""
    try:
        if not os.path.exists(KICAD_PATH):
            return jsonify({'error': 'KiCad not found'}), 404
        
        last_project = get_last_project('kicad')
        if last_project and os.path.exists(last_project):
            success = launch_app(KICAD_PATH, [last_project])
        else:
            success = launch_app(KICAD_PATH)
        
        if success:
            return jsonify({'status': 'opened'})
        else:
            return jsonify({'error': 'Failed to open KiCad'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/bambu-studio', methods=['POST'])
def open_bambu_studio():
    """Open Bambu Studio"""
    try:
        if not os.path.exists(BAMBU_STUDIO_PATH):
            return jsonify({'error': 'Bambu Studio not found'}), 404
        
        success = launch_app(BAMBU_STUDIO_PATH)
        if success:
            return jsonify({'status': 'opened'})
        else:
            return jsonify({'error': 'Failed to open Bambu Studio'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/pdf-viewer', methods=['POST'])
def open_pdf_viewer():
    """Open PDF viewer (requires file path in request)"""
    try:
        data = request.get_json()
        pdf_path = data.get('path') if data else None
        
        if not pdf_path:
            return jsonify({'error': 'PDF path required'}), 400
        
        if not os.path.exists(pdf_path):
            return jsonify({'error': 'PDF file not found'}), 404
        
        success = launch_app(PDF_VIEWER_PATH, [pdf_path])
        if success:
            return jsonify({'status': 'opened'})
        else:
            return jsonify({'error': 'Failed to open PDF viewer'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
