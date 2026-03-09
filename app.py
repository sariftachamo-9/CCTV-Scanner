from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import threading
import json
import nmap
import netifaces
import socket
import requests
from datetime import datetime
import os
import subprocess
import platform
import re
import atexit
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from scanner import NetworkCameraScanner

app = Flask(__name__)

# Cloudflare Process Reference
cloudflared_process = None

def cleanup_cloudflared():
    global cloudflared_process
    if cloudflared_process:
        try:
            cloudflared_process.terminate()
        except:
            pass

atexit.register(cleanup_cloudflared)

def start_cloudflare_tunnel():
    """Launch Cloudflare tunnel in background and extract URL"""
    global cloudflared_process
    def run_cf():
        global cloudflared_process
        try:
            # Stderr has the output we need
            cloudflared_process = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", "http://127.0.0.1:5001"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0,
                bufsize=1
            )
            print("\n[!] Initializing Cloudflare Request...")
            url_printed = False
            for line in cloudflared_process.stdout:
                if not url_printed and "trycloudflare.com" in line:
                    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        print("\n" + "="*50)
                        print("  🌐 SECURE REMOTE ACCESS URL")
                        print("  " + match.group(0))
                        print("="*50 + "\n")
                        url_printed = True
        except FileNotFoundError:
            print("\n[!] 'cloudflared' not found in system PATH. Remote access disabled.")
        except Exception as e:
            pass

    threading.Thread(target=run_cf, daemon=True).start()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-change-me')
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active scans
active_scans = {}

# Nmap path - loaded from .env
NMAP_PATH = os.getenv('NMAP_PATH', r"C:\Program Files (x86)\Nmap")

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/network-info')
def network_info():
    """Get current network information"""
    try:
        from scanner.utils import get_local_ip, is_admin
        scanner = NetworkCameraScanner(nmap_path=NMAP_PATH)
        network = scanner.get_local_network()
        
        # Get local IP using the robust method
        local_ip = get_local_ip()
        hostname = socket.gethostname()
        admin_status = is_admin()
        nmap_installed = scanner.nm is not None
        
        # Cloudflare Tunnel detection
        cf_ray = request.headers.get('Cf-Ray')
        is_cloudflared = cf_ray is not None
        
        return jsonify({
            'success': True,
            'network': network,
            'local_ip': local_ip,
            'hostname': hostname,
            'is_admin': admin_status,
            'nmap_installed': nmap_installed,
            'is_cloudflared': is_cloudflared
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@socketio.on('start_scan')
def handle_scan(data):
    """Start network camera scan"""
    scan_id = data.get('scan_id', datetime.now().strftime('%Y%m%d%H%M%S'))
    network = data.get('network')
    
    if not network:
        emit('scan_error', {'scan_id': scan_id, 'error': 'No network range provided'})
        return

    # Store scan in active_scans
    active_scans[scan_id] = {
        'status': 'running',
        'results': [],
        'start_time': datetime.now()
    }
    
    # Perform scan in background
    def scan_thread():
        try:
            from scanner.utils import log_message
            scanner = NetworkCameraScanner(nmap_path=NMAP_PATH)
            
            if not scanner.nm:
                error_msg = "Nmap not found. Scanning disabled."
                log_message(error_msg, level='error')
                socketio.emit('scan_error', {'scan_id': scan_id, 'error': error_msg})
                active_scans[scan_id]['status'] = 'failed'
                return

            # Pass socketio to the scanner so it can emit progress and found cameras
            results = scanner.perform_scan(network, scan_id, socketio=socketio)
            
            active_scans[scan_id]['status'] = 'completed'
            active_scans[scan_id]['results'] = results
            
            socketio.emit('scan_complete', {
                'scan_id': scan_id,
                'results': results,
                'count': len(results)
            })
        except Exception as e:
            from scanner.utils import log_message
            log_message(f"Background scan error: {e}", level='error')
            socketio.emit('scan_error', {'scan_id': scan_id, 'error': str(e)})
            active_scans[scan_id]['status'] = 'failed'
    
    thread = threading.Thread(target=scan_thread)
    thread.daemon = True
    thread.start()
    
    emit('scan_started', {'scan_id': scan_id, 'network': network, 'scan_type': 'network'})

@socketio.on('start_traffic_scan')
def handle_traffic_scan(data):
    """Start traffic light infrastructure scan"""
    scan_id = data.get('scan_id', datetime.now().strftime('%Y%m%d%H%M%S'))
    network = data.get('network')
    
    if not network:
        emit('scan_error', {'scan_id': scan_id, 'error': 'No target range provided'})
        return

    active_scans[scan_id] = {
        'status': 'running',
        'results': [],
        'start_time': datetime.now()
    }
    
    def traffic_scan_thread():
        try:
            from scanner.utils import log_message
            scanner = NetworkCameraScanner(nmap_path=NMAP_PATH)
            
            if not scanner.nm:
                error_msg = "Nmap not found. Scanning disabled."
                socketio.emit('scan_error', {'scan_id': scan_id, 'error': error_msg, 'scan_type': 'traffic'})
                return

            results = scanner.perform_traffic_scan(network, scan_id, socketio=socketio)
            
            active_scans[scan_id]['status'] = 'completed'
            active_scans[scan_id]['results'] = results
            
            socketio.emit('scan_complete', {
                'scan_id': scan_id,
                'scan_type': 'traffic',
                'results': results,
                'count': len(results)
            })
        except Exception as e:
            from scanner.utils import log_message
            log_message(f"Traffic scan thread error: {e}", level='error')
            socketio.emit('scan_error', {'scan_id': scan_id, 'error': str(e), 'scan_type': 'traffic'})
            active_scans[scan_id]['status'] = 'failed'
    
    thread = threading.Thread(target=traffic_scan_thread)
    thread.daemon = True
    thread.start()
    
    emit('scan_started', {'scan_id': scan_id, 'network': network, 'scan_type': 'traffic'})

@socketio.on('get_scan_status')
def handle_status(data):
    """Get scan status"""
    scan_id = data.get('scan_id')
    if scan_id in active_scans:
        emit('scan_status', active_scans[scan_id])
    else:
        emit('scan_status', {'status': 'not_found'})

@app.route('/api/sensor-scan', methods=['POST'])
def sensor_scan():
    """Handle sensor-based detection from mobile"""
    data = request.json
    sensor_data = data.get('sensorData', {})
    
    # Process sensor data
    threats = []
    
    # Check magnetometer for EM fields
    if 'magnetometer' in sensor_data:
        mag = sensor_data['magnetometer']
        if mag.get('strength', 0) > 50:  # Threshold
            threats.append({
                'type': 'magnetic_field',
                'strength': mag['strength'],
                'location': 'nearby electronic device',
                'confidence': min(mag['strength'], 100)
            })
    
    # Check camera for IR
    if 'ir_detection' in sensor_data:
        ir = sensor_data['ir_detection']
        if ir.get('ir_detected', False):
            threats.append({
                'type': 'infrared',
                'strength': ir.get('intensity', 0),
                'location': 'camera lens detected',
                'confidence': 85
            })
    
    return jsonify({
        'success': True,
        'threats': threats,
        'count': len(threats)
    })

@app.route('/api/export-results/<scan_id>')
def export_results(scan_id):
    """Export scan results as JSON"""
    if scan_id in active_scans:
        return jsonify(active_scans[scan_id])
    return jsonify({'error': 'Scan not found'}), 404

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the Flask server"""
    try:
        from scanner.utils import log_message
        log_message("Shutdown requested by user. Terminating server...", level='warning')
        
        # Give time for the response to reach the client
        def stop_server():
            import time
            time.sleep(1)
            import os
            import signal
            os.kill(os.getpid(), signal.SIGINT)
            
        import threading
        threading.Thread(target=stop_server).start()
        return jsonify({'message': 'Server shutting down...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("*" * 50)
    print("  CCTV CAMERA DETECTION SYSTEM")
    print("  Starting server on http://localhost:5001")
    print("  Please keep this window open while using the app.")
    print("*" * 50)
    
    # Launch Cloudflare tunnel automatically
    start_cloudflare_tunnel()
    
    socketio.run(app, debug=False, host='0.0.0.0', port=5001)
