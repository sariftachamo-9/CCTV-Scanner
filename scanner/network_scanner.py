"""Network scanner module for detecting cameras and devices"""

import socket
import ipaddress
import nmap
import netifaces
import requests
import subprocess
import platform
import os
from .utils import log_message, get_local_ip

class NetworkCameraScanner:
    def __init__(self, nmap_path=None):
        if nmap_path:
            # Add nmap to PATH if provided
            os.environ["PATH"] += os.pathsep + nmap_path
            
        try:
            self.nm = nmap.PortScanner()
        except nmap.PortScannerError:
            log_message("Nmap not found in PATH. Make sure it's installed correctly.", level='error')
            self.nm = None
        except Exception as e:
            log_message(f"Error initializing Nmap: {e}", level='error')
            self.nm = None
            
        self.results = []
        
    def get_local_network(self):
        """Get local network range"""
        try:
            # Try to get the IP used for external traffic
            local_ip = get_local_ip()
            log_message(f"Detected local IP: {local_ip}")
            
            if local_ip == '127.0.0.1':
                # Fallback to netifaces if possible
                try:
                    gateways = netifaces.gateways()
                    if 'default' in gateways and netifaces.AF_INET in gateways['default']:
                        default_interface = gateways['default'][netifaces.AF_INET][1]
                        addrs = netifaces.ifaddresses(default_interface)
                        if netifaces.AF_INET in addrs:
                            local_ip = addrs[netifaces.AF_INET][0]['addr']
                            log_message(f"Retrieved IP from default gateway interface: {local_ip}")
                except Exception as e:
                    log_message(f"Netifaces fallback failed: {e}", level='debug')
            
            if local_ip == '127.0.0.1':
                # Last resort: try any non-loopback interface
                for iface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        addr = addrs[netifaces.AF_INET][0]['addr']
                        if not addr.startswith('127.'):
                            local_ip = addr
                            log_message(f"Using IP from interface {iface}: {local_ip}")
                            break

            if local_ip == '127.0.0.1':
                log_message("Could not detect local network, falling back to 192.168.1.0/24", level='warning')
                return "192.168.1.0/24" 

            parts = local_ip.split('.')
            # Common home networks often use /24
            # We could try to get the actual netmask from netifaces
            try:
                gateways = netifaces.gateways()
                if 'default' in gateways and netifaces.AF_INET in gateways['default']:
                    default_interface = gateways['default'][netifaces.AF_INET][1]
                    addrs = netifaces.ifaddresses(default_interface)
                    if netifaces.AF_INET in addrs:
                        netmask = addrs[netifaces.AF_INET][0].get('netmask')
                        if netmask:
                            # Simple CIDR conversion (not perfect but covers common cases)
                            if netmask == '255.255.255.0': cidr = 24
                            elif netmask == '255.255.0.0': cidr = 16
                            elif netmask == '255.0.0.0': cidr = 8
                            else: cidr = 24
                            
                            # Calculate network address
                            interface = ipaddress.IPv4Interface(f"{local_ip}/{netmask}")
                            return str(interface.network)
            except Exception as e:
                log_message(f"Error calculating precise network: {e}", level='debug')
            
            # Simple fallback /24
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            
        except Exception as e:
            log_message(f"Error getting network: {e}", level='warning')
            return "192.168.1.0/24"  # Default fallback
    
    def scan_common_ports(self, ip):
        """Check if IP has open camera ports"""
        common_ports = [80, 443, 554, 8080, 8081, 8888, 37777, 37778]
        open_ports = []
        
        for port in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((ip, port))
                if result == 0:
                    # Check if it might be a camera
                    service = self.identify_service(ip, port)
                    open_ports.append({
                        'port': port,
                        'service': service
                    })
                sock.close()
            except:
                pass
        
        return open_ports
    
    def identify_service(self, ip, port):
        """Try to identify if service is a camera"""
        try:
            if port == 80 or port == 8080:
                # Try HTTP request
                response = requests.get(f"http://{ip}:{port}", timeout=1)
                if response.status_code == 200:
                    # Check for camera signatures in HTML
                    html = response.text.lower()
                    camera_keywords = ['camera', 'webcam', 'ipcam', 'dvr', 'nvr', 
                                     'onvif', 'rtsp', 'h264', 'mpeg']
                    for keyword in camera_keywords:
                        if keyword in html:
                            return f"Possible Camera (HTTP - {keyword})"
                    return "Web Server"
            elif port == 554:
                # RTSP port
                return "RTSP Stream (Likely Camera)"
            elif port == 37777:
                # Common for some IP cameras
                return "Dahua/Camera Port"
        except:
            pass
        
        return "Unknown"
    
    def perform_scan(self, network_range, scan_id, socketio=None):
        """Perform network scan for cameras"""
        results = []
        if not self.nm:
            log_message("Nmap scanner not initialized", level='error')
            return []

        try:
            log_message(f"Starting {scan_id} on {network_range}")
            # Ping scan to find live hosts
            self.nm.scan(hosts=network_range, arguments='-sn')
            live_hosts = self.nm.all_hosts()
            
            total = len(live_hosts)
            for idx, host in enumerate(live_hosts):
                # Emit progress if socketio is provided
                if socketio:
                    socketio.emit('scan_progress', {
                        'scan_id': scan_id,
                        'progress': int((idx + 1) / total * 100),
                        'current_host': host
                    })
                
                # Check for open camera ports
                open_ports = self.scan_common_ports(host)
                
                if open_ports:
                    # Try to get hostname
                    try:
                        hostname = socket.gethostbyaddr(host)[0]
                    except:
                        hostname = "Unknown"
                    
                    camera_info = {
                        'ip': host,
                        'hostname': hostname,
                        'ports': open_ports,
                        'mac': self.get_mac_address(host),
                        'confidence': self.calculate_confidence(open_ports)
                    }
                    results.append(camera_info)
                    
                    # Emit found camera if socketio is provided
                    if socketio:
                        socketio.emit('camera_found', {
                            'scan_id': scan_id,
                            'camera': camera_info
                        })
            
            return results
        except Exception as e:
            log_message(f"Scan error: {e}", level='error')
            return []
            
    def perform_traffic_scan(self, network_range, scan_id, socketio=None):
        """Perform scan for traffic lights and infrastructure"""
        results = []
        if not self.nm:
            log_message("Nmap scanner not initialized", level='error')
            return []

        # Specific ports for traffic systems and industrial controllers
        # 161 (SNMP), 502 (Modbus), 44818 (EtherNet/IP), 24800 (NTCIP)
        infrastructure_ports = '161,502,44818,24800,80,8080'

        try:
            log_message(f"Starting Traffic Scan {scan_id} on {network_range}")
            # Port scan for infrastructure
            self.nm.scan(hosts=network_range, arguments=f'-p {infrastructure_ports} -sV --version-intensity 3')
            
            scanned_hosts = self.nm.all_hosts()
            total = len(scanned_hosts)
            
            for idx, host in enumerate(scanned_hosts):
                if socketio:
                    socketio.emit('scan_progress', {
                        'scan_id': scan_id,
                        'scan_type': 'traffic',
                        'progress': int((idx + 1) / total * 100),
                        'current_host': host
                    })
                
                device_ports = []
                is_traffic_related = False
                device_type = "Unknown Infrastructure"
                
                if 'tcp' in self.nm[host]:
                    for port in self.nm[host]['tcp']:
                        if self.nm[host]['tcp'][port]['state'] == 'open':
                            service = self.nm[host]['tcp'][port].get('name', 'Unknown')
                            product = self.nm[host]['tcp'][port].get('product', '').lower()
                            
                            # Detection logic
                            if port == 502 or 'modbus' in product:
                                is_traffic_related = True
                                device_type = "Industrial Controller (Modbus)"
                            elif port == 161 or 'snmp' in product:
                                is_traffic_related = True
                                device_type = "SNMP Infrastructure (NTCIP Capable)"
                            elif 'traffic' in product or 'ntcip' in product:
                                is_traffic_related = True
                                device_type = "Traffic Management System"
                                
                            device_ports.append({
                                'port': port,
                                'service': f"{service} ({product})" if product else service
                            })
                
                if is_traffic_related:
                    device_info = {
                        'ip': host,
                        'hostname': self.nm[host].hostname() or "Unknown",
                        'ports': device_ports,
                        'type': device_type
                    }
                    results.append(device_info)
                    if socketio:
                        socketio.emit('traffic_found', {
                            'scan_id': scan_id,
                            'device': device_info
                        })
            
            return results
        except Exception as e:
            log_message(f"Traffic scan error: {e}", level='error')
            return []
    
    def get_mac_address(self, ip):
        """Get MAC address for IP"""
        try:
            if platform.system().lower() == "windows":
                # Windows command
                result = subprocess.check_output(f"arp -a {ip}", shell=True).decode()
                lines = result.split('\n')
                for line in lines:
                    if ip in line:
                        parts = line.split()
                        for part in parts:
                            if '-' in part or ':' in part:
                                return part
            else:
                # Linux/Mac command
                result = subprocess.check_output(f"arp -n {ip}", shell=True).decode()
                lines = result.split('\n')
                for line in lines:
                    if ip in line:
                        parts = line.split()
                        for part in parts:
                            if ':' in part:
                                return part
        except:
            pass
        return "Unknown"
    
    def calculate_confidence(self, ports):
        """Calculate confidence score that this is a camera"""
        score = 0
        for port in ports:
            if port['port'] == 554:  # RTSP
                score += 40
            elif port['port'] == 80 and 'camera' in port.get('service', '').lower():
                score += 30
            elif port['port'] in [37777, 37778]:  # Common camera ports
                score += 30
            elif port['port'] in [8080, 8081]:
                score += 10
        
        return min(score, 100)

# Legacy functional interface (for backward compatibility if needed)
def scan_network_legacy(target='192.168.1.0/24', ports=None):
    scanner = NetworkCameraScanner()
    results = scanner.perform_scan(target, "legacy_scan")
    return {
        'devices': results,
        'total_scanned': len(results), # This is not accurate but fine for legacy
        'total_found': len(results)
    }
