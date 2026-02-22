"""
Network Scanning API endpoints
"""

from flask import Blueprint, jsonify, request
import subprocess
import socket
import os
import re

bp = Blueprint('network', __name__)

def get_local_ip():
    """Get local IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
        s.close()
        return IP
    except Exception:
        return '127.0.0.1'

@bp.route('/scan', methods=['GET'])
def scan_network():
    """Scan local network for devices"""
    try:
        local_ip = get_local_ip()
        ip_prefix = '.'.join(local_ip.split('.')[:-1]) + '.'
        subnet = ip_prefix + '0/24'
        
        devices = []
        found_ips = set()
        
        # 1. Active Ping Sweep using nmap
        # This forces all devices to wake up and respond, populating the ARP table.
        try:
            # -sn: Ping Scan - disable port scan
            # -T4: Faster execution
            subprocess.run(['nmap', '-sn', '-T4', subnet], capture_output=True, text=True, timeout=30)
        except Exception as e:
            print(f"nmap sweep failed or timed out: {e}")

        # 2. Use 'ip neigh' to get the now-populated local ARP table
        try:
            result = subprocess.run(['ip', 'neigh', 'show'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    # 172.19.19.1 dev wlan0 lladdr 00:11:22:33:44:55 REACHABLE
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+dev\s+\S+\s+lladdr\s+(\S+)\s+(\S+)', line)
                    if match:
                        ip = match.group(1)
                        mac = match.group(2)
                        status = match.group(3)
                        
                        # Only add if we haven't seen this IP yet
                        if ip not in found_ips:
                            found_ips.add(ip)
                            
                            # Try to get hostname
                            hostname = "Unknown"
                            try:
                                host_result = subprocess.run(['getent', 'hosts', ip], capture_output=True, text=True, timeout=1)
                                if host_result.returncode == 0 and host_result.stdout:
                                    hostname = host_result.stdout.split()[1]
                            except:
                                pass
                                
                            devices.append({
                                'ip': ip,
                                'mac': mac,
                                'hostname': hostname,
                                'status': status,
                                'is_self': ip == local_ip
                            })
        except Exception as e:
            print(f"Error in ip neigh: {e}")

        # Ensure local device is always in the list
        if local_ip not in found_ips:
            hostname = socket.gethostname()
            # Try to get local MAC (can be complex, defaulting for simplicity)
            devices.append({
                'ip': local_ip,
                'mac': 'Local Device',
                'hostname': hostname,
                'status': 'REACHABLE',
                'is_self': True
            })
        
        # Sort so self is first, then by IP
        devices.sort(key=lambda x: (not x['is_self'], socket.inet_aton(x['ip'])))

        return jsonify({
            'local_ip': local_ip,
            'devices': devices
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
