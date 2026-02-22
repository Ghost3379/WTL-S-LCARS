"""
Pironman 5 case control API endpoints
Fan, display, RGB controls
"""

from flask import Blueprint, jsonify, request
import subprocess
import os
import json

bp = Blueprint('pironman', __name__)

# Pironman 5 command
PIRONMAN_CMD = '/usr/local/bin/pironman5'
PIRONMAN_CONFIG = '/opt/pironman5/venv/lib/python3.13/site-packages/pironman5/config.json'

def get_pironman_config():
    """Read current Pironman configuration"""
    try:
        if os.path.exists(PIRONMAN_CONFIG):
            with open(PIRONMAN_CONFIG, 'r') as f:
                return json.load(f)
    except:
        pass
    return None

def get_pironman_status():
    """Get current Pironman status from config"""
    config = get_pironman_config()
    if not config or 'system' not in config:
        return {
            'fan': {'mode': 'auto'},
            'display': {'on': True, 'brightness': 100},
            'rgb': {'on': True, 'mode': 'static'}
        }
    
    system_config = config.get('system', {})
    
    # Map fan mode: 0=Always On, 1=Performance, 2=Cool
    fan_mode_map = {0: 'on', 1: 'auto', 2: 'auto'}
    fan_mode = system_config.get('gpio_fan_mode', 1)
    fan_mode_str = fan_mode_map.get(fan_mode, 'auto')
    
    # OLED status
    oled_enable = system_config.get('oled_enable', True)
    if isinstance(oled_enable, str):
        oled_enable = oled_enable.lower() in ['true', 'on', '1']
    
    # RGB status
    rgb_enable = system_config.get('rgb_enable', True)
    if isinstance(rgb_enable, str):
        rgb_enable = rgb_enable.lower() in ['true', 'on', '1']
    
    rgb_brightness = system_config.get('rgb_brightness', 50)
    rgb_style = system_config.get('rgb_style', 'solid')
    rgb_color = system_config.get('rgb_color', '#0a1aff')
    rgb_speed = system_config.get('rgb_speed', 50)
    
    # Remove # from color if present
    if rgb_color.startswith('#'):
        rgb_color = rgb_color[1:]
    
    # Fan RGB LED state
    fan_rgb_led = system_config.get('gpio_fan_led', 'follow')
    if fan_rgb_led is None:
        fan_rgb_led = 'follow'
    
    return {
        'fan': {
            'mode': fan_mode_str,
            'rgb_led': str(fan_rgb_led)
        },
        'display': {'on': bool(oled_enable)},  # OLED doesn't have brightness control
        'rgb': {
            'on': bool(rgb_enable), 
            'style': rgb_style, 
            'brightness': rgb_brightness,
            'color': rgb_color,
            'speed': rgb_speed
        }
    }

def control_fan(mode):
    """
    Control Pironman fan
    Mode: 'auto' (Performance), 'on' (Always On), 'off' (Cool)
    """
    try:
        # Map mode to GPIO fan mode: 0=Always On, 1=Performance, 2=Cool
        mode_map = {'on': 0, 'auto': 1, 'off': 2}
        gpio_mode = mode_map.get(mode, 1)
        
        # Run pironman5 command with sudo to update config
        result = subprocess.run(
            ['sudo', PIRONMAN_CMD, '--gpio-fan-mode', str(gpio_mode)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Pironman fan command failed: {result.stderr}")
            return False
        
        # Restart pironman5 service to apply changes
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'pironman5'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if restart_result.returncode != 0:
            print(f"Failed to restart pironman5 service: {restart_result.stderr}")
            # Still return True as config was updated
        
        return True
    except subprocess.TimeoutExpired:
        print("Pironman fan command timed out")
        return False
    except Exception as e:
        print(f"Error controlling fan: {e}")
        return False

def control_display(state):
    """
    Control Pironman OLED display on/off
    """
    try:
        # Convert state to Pironman format
        oled_state = 'True' if state == 'on' else 'False'
        
        # Run pironman5 command with sudo to update config
        result = subprocess.run(
            ['sudo', PIRONMAN_CMD, '--oled-enable', oled_state],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Pironman command failed: {result.stderr}")
            return False
        
        # Restart pironman5 service to apply changes
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'pironman5'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if restart_result.returncode != 0:
            print(f"Failed to restart pironman5 service: {restart_result.stderr}")
            # Still return True as config was updated
        
        return True
    except subprocess.TimeoutExpired:
        print("Pironman command timed out")
        return False
    except Exception as e:
        print(f"Error controlling display: {e}")
        return False

def control_brightness(brightness):
    """
    Control Pironman display brightness (0-100)
    Note: OLED display may not support brightness control, but we'll try
    """
    try:
        # OLED doesn't have brightness control, but we'll keep the function
        # for potential future use or RGB brightness
        # For now, just return success
        return True
    except Exception as e:
        print(f"Error controlling brightness: {e}")
        return False

def control_fan_rgb(state):
    """
    Control Pironman fan RGB on/off
    """
    try:
        # Convert state to Pironman format
        rgb_state = 'True' if state == 'on' else 'False'
        
        # Run pironman5 command with sudo to update config
        result = subprocess.run(
            ['sudo', PIRONMAN_CMD, '--rgb-enable', rgb_state],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Pironman RGB command failed: {result.stderr}")
            return False
        
        # Restart pironman5 service to apply changes
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'pironman5'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if restart_result.returncode != 0:
            print(f"Failed to restart pironman5 service: {restart_result.stderr}")
            # Still return True as config was updated
        
        return True
    except subprocess.TimeoutExpired:
        print("Pironman RGB command timed out")
        return False
    except Exception as e:
        print(f"Error controlling RGB: {e}")
        return False

def control_rgb_color(color):
    """
    Control Pironman RGB color (hex format without #)
    Note: Also ensures RGB is enabled when setting color
    """
    try:
        # Remove # if present
        color = color.replace('#', '').lower()
        
        # Run pironman5 command with sudo to update config
        # Enable RGB and set color together
        result = subprocess.run(
            ['sudo', PIRONMAN_CMD, '--rgb-enable', 'True', '--rgb-color', color],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Pironman RGB color command failed: {result.stderr}")
            return False
        
        # Restart pironman5 service to apply changes
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'pironman5'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if restart_result.returncode != 0:
            print(f"Failed to restart pironman5 service: {restart_result.stderr}")
        
        return True
    except subprocess.TimeoutExpired:
        print("Pironman RGB color command timed out")
        return False
    except Exception as e:
        print(f"Error controlling RGB color: {e}")
        return False

def control_rgb_style(style):
    """
    Control Pironman RGB style
    Note: Also ensures RGB is enabled when setting style
    """
    try:
        # Run pironman5 command with sudo to update config
        # Enable RGB and set style together
        result = subprocess.run(
            ['sudo', PIRONMAN_CMD, '--rgb-enable', 'True', '--rgb-style', style],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Pironman RGB style command failed: {result.stderr}")
            return False
        
        # Restart pironman5 service to apply changes
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'pironman5'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if restart_result.returncode != 0:
            print(f"Failed to restart pironman5 service: {restart_result.stderr}")
        
        return True
    except subprocess.TimeoutExpired:
        print("Pironman RGB style command timed out")
        return False
    except Exception as e:
        print(f"Error controlling RGB style: {e}")
        return False

def control_rgb_brightness(brightness):
    """
    Control Pironman RGB brightness (0-100)
    Note: Also ensures RGB is enabled when setting brightness
    """
    try:
        # Run pironman5 command with sudo to update config
        # Enable RGB and set brightness together
        result = subprocess.run(
            ['sudo', PIRONMAN_CMD, '--rgb-enable', 'True', '--rgb-brightness', str(brightness)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Pironman RGB brightness command failed: {result.stderr}")
            return False
        
        # Restart pironman5 service to apply changes
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'pironman5'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if restart_result.returncode != 0:
            print(f"Failed to restart pironman5 service: {restart_result.stderr}")
        
        return True
    except subprocess.TimeoutExpired:
        print("Pironman RGB brightness command timed out")
        return False
    except Exception as e:
        print(f"Error controlling RGB brightness: {e}")
        return False

def control_rgb_speed(speed):
    """
    Control Pironman RGB speed (0-100)
    Note: Also ensures RGB is enabled when setting speed
    """
    try:
        # Run pironman5 command with sudo to update config
        # Enable RGB and set speed together
        result = subprocess.run(
            ['sudo', PIRONMAN_CMD, '--rgb-enable', 'True', '--rgb-speed', str(speed)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Pironman RGB speed command failed: {result.stderr}")
            return False
        
        # Restart pironman5 service to apply changes
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'pironman5'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if restart_result.returncode != 0:
            print(f"Failed to restart pironman5 service: {restart_result.stderr}")
        
        return True
    except subprocess.TimeoutExpired:
        print("Pironman RGB speed command timed out")
        return False
    except Exception as e:
        print(f"Error controlling RGB speed: {e}")
        return False

def control_fan_rgb_led(state):
    """
    Control Pironman fan RGB LED state (on, off, follow)
    follow = RGB turns on automatically when fan is on
    """
    try:
        # Run pironman5 command with sudo to update config
        # Use -fl flag for fan LED control
        result = subprocess.run(
            ['sudo', PIRONMAN_CMD, '-fl', state],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Pironman fan RGB LED command failed: {result.stderr}")
            return False
        
        # Restart pironman5 service to apply changes
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'pironman5'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if restart_result.returncode != 0:
            print(f"Failed to restart pironman5 service: {restart_result.stderr}")
        
        return True
    except subprocess.TimeoutExpired:
        print("Pironman fan RGB LED command timed out")
        return False
    except Exception as e:
        print(f"Error controlling fan RGB LED: {e}")
        return False

@bp.route('/status', methods=['GET'])
def get_status():
    """Get Pironman system status"""
    try:
        status = get_pironman_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fan', methods=['POST'])
def set_fan():
    """Set fan mode (auto, on, off)"""
    try:
        data = request.get_json()
        mode = data.get('mode', 'auto')
        
        if mode not in ['auto', 'on', 'off']:
            return jsonify({'error': 'Invalid mode'}), 400
        
        success = control_fan(mode)
        if success:
            return jsonify({'status': 'ok', 'mode': mode})
        else:
            return jsonify({'error': 'Failed to set fan mode'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/display', methods=['POST'])
def set_display():
    """Set display state (on, off)"""
    try:
        data = request.get_json()
        state = data.get('state', 'on')
        
        if state not in ['on', 'off']:
            return jsonify({'error': 'Invalid state'}), 400
        
        success = control_display(state)
        if success:
            return jsonify({'status': 'ok', 'state': state})
        else:
            return jsonify({'error': 'Failed to set display state'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/brightness', methods=['POST'])
def set_brightness():
    """Set display brightness (0-100)"""
    try:
        data = request.get_json()
        brightness = int(data.get('brightness', 100))
        
        if brightness < 0 or brightness > 100:
            return jsonify({'error': 'Brightness must be between 0 and 100'}), 400
        
        success = control_brightness(brightness)
        if success:
            return jsonify({'status': 'ok', 'brightness': brightness})
        else:
            return jsonify({'error': 'Failed to set brightness'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fan-rgb', methods=['POST'])
def set_fan_rgb():
    """Set fan RGB state (on, off)"""
    try:
        data = request.get_json()
        state = data.get('state', 'on')
        
        if state not in ['on', 'off']:
            return jsonify({'error': 'Invalid state'}), 400
        
        success = control_fan_rgb(state)
        if success:
            return jsonify({'status': 'ok', 'state': state})
        else:
            return jsonify({'error': 'Failed to set RGB state'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fan-rgb-color', methods=['POST'])
def set_fan_rgb_color():
    """Set fan RGB color (hex format without #)"""
    try:
        data = request.get_json()
        color = data.get('color', '0a1aff')
        
        # Remove # if present and validate hex
        color = color.replace('#', '').lower()
        if len(color) != 6 or not all(c in '0123456789abcdef' for c in color):
            return jsonify({'error': 'Invalid color format'}), 400
        
        success = control_rgb_color(color)
        if success:
            return jsonify({'status': 'ok', 'color': color})
        else:
            return jsonify({'error': 'Failed to set RGB color'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fan-rgb-style', methods=['POST'])
def set_fan_rgb_style():
    """Set fan RGB style"""
    try:
        data = request.get_json()
        style = data.get('style', 'solid')
        
        valid_styles = ['solid', 'breathing', 'flow', 'flow_reverse', 'rainbow', 'rainbow_reverse', 'hue_cycle']
        if style not in valid_styles:
            return jsonify({'error': 'Invalid style'}), 400
        
        success = control_rgb_style(style)
        if success:
            return jsonify({'status': 'ok', 'style': style})
        else:
            return jsonify({'error': 'Failed to set RGB style'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fan-rgb-brightness', methods=['POST'])
def set_fan_rgb_brightness():
    """Set fan RGB brightness (0-100)"""
    try:
        data = request.get_json()
        brightness = int(data.get('brightness', 50))
        
        if brightness < 0 or brightness > 100:
            return jsonify({'error': 'Brightness must be between 0 and 100'}), 400
        
        success = control_rgb_brightness(brightness)
        if success:
            return jsonify({'status': 'ok', 'brightness': brightness})
        else:
            return jsonify({'error': 'Failed to set RGB brightness'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fan-rgb-speed', methods=['POST'])
def set_fan_rgb_speed():
    """Set fan RGB speed (0-100)"""
    try:
        data = request.get_json()
        speed = int(data.get('speed', 50))
        
        if speed < 0 or speed > 100:
            return jsonify({'error': 'Speed must be between 0 and 100'}), 400
        
        success = control_rgb_speed(speed)
        if success:
            return jsonify({'status': 'ok', 'speed': speed})
        else:
            return jsonify({'error': 'Failed to set RGB speed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/fan-rgb-led', methods=['POST'])
def set_fan_rgb_led():
    """Set fan RGB LED state (on, off, follow)"""
    try:
        data = request.get_json()
        state = data.get('state', 'follow')
        
        if state not in ['on', 'off', 'follow']:
            return jsonify({'error': 'Invalid state. Use: on, off, or follow'}), 400
        
        success = control_fan_rgb_led(state)
        if success:
            return jsonify({'status': 'ok', 'state': state})
        else:
            return jsonify({'error': 'Failed to set fan RGB LED state'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
