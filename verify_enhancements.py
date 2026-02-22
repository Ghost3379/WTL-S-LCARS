import requests
import json

BASE_URL = "http://localhost:5000/api"

def test_settings():
    print("Testing settings persistence...")
    # Get initial settings
    try:
        r = requests.get(f"{BASE_URL}/system/settings")
        print(f"Initial settings: {r.json()}")
        
        # Update settings
        new_settings = {
            "volume": 75,
            "standbyTimeout": 10,
            "standbyConfig": {"display": "on", "lights": "off", "fan": "auto", "minecraft": "keep"}
        }
        r = requests.post(f"{BASE_URL}/system/settings", json=new_settings)
        print(f"Save status: {r.json()}")
        
        # Verify
        r = requests.get(f"{BASE_URL}/system/settings")
        saved = r.json()
        if saved.get('volume') == 75:
            print("Settings persistence TEST PASSED")
        else:
            print(f"Settings persistence TEST FAILED: expected 75, got {saved.get('volume')}")
    except Exception as e:
        print(f"Error testing settings: {e}")

def test_network_scan():
    print("\nTesting network scan...")
    try:
        r = requests.get(f"{BASE_URL}/network/scan")
        data = r.json()
        print(f"Local IP: {data.get('local_ip')}")
        print(f"Devices found: {len(data.get('devices', []))}")
        for dev in data.get('devices', [])[:3]:
            print(f" - {dev.get('ip')} ({dev.get('hostname')})")
        print("Network scan TEST PASSED (if devices list is returned)")
    except Exception as e:
        print(f"Error testing network: {e}")

if __name__ == "__main__":
    test_settings()
    test_network_scan()
