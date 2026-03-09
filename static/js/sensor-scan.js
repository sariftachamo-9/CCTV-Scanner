// Sensor-based detection for mobile devices
let sensorScanActive = false;
let magnetometer = null;
let scanInterval_sensor = null;

// Start sensor scan
function startSensorScan() {
    if (!/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
        alert('Sensor scan is only available on mobile devices');
        return;
    }
    
    sensorScanActive = true;
    document.getElementById('startSensorScan').disabled = true;
    document.getElementById('stopSensorScan').disabled = false;
    
    const status = document.getElementById('sensorStatus');
    status.innerHTML = '<div class="loading"></div> Scanning for hidden cameras...';
    
    // Clear previous results
    document.getElementById('sensorResults').innerHTML = '';
    
    // Start sensor monitoring
    startMagnetometerScan();
    startIRDetection();
    
    // Simulate movement instructions
    setTimeout(() => {
        addSensorTip('Move your phone slowly around the room');
    }, 2000);
    
    setTimeout(() => {
        addSensorTip('Check near electronics and power outlets');
    }, 4000);
    
    setTimeout(() => {
        addSensorTip('Turn off lights for better IR detection');
    }, 6000);
}

// Stop sensor scan
function stopSensorScan() {
    sensorScanActive = false;
    document.getElementById('startSensorScan').disabled = false;
    document.getElementById('stopSensorScan').disabled = true;
    
    if (scanInterval_sensor) {
        clearInterval(scanInterval_sensor);
    }
    
    if (magnetometer) {
        magnetometer.stop();
    }
    
    const status = document.getElementById('sensorStatus');
    status.innerHTML = '<p>Scan stopped</p>';
}

// Start magnetometer scan
function startMagnetometerScan() {
    if ('Magnetometer' in window) {
        try {
            magnetometer = new Magnetometer({ frequency: 10 });
            
            magnetometer.addEventListener('reading', () => {
                if (!sensorScanActive) return;
                
                const strength = Math.sqrt(
                    magnetometer.x ** 2 + 
                    magnetometer.y ** 2 + 
                    magnetometer.z ** 2
                );
                
                // Check for anomalous magnetic fields
                if (strength > 50) {
                    addSensorDetection({
                        type: 'magnetic_field',
                        strength: strength,
                        location: 'nearby',
                        confidence: Math.min(strength, 100)
                    });
                }
            });
            
            magnetometer.start();
        } catch (error) {
            console.error('Magnetometer error:', error);
            addSensorTip('Magnetometer not available - using fallback detection');
            startFallbackDetection();
        }
    } else {
        startFallbackDetection();
    }
}

// Fallback detection using device motion
function startFallbackDetection() {
    if (window.DeviceMotionEvent) {
        window.addEventListener('devicemotion', (event) => {
            if (!sensorScanActive) return;
            
            const acceleration = event.accelerationIncludingGravity;
            if (acceleration) {
                const magnitude = Math.sqrt(
                    acceleration.x ** 2 + 
                    acceleration.y ** 2 + 
                    acceleration.z ** 2
                );
                
                // Detect sudden movements that might indicate electronics
                if (magnitude > 15) {
                    // This is very basic and not reliable
                    console.log('Movement detected:', magnitude);
                }
            }
        });
    }
}

// Start IR detection using camera
function startIRDetection() {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: 'environment',
                advanced: [{ torch: true }] 
            } 
        })
        .then(stream => {
            const video = document.createElement('video');
            video.srcObject = stream;
            video.play();
            
            // Create canvas for frame analysis
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            
            scanInterval_sensor = setInterval(() => {
                if (!sensorScanActive) {
                    clearInterval(scanInterval_sensor);
                    stream.getTracks().forEach(track => track.stop());
                    return;
                }
                
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);
                
                // Analyze image for IR signatures
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const irDetected = detectIRGlow(imageData);
                
                if (irDetected) {
                    addSensorDetection({
                        type: 'infrared',
                        strength: irDetected.intensity,
                        location: 'camera lens detected',
                        confidence: 85
                    });
                }
            }, 1000);
        })
        .catch(error => {
            console.error('Camera access error:', error);
            addSensorTip('Could not access camera for IR detection');
        });
    }
}

// Detect IR glow in image data
function detectIRGlow(imageData) {
    const data = imageData.data;
    let irPixels = 0;
    
    // Look for purple/reddish glow (common in IR)
    for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        
        // Check for IR signature (reddish-purple)
        if (r > 200 && g < 100 && b > 150) {
            irPixels++;
        }
    }
    
    const totalPixels = data.length / 4;
    const ratio = irPixels / totalPixels;
    
    if (ratio > 0.01) { // More than 1% of pixels show IR
        return {
            detected: true,
            intensity: ratio * 100
        };
    }
    
    return false;
}

// Add sensor detection result
function addSensorDetection(detection) {
    const resultsDiv = document.getElementById('sensorResults');
    const timestamp = new Date().toLocaleTimeString();
    
    const html = `
        <div class="result-item camera">
            <div class="ip">⚠️ ${detection.type.replace('_', ' ').toUpperCase()}</div>
            <span class="confidence">${detection.confidence}% confidence</span>
            <div class="ports">Strength: ${detection.strength.toFixed(2)}</div>
            <div class="ports">Time: ${timestamp}</div>
        </div>
    `;
    
    resultsDiv.insertAdjacentHTML('afterbegin', html);
    
    // Send to server for analysis
    sendSensorData(detection);
}

// Send sensor data to server
function sendSensorData(detection) {
    fetch('/api/sensor-scan', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            sensorData: detection
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.threats && data.threats.length > 0) {
            // Update UI with server analysis
            console.log('Server detected threats:', data.threats);
        }
    })
    .catch(error => {
        console.error('Error sending sensor data:', error);
    });
}

// Add sensor tip
function addSensorTip(tip) {
    const status = document.getElementById('sensorStatus');
    status.innerHTML = `<p>💡 ${tip}</p>`;
}

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    if (sensorScanActive) {
        stopSensorScan();
    }
});
