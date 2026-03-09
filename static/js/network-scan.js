// Network scanning utilities
let activeNetworkScans = new Map();

// Perform quick port scan on single IP
function quickScanIP(ip) {
    const commonPorts = [80, 443, 554, 8080, 8081, 8888, 37777];
    const openPorts = [];
    
    commonPorts.forEach(port => {
        const img = new Image();
        const timeout = setTimeout(() => {
            img.onerror = null;
            img.onload = null;
        }, 2000);
        
        img.onload = () => {
            clearTimeout(timeout);
            openPorts.push({
                port: port,
                service: identifyService(port)
            });
        };
        
        img.onerror = () => {
            clearTimeout(timeout);
        };
        
        img.src = `http://${ip}:${port}/snapshot.jpg?t=${Date.now()}`;
    });
    
    return openPorts;
}

// Identify service by port
function identifyService(port) {
    const services = {
        80: 'HTTP Web Interface',
        443: 'HTTPS Web Interface',
        554: 'RTSP Stream',
        8080: 'HTTP Alternate',
        8081: 'HTTP Alternate',
        8888: 'HTTP Camera Port',
        37777: 'Dahua Camera Port'
    };
    
    return services[port] || 'Unknown';
}

// Get MAC address vendor
function getMacVendor(mac) {
    const vendors = {
        '00:11:22': 'Generic Camera',
        'AC:CC:8E': 'Hikvision',
        '00:12:3F': 'Dahua',
        '00:1C:CF': 'Axis',
        '00:40:8C': 'Bosch',
        '00:0C:43': 'Samsung',
        '00:1E:C0': 'Panasonic'
    };
    
    const prefix = mac.substring(0, 8).toUpperCase();
    return vendors[prefix] || 'Unknown Manufacturer';
}

// Validate if IP is camera
function validateCamera(ip) {
    return new Promise((resolve) => {
        // Try RTSP first
        const rtspCheck = new Image();
        rtspCheck.onload = () => resolve(true);
        rtspCheck.onerror = () => {
            // Try HTTP snapshot
            const httpCheck = new Image();
            httpCheck.onload = () => resolve(true);
            httpCheck.onerror = () => resolve(false);
            httpCheck.src = `http://${ip}/snapshot.jpg?t=${Date.now()}`;
        };
        rtspCheck.src = `http://${ip}:554/snapshot.jpg?t=${Date.now()}`;
    });
}

// Export network scan results
function exportNetworkResults() {
    const results = [];
    document.querySelectorAll('#networkResults .result-item').forEach(item => {
        const ip = item.querySelector('.ip').textContent;
        const confidence = item.querySelector('.confidence').textContent;
        results.push({ ip, confidence });
    });
    
    const dataStr = JSON.stringify(results, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = 'network-scan-results.json';
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
}
