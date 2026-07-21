# CCTV & Infra Scanner Pro

An advanced, real-time security scanning tool designed for the identification, analysis, and mapping of IP cameras, CCTV systems, and industrial infrastructure (such as traffic controllers and industrial IoT systems) on a network. The application also supports mobile-responsive hardware sensor scans (magnetometer and IR detection inputs) to scan for localized physical hidden cameras.

---

## Table of Contents 
1. [Description](#description)
2. [Features](#features)
3. [Tech Stack](#tech-stack)
4. [Project Architecture](#project-architecture)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Usage](#usage)
8. [Folder Structure](#folder-structure)
9. [Security Features](#security-features)
10. [Testing](#testing)
11. [Future Improvements](#future-improvements)

---

## Description
**CCTV & Infra Scanner Pro** is an ethical hacking and security utility developed to scan and assess network-attached surveillance systems. It features a modern, clean web dashboard that allows users to initiate live scans, monitor progress, inspect open ports/services, and export detailed discovery logs. It leverages the speed and detail of `Nmap` for deep port probing, combined with custom signature-matching logic to categorize devices with a calculated "camera confidence" score.

---

## Features
- **Network Camera Discovery**: Perform active ping scans on subnets to detect live hosts and run targeted port scans on common surveillance ports:
  - `80`, `443` (HTTP/HTTPS web portals)
  - `554` (RTSP video streaming)
  - `8080`, `8081`, `8888` (Alternative HTTP web management)
  - `37777`, `37778` (Dahua and other major manufacturer control ports)
- **Dynamic Service Fingerprinting**: Analyzes response payloads, HTTP page content keywords (e.g., *camera, web-cam, DVR, NVR, ONVIF, RTSP, H264, MPEG*), and port numbers to verify camera presence and calculate confidence levels.
- **Infrastructure Scanner**: A specialized scanner targeting critical industrial and municipal network devices (e.g., traffic light control systems, PLCs, industrial controllers) by scanning ports like:
  - `161` (SNMP / NTCIP)
  - `502` (Modbus Protocol)
  - `44818` (EtherNet/IP)
  - `24800` (NTCIP Traffic Control)
- **Local Hardware Sensor Scan**: Integrated tab for mobile devices allowing manual calibration of magnetic/infrared fields to pinpoint nearby physical lenses or hidden spy cameras.
- **Real-Time WebSocket Updates**: Full real-time feedback using WebSockets (Socket.IO) to display active progress, current target IPs, and immediately output discovered cameras on the map without page refreshes.
- **Secure Remote Tunneling**: Built-in integration with Cloudflare Tunnels (`cloudflared`) to expose the local dashboard securely over the internet for remote mobile control without router port-forwarding.
- **Data Exporting**: Export all session logs and details directly to standard JSON documents.
- **Theme Customizer**: Clean light/dark mode switch.

---

## Tech Stack
* **Frontend**: HTML5, CSS3 (CSS Variables for theme customization), JavaScript (ES6 Vanilla), Socket.io Client
* **Backend**: Python 3.8+, Flask, Flask-SocketIO
* **Network & Scanning Core**: Nmap (C-based utility), Python-NMap
* **Helper Libraries**: Netifaces-Plus (network interface enumeration), Requests (HTTP header/signature scraping)
* **Remote Access**: Cloudflared (tunnel daemon)

---

## Project Architecture
The application runs as a lightweight client-server architecture:

```
                  ┌───────────────────────────────────────────────┐
                  │                 Web Browser                   │
                  │  (Tabbed UI: Network, Traffic, Sensors, Logs) │
                  └───────────────────────┬───────────────────────┘
                                          │  WebSocket / REST
                                          ▼
                  ┌───────────────────────────────────────────────┐
                  │              Flask Web Server                 │
                  │       (app.py / SocketIO / Threading)         │
                  └──────────────┬─────────────────┬──────────────┘
                                 │                 │
                 Imports/Calls   │                 │ Launches
                                 ▼                 ▼
          ┌─────────────────────────────┐   ┌─────────────────────────────┐
          │     scanner package         │   │      cloudflared tunnel     │
          │  (network_scanner.py /      │   │  (Exposes backend           │
          │   utils.py)                 │   │   to external devices)      │
          └──────────────┬──────────────┘   └─────────────────────────────┘
                         │
                         ▼ (Launches subprocess)
          ┌─────────────────────────────┐
          │            Nmap             │
          │     (Binary on System)      │
          └─────────────────────────────┘
```

1. **Client Interface**: Interactive single-page dashboard. Sends actions (`start_scan`, `start_traffic_scan`) and listens for WebSocket broadcasts (`scan_progress`, `camera_found`, `scan_complete`).
2. **Asynchronous Threading**: Scan requests spin up a background thread in Flask to avoid blocking the web application main loop.
3. **Scanning Engine**: Custom python code wrapping the `nmap` scanner binary, feeding real-time updates back to the WebSocket thread.

---

## Installation

### 1. System Dependencies (Nmap)
You must install Nmap on your system and ensure it is in your system's PATH.

* **Windows**:
  - Download the Windows installer from [Nmap Official Page](https://nmap.org/download.html).
  - Run the setup wizard and check the option **"Add Nmap to system PATH"**.
  - Restart your computer/terminal.
  *Alternatively, via Chocolatey:*
  ```powershell
  choco install nmap -y
  ```
  *Or via winget:*
  ```powershell
  winget install Insecure.Nmap
  ```
* **Linux (Debian/Ubuntu)**:
  ```bash
  sudo apt update && sudo apt install nmap -y
  ```

### 2. Python Dependencies
Install the required Python libraries.
```bash
pip install -r requirements.txt
```

### 3. Remote Tunneling (Optional)
If you want to use the Remote Access features, install [Cloudflared](https://github.com/cloudflare/cloudflared/releases) and ensure `cloudflared` is added to your environment variables.

---

## Configuration
The project is configured using environment variables. 
1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configure the following variables inside `.env`:
   - `SECRET_KEY`: A secure random key for Flask session security.
   - `NMAP_PATH`: Specify the absolute folder path where the `nmap` executable is installed (e.g., `C:\Program Files (x86)\Nmap`).

---

## Usage

### Starting the Application (Windows Batch Script)
Run the control batch script as an administrator:
1. Right-click `CCTV_Scanner.bat` and select **Run as Administrator**.
2. Select your Access Option:
   - `1` for Local Access Only (`http://localhost:5001`).
   - `2` for Remote Access (automatically initializes Cloudflare tunnel and copies remote URL).
3. The dashboard will automatically open in your default browser.

### Starting via Python Command Line
```bash
python app.py
```
Open your browser and navigate to: `http://localhost:5001`

---

## Folder Structure
```
CCTV Camera/
│
├── app.py                       # Main Flask web server & SocketIO event handlers
├── CCTV_Scanner.bat             # Administrator helper bootstrapper script
├── requirements.txt             # Python packages manifest
├── .env.example                 # Template for local environment setup
├── .env                         # Local runtime config (contains secret keys, nmap path)
├── SETUP.md                     # Direct python setup guide
├── host_setup.md                # Detailed guide for Cloudflare tunnel hosting
│
├── scanner/                     # Core scanning python package
│   ├── __init__.py              # Package entry point
│   ├── network_scanner.py       # Nmap parsing, port probing, & device detection
│   └── utils.py                 # OS admin checking, logging, IP validation, IP detection
│
├── static/                      # Static client-side web assets
│   ├── css/
│   │   └── style.css            # Custom CSS for Light/Dark UI and layout
│   └── js/
│       ├── main.js              # Socket connections & tab switching logic
│       ├── network-scan.js      # Network scan UI handling
│       └── sensor-scan.js       # Mobile sensor calibrator scripts
│
└── templates/                   # Flask templates
    └── index.html               # Main dashboard HTML template
```

---

## Security Features
- **Admin Privilege Checks**: Network scanning functions test for Administrative/Root privileges (`is_admin()` helper) to ensure socket operations can run correctly.
- **Port Cleanup & Reclaim**: The startup batch script kills conflicting ports and old hanging tunnel connections to prevent daemon leaks.
- **Encrypted WebSocket Transport**: Supports remote scanning safely over HTTPS when served through a Cloudflare Tunnel.
- **Disclaimer & Limitations**:
  - The dashboard operates without authentication by default. Do not share your trycloudflare.com URL with untrusted parties.
  - Scan targets are limited to authorized ranges.

---

## Testing
- **Nmap Verification**: Run `nmap --version` in terminal/command prompt to verify installation.
- **Port Conflict Test**: Check if port `5001` is free by running:
  - Windows: `netstat -ano | findstr :5001`
  - Linux: `ss -lntu | grep 5001`
- **Mock Scanning**: Use local subnet range (e.g., `127.0.0.1` or `192.168.1.0/24`) to confirm scan progress events are transmitting correctly via WebSockets.

---

## Future Improvements
1. **User Authentication**: Add a basic login page or passcode requirement to protect the remote dashboard.
2. **ONVIF Integration**: Automate camera stream scanning by adding ONVIF handshake capability to grab camera metadata.
3. **Capture Preview Screenshots**: Automatically try default RTSP credentials to capture a frame from detected security cameras and display it in the Live View Modal.
4. **Vulnerability Assessment**: Identify outdated firmware versions on standard CCTV/DVR units based on scanned banner details.
