# Camera Detection System - Setup Guide

## Python Dependencies Installation

✅ Already installed:
- Flask 2.3.2
- Flask-SocketIO 5.3.4
- Python-SocketIO 5.9.0
- Python-NMap 0.7.1
- NetiInterfaces-Plus 0.12.5
- Requests 2.31.0
- Python-EngineIO 4.7.1

## System Dependencies - NMAP Installation

The project requires **Nmap** to be installed on your system for network scanning functionality.

### Option 1: Download and Install (Recommended)
1. Visit: https://nmap.org/download.html
2. Download **Nmap Windows Installer** (nmap-X.XX-setup.exe)
3. Run the installer and follow the setup wizard
4. Make sure to check "Add Nmap to system PATH" during installation
5. Restart your terminal/PowerShell after installation

### Option 2: Using Chocolatey (if installed)
```powershell
choco install nmap -y
```

### Option 3: Using Windows Package Manager (if installed)
```powershell
winget install Insecure.Nmap
```

## Verify Installation

After installing nmap, verify it in PowerShell:
```powershell
nmap --version
```

If successful, you should see the nmap version number.

## Running the Application

1. Navigate to project directory:
```powershell
cd "c:\Users\97798\Desktop\CyberSEC\Ethical Hacking\CCTV Camera"
```

2. Start the Flask application:
```powershell
python app.py
```

3. Open browser and navigate to:
```
http://localhost:5000
```

## Features

- **Network Scan**: Detect IP cameras on your network
- **Sensor Scan**: Mobile device sensor-based detection
- **Real-time Updates**: WebSocket-based live progress
- **Export Results**: Save scan results as JSON

## Troubleshooting

### "nmap is not recognized" error
- Make sure nmap is installed and added to system PATH
- Restart your terminal after installation
- Try running `nmap --version` to verify

### Port already in use error
- Change the port in app.py or kill the process using port 5000
- On Windows: `netstat -ano | findstr :5000`

### Permission errors
- May occur during network scanning (normal Windows behavior)
- Run PowerShell as Administrator for full network access

## Security Note

This tool is for ethical testing on networks you own or have permission to test.
Unauthorized network scanning may be illegal in your jurisdiction.
