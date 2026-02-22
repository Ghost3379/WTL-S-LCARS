
import psutil
import subprocess
import socket
import sys

def check_wifi():
    print("=== Network Interfaces (psutil) ===")
    interfaces = psutil.net_if_addrs()
    wlan_interface = None
    
    for interface_name, addresses in interfaces.items():
        print(f"Interface: {interface_name}")
        for addr in addresses:
            print(f"  - Family: {addr.family}, Address: {addr.address}")
            if addr.family == socket.AF_INET and ('wlan' in interface_name.lower() or 'wifi' in interface_name.lower()):
                print(f"  -> MATCHED as WiFi interface")
                wlan_interface = interface_name

    if not wlan_interface:
        print("\nWARNING: No interface matched 'wlan' or 'wifi'. Trying to find one anyway...")
        # Fallback: look for wireless extensions
        try:
            with open('/proc/net/wireless', 'r') as f:
                content = f.read()
                print("\n=== /proc/net/wireless ===")
                print(content)
        except Exception as e:
            print(f"Could not read /proc/net/wireless: {e}")

    search_interface = wlan_interface if wlan_interface else "wlan0" # Default guess
    print(f"\n=== Testing commands on {search_interface} ===")

    # Test iwconfig
    print("\n--- iwconfig ---")
    try:
        result = subprocess.run(['iwconfig', search_interface], capture_output=True, text=True)
        print("Return Code:", result.returncode)
        print("stdout:", result.stdout)
        print("stderr:", result.stderr)
    except FileNotFoundError:
        print("ERROR: iwconfig command not found")
    except Exception as e:
        print(f"ERROR running iwconfig: {e}")

    # Test iwgetid
    print("\n--- iwgetid ---")
    try:
        result = subprocess.run(['iwgetid', '-r', search_interface], capture_output=True, text=True)
        print("Return Code:", result.returncode)
        print("stdout:", result.stdout)
        print("stderr:", result.stderr)
    except FileNotFoundError:
        print("ERROR: iwgetid command not found")
    except Exception as e:
        print(f"ERROR running iwgetid: {e}")

    # Test nmcli (NetworkManager) - common modern alternative
    print("\n--- nmcli ---")
    try:
        result = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL', 'dev', 'wifi'], capture_output=True, text=True)
        print("Return Code:", result.returncode)
        print("stdout:\n", result.stdout)
    except FileNotFoundError:
        print("ERROR: nmcli command not found")
    except Exception as e:
        print(f"ERROR running nmcli: {e}")

if __name__ == "__main__":
    check_wifi()
