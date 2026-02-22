
import sys
import os

# Add backend directory to path so we can import the module
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from api.system import get_network_info
    
    print("=== Testing get_network_info() ===")
    info = get_network_info()
    print("Result:")
    print(f"  Interface: {info.get('interface')}")
    print(f"  Connected: {info.get('connected')}")
    print(f"  SSID:      {info.get('ssid')}")
    print(f"  IP:        {info.get('ip')}")
    print(f"  RSSI:      {info.get('rssi')} dBm")
    
except ImportError as e:
    print(f"Error importing module: {e}")
except Exception as e:
    print(f"Error running test: {e}")
