// Main application logic
let socket;
let currentScanId = null;
let scanInterval = null;
let detectedCameras = [];
let networkData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    initializeSocket();
    detectDeviceType();
    loadNetworkInfo();
    checkSensorSupport();
});

// Theme Management
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const toggleBtn = document.getElementById('themeToggle');
    if (toggleBtn) {
        toggleBtn.textContent = theme === 'light' ? '🌙' : '☀️';
    }
}

// Initialize Socket.IO connection
function initializeSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to server');
    });
    
    socket.on('scan_progress', function(data) {
        if (data.scan_type === 'traffic') {
            updateTrafficProgress(data);
        } else {
            updateScanProgress(data);
        }
    });

    socket.on('traffic_found', function(data) {
        addDetectedTrafficDevice(data.device);
    });
    
    socket.on('scan_error', function(data) {
        addScanAlert('Scan Error: ' + data.error, 'error');
        if (data.scan_type === 'traffic') {
            stopTrafficScan();
        } else {
            stopNetworkScan();
        }
    });
    
    socket.on('camera_found', function(data) {
        addDetectedCamera(data.camera);
    });
    
    socket.on('scan_complete', function(data) {
        if (data.scan_type === 'traffic') {
            completeTrafficScan(data);
        } else {
            completeScan(data);
        }
    });
    
    socket.on('scan_started', function(data) {
        currentScanId = data.scan_id;
        if (data.scan_type === 'traffic') {
            document.getElementById('startTrafficScan').disabled = true;
            document.getElementById('stopTrafficScan').disabled = false;
            document.getElementById('trafficProgress').style.display = 'block';
        } else {
            document.getElementById('startNetworkScan').disabled = true;
            document.getElementById('stopNetworkScan').disabled = false;
            document.getElementById('scanProgress').style.display = 'block';
        }
    });
}

// Detect device type (mobile/tablet/desktop)
function detectDeviceType() {
    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    const isTablet = /iPad|Android(?!.*Mobile)/i.test(navigator.userAgent);
    const deviceBadge = document.getElementById('deviceType');
    
    if (isTablet) {
        deviceBadge.textContent = '📱 Tablet Mode - Full sensor support';
    } else if (isMobile) {
        deviceBadge.textContent = '📱 Mobile Mode - Full sensor support';
    } else {
        deviceBadge.textContent = '💻 Desktop Mode - Network scan only';
        // Disable sensor tab on desktop
        const sensorTabBtn = document.querySelector('[onclick*="sensor"]');
        if (sensorTabBtn) sensorTabBtn.disabled = true;
    }
}

// Switch between tabs
function switchTab(tabName, element) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    if (element) {
        element.classList.add('active');
    } else {
        // Find the button if element not provided (e.g. called programmatically)
        const buttons = document.querySelectorAll('.tab-btn');
        buttons.forEach(btn => {
            if (btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(`'${tabName}'`)) {
                btn.classList.add('active');
            }
        });
    }
    
    // Show selected tab
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    const selectedTab = document.getElementById(tabName + '-tab');
    if (selectedTab) {
        selectedTab.classList.add('active');
    }
    
    // Load tab-specific content
    if (tabName === 'results') {
        loadAllResults();
    }
}

// Load network information
function loadNetworkInfo() {
    fetch('/api/network-info')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                networkData = data;
                const networkInfo = document.getElementById('networkInfo');
                
                // Add Cloudflare status to header if active
                if (data.is_cloudflared) {
                    const header = document.querySelector('header');
                    if (!document.getElementById('remoteBadge')) {
                        const badge = document.createElement('div');
                        badge.id = 'remoteBadge';
                        badge.className = 'badge badge-success';
                        badge.style.marginTop = '10px';
                        badge.innerHTML = '🛡️ Secure Remote Access Active';
                        header.appendChild(badge);
                    }
                }

                let adminAlert = '';
                if (!data.is_admin && navigator.platform.toUpperCase().indexOf('WIN') > -1) {
                    adminAlert = `<div class="alert alert-warning" style="font-size: 0.8em; margin-top: 5px;">
                        <strong>Note:</strong> Running as Administrator is recommended for better scanning.
                    </div>`;
                }

                let nmapAlert = '';
                if (!data.nmap_installed) {
                    nmapAlert = `<div class="alert alert-error" style="font-size: 0.8em; margin-top: 5px;">
                        <strong>Critical:</strong> Nmap not found. Network scanning will not work.
                    </div>`;
                }

                networkInfo.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 5px;">
                        <p><strong>Network Range:</strong> <code style="background: #eee; padding: 2px 5px; border-radius: 3px;">${data.network}</code></p>
                        <p><strong>Local IP:</strong> ${data.local_ip}</p>
                        <p><strong>Host:</strong> ${data.hostname}</p>
                        ${adminAlert}
                        ${nmapAlert}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading network info:', error);
            document.getElementById('networkInfo').innerHTML = `<p class="alert alert-error">Failed to load network info. Please check if server is running.</p>`;
        });
}

// Check sensor support
function checkSensorSupport() {
    if (window.DeviceOrientationEvent) {
        console.log('Device orientation supported');
    }
    
    if ('ondevicemotion' in window) {
        console.log('Device motion supported');
    }
    
    // Check magnetometer
    if ('Magnetometer' in window) {
        console.log('Magnetometer supported');
    }
}

// Start network scan
function startNetworkScan() {
    if (networkData && networkData.network) {
        const network = networkData.network;
        const scanId = 'scan_' + Date.now();
        
        socket.emit('start_scan', {
            scan_id: scanId,
            network: network
        });
        
        addScanAlert('Scan started on network: ' + network, 'success');
    } else {
        addScanAlert('Could not determine network range. Please refresh the page.', 'error');
        loadNetworkInfo(); // Try to reload
    }
}

// Start traffic scan
function startTrafficScan() {
    const range = document.getElementById('trafficRange').value.trim();
    if (!range) {
        addScanAlert('Please enter a target range or IP', 'error');
        return;
    }

    const scanId = 'traffic_' + Date.now();
    socket.emit('start_traffic_scan', {
        scan_id: scanId,
        network: range
    });
    
    addScanAlert('Traffic infrastructure scan started on: ' + range, 'success');
}

// Stop traffic scan
function stopTrafficScan() {
    document.getElementById('startTrafficScan').disabled = false;
    document.getElementById('stopTrafficScan').disabled = true;
    document.getElementById('trafficProgress').style.display = 'none';
    addScanAlert('Traffic scan stopped', 'warning');
}

// Update traffic progress
function updateTrafficProgress(data) {
    document.getElementById('trafficProgressBar').style.width = data.progress + '%';
    document.getElementById('trafficProgressText').textContent = `Scanning: ${data.progress}%`;
    document.getElementById('trafficCurrentTarget').textContent = `Current: ${data.current_host}`;
}

// Add detected traffic device
function addDetectedTrafficDevice(device) {
    const resultsDiv = document.getElementById('trafficResults');
    const deviceHtml = `
        <div class="result-item infrastructure">
            <div class="ip">${device.ip}</div>
            <span class="confidence confidence-high">Infrastructure Detected</span>
            <div class="ports">
                <strong>Type:</strong> ${device.type}<br>
                <strong>Hostname:</strong> ${device.hostname}<br>
                <strong>Services:</strong> ${device.ports.map(p => p.service).join(', ')}
            </div>
            <div class="actions">
                <button onclick="saveCamera('${device.ip}')">Save Result</button>
            </div>
        </div>
    `;
    resultsDiv.insertAdjacentHTML('afterbegin', deviceHtml);
    
    // Also add to global results if it's high confidence
    detectedCameras.push({...device, confidence: 90}); 
}

// Complete traffic scan
function completeTrafficScan(data) {
    document.getElementById('startTrafficScan').disabled = false;
    document.getElementById('stopTrafficScan').disabled = true;
    document.getElementById('trafficProgress').style.display = 'none';
    
    addScanAlert(`Traffic scan complete! Found ${data.count} infrastructure devices.`, 'success');
}

// Stop network scan
function stopNetworkScan() {
    if (scanInterval) {
        clearInterval(scanInterval);
        scanInterval = null;
    }
    
    document.getElementById('startNetworkScan').disabled = false;
    document.getElementById('stopNetworkScan').disabled = true;
    document.getElementById('scanProgress').style.display = 'none';
    
    addScanAlert('Scan stopped by user', 'warning');
}

// Update scan progress
function updateScanProgress(data) {
    document.getElementById('progressBar').style.width = data.progress + '%';
    document.getElementById('progressText').textContent = `Scanning: ${data.progress}%`;
    document.getElementById('currentTarget').textContent = `Current: ${data.current_host}`;
}

// Add detected camera to list
function addDetectedCamera(camera) {
    detectedCameras.push(camera);
    
    const resultsDiv = document.getElementById('networkResults');
    const cameraHtml = createCameraCard(camera);
    resultsDiv.insertAdjacentHTML('afterbegin', cameraHtml);
}

// Create camera card HTML
function createCameraCard(camera) {
    const confidence = camera.confidence || 0;
    let confidenceClass = 'low';
    if (confidence > 70) confidenceClass = 'high';
    else if (confidence > 30) confidenceClass = 'medium';
    
    let portsHtml = '';
    camera.ports.forEach(port => {
        portsHtml += `<span class="port-badge">Port ${port.port}: ${port.service}</span> `;
    });
    
    return `
        <div class="result-item camera">
            <div class="ip">${camera.ip}</div>
            <span class="confidence confidence-${confidenceClass}">${confidence}% confidence</span>
            <div class="ports">${portsHtml}</div>
            <div class="actions">
                <button onclick="previewCamera('${camera.ip}')">Preview</button>
                <button onclick="saveCamera('${camera.ip}')">Save</button>
            </div>
        </div>
    `;
}

// Complete scan
function completeScan(data) {
    document.getElementById('startNetworkScan').disabled = false;
    document.getElementById('stopNetworkScan').disabled = true;
    document.getElementById('scanProgress').style.display = 'none';
    
    addScanAlert(`Scan complete! Found ${data.count} potential cameras.`, 'success');
    
    // Switch to results tab
    document.querySelector('[onclick="switchTab(\'results\')"]').click();
}

// Add scan alert
function addScanAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    // Insert into active tab
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab) {
        activeTab.insertBefore(alertDiv, activeTab.firstChild);
    } else {
        const networkTab = document.getElementById('network-tab');
        networkTab.insertBefore(alertDiv, networkTab.firstChild);
    }
    
    // Remove after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Load all results
function loadAllResults() {
    const resultsDiv = document.getElementById('allResults');
    resultsDiv.innerHTML = '';
    
    if (detectedCameras.length === 0) {
        resultsDiv.innerHTML = '<p class="alert alert-info">No cameras detected yet. Run a scan first.</p>';
        return;
    }
    
    detectedCameras.forEach(camera => {
        resultsDiv.insertAdjacentHTML('beforeend', createCameraCard(camera));
    });
}

// Preview camera
function previewCamera(ip) {
    document.getElementById('previewImage').src = `http://${ip}/snapshot.jpg?t=${Date.now()}`;
    document.getElementById('cameraPreviewModal').style.display = 'flex';
}

// Save camera
function saveCamera(ip) {
    const camera = detectedCameras.find(c => c.ip === ip);
    if (camera) {
        localStorage.setItem('saved_camera_' + ip, JSON.stringify(camera));
        addScanAlert('Camera saved to local storage', 'success');
    }
}

// Export results
function exportResults() {
    const dataStr = JSON.stringify(detectedCameras, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = 'camera-scan-results.json';
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
}

// Exit system
function exitSystem() {
    if (confirm('Are you sure you want to shut down the scanner and exit? This will close the server.')) {
        addScanAlert('Shutting down server...', 'warning');
        fetch('/api/shutdown', { method: 'POST' })
            .then(response => {
                if (response.ok) {
                    document.body.innerHTML = `
                        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background: #222; color: white; font-family: sans-serif;">
                            <h1 style="color: #f44336;">System Shutdown</h1>
                            <p>The server has been stopped. You can now close this window.</p>
                        </div>
                    `;
                }
            })
            .catch(err => {
                console.error('Shutdown failed:', err);
                addScanAlert('Shutdown command sent. You may close the console.', 'success');
            });
    }
}

// Close modal
function closeModal() {
    document.getElementById('cameraPreviewModal').style.display = 'none';
}
