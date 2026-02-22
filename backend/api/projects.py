"""
Projects API endpoints - Project management with folder-based storage
Each project is stored as a folder containing project.json and project files
"""

from flask import Blueprint, jsonify, request, send_file, send_from_directory
import json
import os
import shutil
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename

bp = Blueprint('projects', __name__)

# Projects storage directory
PROJECTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'projects')
PROJECT_INFO_FILE = 'project.json'

def ensure_projects_dir():
    """Ensure projects directory exists"""
    os.makedirs(PROJECTS_DIR, exist_ok=True)

def get_project_dir(project_id):
    """Get the directory path for a project"""
    return os.path.join(PROJECTS_DIR, project_id)

def get_project_info_path(project_id):
    """Get the path to project.json for a project"""
    return os.path.join(get_project_dir(project_id), PROJECT_INFO_FILE)

def load_project_info(project_id):
    """Load project info from project.json"""
    info_path = get_project_info_path(project_id)
    if os.path.exists(info_path):
        try:
            with open(info_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading project info: {e}")
            return None
    return None

def save_project_info(project_id, project_info):
    """Save project info to project.json"""
    project_dir = get_project_dir(project_id)
    os.makedirs(project_dir, exist_ok=True)
    info_path = get_project_info_path(project_id)
    try:
        with open(info_path, 'w') as f:
            json.dump(project_info, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving project info: {e}")
        return False

def list_project_files(project_id):
    """List all files in a project directory (excluding project.json)"""
    project_dir = get_project_dir(project_id)
    if not os.path.exists(project_dir):
        return []
    
    files = []
    for item in os.listdir(project_dir):
        item_path = os.path.join(project_dir, item)
        if os.path.isfile(item_path) and item != PROJECT_INFO_FILE:
            stat = os.stat(item_path)
            files.append({
                'name': item,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
    return files

@bp.route('', methods=['GET'])
def get_projects():
    """Get all projects"""
    try:
        ensure_projects_dir()
        projects = []
        
        # Scan projects directory
        if os.path.exists(PROJECTS_DIR):
            for project_id in os.listdir(PROJECTS_DIR):
                project_dir = get_project_dir(project_id)
                if os.path.isdir(project_dir):
                    project_info = load_project_info(project_id)
                    if project_info:
                        # Add file count
                        files = list_project_files(project_id)
                        project_info['file_count'] = len(files)
                        projects.append(project_info)
        
        # Sort by created date (newest first)
        projects.sort(key=lambda x: x.get('created', ''), reverse=True)
        return jsonify(projects)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('', methods=['POST'])
def create_project():
    """Create a new project"""
    try:
        ensure_projects_dir()
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Project name is required'}), 400
        
        # Generate unique project ID
        project_id = secure_filename(name.lower().replace(' ', '_'))
        # Ensure uniqueness
        base_id = project_id
        counter = 1
        while os.path.exists(get_project_dir(project_id)):
            project_id = f"{base_id}_{counter}"
            counter += 1
        
        # Create project info
        project_info = {
            'id': project_id,
            'name': name,
            'status': data.get('status', 'active'),
            'active': data.get('active', True),
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'todos': data.get('todos', []),
            'description': data.get('description', '')
        }
        
        # Create project directory and save info
        if save_project_info(project_id, project_info):
            project_info['file_count'] = 0
            return jsonify(project_info), 201
        else:
            return jsonify({'error': 'Failed to create project directory'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get a specific project"""
    try:
        project_info = load_project_info(project_id)
        if not project_info:
            return jsonify({'error': 'Project not found'}), 404
        
        # Add file list
        files = list_project_files(project_id)
        project_info['files'] = files
        project_info['file_count'] = len(files)
        
        return jsonify(project_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<project_id>', methods=['PUT'])
def update_project(project_id):
    """Update a project"""
    try:
        project_info = load_project_info(project_id)
        if not project_info:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            project_info['name'] = data['name']
        if 'status' in data:
            project_info['status'] = data['status']
        if 'active' in data:
            project_info['active'] = data['active']
        if 'description' in data:
            project_info['description'] = data['description']
        if 'todos' in data:
            project_info['todos'] = data['todos']
        
        project_info['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if save_project_info(project_id, project_info):
            return jsonify(project_info)
        else:
            return jsonify({'error': 'Failed to save project'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project (removes entire folder)"""
    try:
        project_dir = get_project_dir(project_id)
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404
        
        # Remove entire project directory
        shutil.rmtree(project_dir)
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<project_id>/files', methods=['GET'])
def list_files(project_id):
    """List all files in a project"""
    try:
        files = list_project_files(project_id)
        return jsonify(files)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<project_id>/files', methods=['POST'])
def upload_file(project_id):
    """Upload a file to a project"""
    try:
        project_dir = get_project_dir(project_id)
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Secure filename
        filename = secure_filename(file.filename)
        file_path = os.path.join(project_dir, filename)
        
        # Save file
        file.save(file_path)
        
        # Update project updated timestamp
        project_info = load_project_info(project_id)
        if project_info:
            project_info['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_project_info(project_id, project_info)
        
        return jsonify({
            'status': 'uploaded',
            'filename': filename,
            'size': os.path.getsize(file_path)
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<project_id>/files/<filename>', methods=['GET'])
def download_file(project_id, filename):
    """Download a file from a project"""
    try:
        project_dir = get_project_dir(project_id)
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404
        
        file_path = os.path.join(project_dir, secure_filename(filename))
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<project_id>/files/<filename>', methods=['DELETE'])
def delete_file(project_id, filename):
    """Delete a file from a project"""
    try:
        project_dir = get_project_dir(project_id)
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404
        
        file_path = os.path.join(project_dir, secure_filename(filename))
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        if os.path.isdir(file_path):
            return jsonify({'error': 'Cannot delete directories'}), 400
        
        os.remove(file_path)
        
        # Update project updated timestamp
        project_info = load_project_info(project_id)
        if project_info:
            project_info['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_project_info(project_id, project_info)
        
        return jsonify({'status': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
