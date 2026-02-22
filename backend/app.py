#!/usr/bin/env python3
"""
Wayne Tech Lab - Lab Core Access Retrieval System (WTl-S-LCARS) - Backend Server
Flask API server for WTl-S-LCARS system
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import sys

# Import API route modules
from api import system, printer, pironman, projects, minecraft, apps, music, servers, network

app = Flask(__name__, static_folder='../', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Register API blueprints
app.register_blueprint(system.bp, url_prefix='/api/system')
app.register_blueprint(printer.bp, url_prefix='/api/printer')
app.register_blueprint(pironman.bp, url_prefix='/api/pironman')
app.register_blueprint(projects.bp, url_prefix='/api/projects')
app.register_blueprint(minecraft.bp, url_prefix='/api/minecraft')
app.register_blueprint(apps.bp, url_prefix='/api/apps')
app.register_blueprint(music.bp, url_prefix='/api/music')
app.register_blueprint(servers.bp, url_prefix='/api/servers')
app.register_blueprint(network.bp, url_prefix='/api/network')

# Serve static files (HTML, CSS, JS, assets)
@app.route('/')
def index():
    return send_from_directory('../', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files from project root"""
    return send_from_directory('../', path)

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Run on all interfaces (0.0.0.0) so it's accessible
    app.run(host='0.0.0.0', port=port, debug=True)
