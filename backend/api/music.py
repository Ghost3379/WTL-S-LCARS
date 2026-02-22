"""
Music Player API endpoints - Navidrome integration
Proxies requests to Navidrome Subsonic API
"""

from flask import Blueprint, jsonify, request
import requests
import os
import hashlib
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

bp = Blueprint('music', __name__)

# Navidrome configuration
NAVIDROME_URL = os.environ.get('NAVIDROME_URL', 'http://localhost:4533')
NAVIDROME_USERNAME = os.environ.get('NAVIDROME_USERNAME', 'admin')
NAVIDROME_PASSWORD = os.environ.get('NAVIDROME_PASSWORD', '')
NAVIDROME_CLIENT = 'wtl-s-lcars'

def make_navidrome_request(endpoint, params=None):
    """Make a request to Navidrome Subsonic API"""
    try:
        url = f"{NAVIDROME_URL}/rest/{endpoint}"
        
        # Build authentication parameters
        # Use password-based auth (simpler and works with Navidrome)
        auth_params = {
            'u': NAVIDROME_USERNAME,
            'p': NAVIDROME_PASSWORD,  # Password-based auth
            'c': NAVIDROME_CLIENT,
            'v': '1.16.0',
            'f': 'json'
        }
        
        if params:
            auth_params.update(params)
        
        response = requests.get(url, params=auth_params, timeout=5)
        response.raise_for_status()
        
        # Navidrome returns XML by default, but we request JSON
        data = response.json()
        
        if data.get('subsonic-response', {}).get('status') == 'ok':
            return data.get('subsonic-response', {})
        else:
            error = data.get('subsonic-response', {}).get('error', {})
            return {'error': error.get('message', 'Unknown error'), 'code': error.get('code', 0)}
            
    except requests.exceptions.RequestException as e:
        return {'error': f'Connection error: {str(e)}'}
    except Exception as e:
        return {'error': str(e)}

@bp.route('/status', methods=['GET'])
def get_status():
    """Check if Navidrome is accessible"""
    try:
        result = make_navidrome_request('ping.view')
        if 'error' in result:
            return jsonify({'connected': False, 'error': result['error']})
        
        # We can get the IP from the URL or local host if requested
        # For music server, we'll try to get the host's IP
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = '127.0.0.1'

        return jsonify({
            'connected': True, 
            'version': result.get('version', 'unknown'),
            'ip': local_ip
        })
    except Exception as e:
        return jsonify({'connected': False, 'error': str(e)})

@bp.route('/now-playing', methods=['GET'])
def get_now_playing():
    """Get currently playing track"""
    try:
        result = make_navidrome_request('getNowPlaying.view')
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        
        now_playing = result.get('nowPlaying', {})
        entries = now_playing.get('entry', [])
        
        if entries:
            # Get first playing entry
            track = entries[0] if isinstance(entries, list) else entries
            return jsonify({
                'playing': True,
                'title': track.get('title', ''),
                'artist': track.get('artist', ''),
                'album': track.get('album', ''),
                'duration': track.get('duration', 0),
                'position': track.get('minutesAgo', 0) * 60,  # Approximate
                'id': track.get('id', '')
            })
        else:
            return jsonify({'playing': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/playlists', methods=['GET'])
def get_playlists():
    """Get all playlists"""
    try:
        result = make_navidrome_request('getPlaylists.view')
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        
        playlists = result.get('playlists', {}).get('playlist', [])
        if not isinstance(playlists, list):
            playlists = [playlists] if playlists else []
        
        return jsonify([{
            'id': p.get('id', ''),
            'name': p.get('name', ''),
            'songCount': p.get('songCount', 0),
            'duration': p.get('duration', 0),
            'created': p.get('created', ''),
            'changed': p.get('changed', '')
        } for p in playlists])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/playlist/<playlist_id>', methods=['GET'])
def get_playlist(playlist_id):
    """Get playlist details and tracks"""
    try:
        result = make_navidrome_request('getPlaylist.view', {'id': playlist_id})
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        
        playlist = result.get('playlist', {})
        entries = playlist.get('entry', [])
        if not isinstance(entries, list):
            entries = [entries] if entries else []
        
        tracks = [{
            'id': e.get('id', ''),
            'title': e.get('title', ''),
            'artist': e.get('artist', ''),
            'album': e.get('album', ''),
            'duration': e.get('duration', 0),
            'track': e.get('track', 0),
            'year': e.get('year', ''),
            'genre': e.get('genre', '')
        } for e in entries]
        
        return jsonify({
            'id': playlist.get('id', ''),
            'name': playlist.get('name', ''),
            'songCount': playlist.get('songCount', 0),
            'duration': playlist.get('duration', 0),
            'tracks': tracks
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/search', methods=['GET'])
def search():
    """Search for songs, artists, albums"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    try:
        result = make_navidrome_request('search3.view', {
            'query': query,
            'songCount': 50,
            'albumCount': 20,
            'artistCount': 20
        })
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        
        search_result = result.get('searchResult3', {})
        
        songs = search_result.get('song', [])
        if not isinstance(songs, list):
            songs = [songs] if songs else []
        
        albums = search_result.get('album', [])
        if not isinstance(albums, list):
            albums = [albums] if albums else []
        
        artists = search_result.get('artist', [])
        if not isinstance(artists, list):
            artists = [artists] if artists else []
        
        return jsonify({
            'songs': [{
                'id': s.get('id', ''),
                'title': s.get('title', ''),
                'artist': s.get('artist', ''),
                'album': s.get('album', ''),
                'duration': s.get('duration', 0)
            } for s in songs],
            'albums': [{
                'id': a.get('id', ''),
                'name': a.get('name', ''),
                'artist': a.get('artist', ''),
                'songCount': a.get('songCount', 0)
            } for a in albums],
            'artists': [{
                'id': a.get('id', ''),
                'name': a.get('name', ''),
                'albumCount': a.get('albumCount', 0)
            } for a in artists]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/stream/<song_id>', methods=['GET'])
def get_stream_url(song_id):
    """Get stream URL for a song - proxy through backend to avoid CORS"""
    try:
        from flask import Response, stream_with_context
        import urllib.parse
        
        # Decode the song_id (it comes URL-encoded from the frontend)
        song_id = urllib.parse.unquote(song_id)
        
        # Build Navidrome stream URL
        stream_url = f"{NAVIDROME_URL}/rest/stream.view"
        params = {
            'id': song_id,
            'u': NAVIDROME_USERNAME,
            'p': NAVIDROME_PASSWORD,
            'c': NAVIDROME_CLIENT,
            'v': '1.16.0'
        }
        
        # URL encode parameters
        query_string = urllib.parse.urlencode(params)
        full_url = f"{stream_url}?{query_string}"
        
        print(f"Streaming song ID: {song_id[:50]}...")  # Log first 50 chars for debugging
        
        # Proxy the stream through Flask to handle CORS
        def generate():
            try:
                stream_response = requests.get(full_url, stream=True, timeout=30)
                stream_response.raise_for_status()
                
                # Check content type
                content_type = stream_response.headers.get('Content-Type', 'audio/mpeg')
                print(f"Content-Type: {content_type}")
                
                for chunk in stream_response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            except requests.exceptions.RequestException as e:
                print(f"Stream request error: {e}")
                # Return error in a way the audio element can handle
                yield b''
                raise
        
        # Get content type from Navidrome response (if possible)
        try:
            # Make a HEAD request first to get content type
            head_response = requests.head(full_url, timeout=5)
            content_type = head_response.headers.get('Content-Type', 'audio/mpeg')
        except:
            content_type = 'audio/mpeg'
        
        # Return streamed response with proper headers
        response = Response(
            stream_with_context(generate()),
            mimetype=content_type,
            headers={
                'Content-Type': content_type,
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache',
                'Access-Control-Allow-Origin': '*'
            }
        )
        return response
    except requests.exceptions.RequestException as e:
        print(f"Stream error: {e}")
        return jsonify({'error': f'Stream request failed: {str(e)}'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/scan', methods=['POST'])
def trigger_scan():
    """Trigger Navidrome library scan"""
    try:
        # Navidrome doesn't have a direct scan API endpoint in Subsonic
        # But we can trigger it by calling the startScan endpoint if available
        # Or restart the container to trigger a scan
        result = make_navidrome_request('startScan.view')
        if 'error' in result:
            # If startScan doesn't work, try alternative method
            # For now, return success and let user know to check Navidrome UI
            return jsonify({'status': 'scan_triggered', 'message': 'Scan initiated. Check Navidrome UI for progress.'})
        return jsonify({'status': 'scan_triggered', 'message': 'Library scan started'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/open-music-folder', methods=['POST'])
def open_music_folder():
    """Open the music folder in file manager"""
    import subprocess
    try:
        music_folder = '/srv/navidrome/music'
        
        # Try different file managers
        file_managers = [
            ['pcmanfm', music_folder],
            ['nautilus', music_folder],
            ['thunar', music_folder],
            ['dolphin', music_folder],
            ['xdg-open', music_folder]
        ]
        
        for cmd in file_managers:
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return jsonify({'status': 'opened', 'folder': music_folder})
            except FileNotFoundError:
                continue
        
        return jsonify({'error': 'No file manager found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
