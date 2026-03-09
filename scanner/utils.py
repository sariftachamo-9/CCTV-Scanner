import logging
import socket
import ctypes
import os
import platform
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_message(message, level='info'):
    """
    Log a message with timestamp
    
    Args:
        message (str): Message to log
        level (str): Log level (info, warning, error, debug)
    """
    logger = logging.getLogger(__name__)
    
    if level == 'error':
        logger.error(message)
    elif level == 'warning':
        logger.warning(message)
    elif level == 'debug':
        logger.debug(message)
    else:
        logger.info(message)

def is_admin():
    """
    Check if the process is running with administrator privileges
    
    Returns:
        bool: True if admin, False otherwise
    """
    try:
        if platform.system().lower() == "windows":
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.getuid() == 0
    except AttributeError:
        return False
    except Exception:
        return False

def format_results(data):
    """
    Format scan results for display
    
    Args:
        data (dict): Raw scan results
    
    Returns:
        dict: Formatted results
    """
    return {
        'timestamp': datetime.now().isoformat(),
        'total_devices': len(data.get('devices', [])),
        'devices': data.get('devices', [])
    }

def validate_ip(ip_address):
    """
    Validate IP address format
    
    Args:
        ip_address (str): IP address to validate
    
    Returns:
        bool: True if valid, False otherwise
    """
    parts = ip_address.split('.')
    if len(parts) != 4:
        return False
    
    try:
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False
        return True
    except ValueError:
        return False

def get_local_ip():
    """
    Get local machine IP address
    
    Returns:
        str: Local IP address
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        # Fallback to hostname-based IP
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return '127.0.0.1'
