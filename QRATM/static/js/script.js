// static/js/scripts.js

document.addEventListener('DOMContentLoaded', function () {
    // Enable tooltips everywhere
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // PIN input formatting and validation
    const pinInputs = document.querySelectorAll('input[type="password"][maxlength="4"]');
    pinInputs.forEach(input => {
        input.addEventListener('input', function (e) {
            // Keep only digits
            this.value = this.value.replace(/\D/g, '');

            // Limit to 4 digits
            if (this.value.length > 4) {
                this.value = this.value.slice(0, 4);
            }
        });
    });

    // Money input formatting
    const moneyInputs = document.querySelectorAll('input[type="number"][step="0.01"]');
    moneyInputs.forEach(input => {
        input.addEventListener('blur', function () {
            // Format to 2 decimal places when losing focus
            if (this.value) {
                this.value = parseFloat(this.value).toFixed(2);
            }
        });
    });

    // Auto-focus PIN input on confirm page
    const enteredPinInput = document.getElementById('entered_pin');
    if (enteredPinInput) {
        enteredPinInput.focus();
    }

    // Add animation class to success page
    const successPage = document.querySelector('.card-header.bg-success');
    if (successPage) {
        document.querySelector('.card-body').classList.add('success-page');
    }

    // Prevent form submission on Enter key for QR generate form (except the submit button)
    const generateForm = document.getElementById('generateForm');
    if (generateForm) {
        const inputs = generateForm.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && document.activeElement !== document.querySelector('#generateForm button[type="submit"]')) {
                    e.preventDefault();
                    const nextInput = this.nextElementSibling;
                    if (nextInput && nextInput.tagName === 'INPUT') {
                        nextInput.focus();
                    } else {
                        // Find the next form field
                        const nextFormGroup = this.closest('.mb-3').nextElementSibling;
                        if (nextFormGroup) {
                            const nextInput = nextFormGroup.querySelector('input');
                            if (nextInput) {
                                nextInput.focus();
                            }
                        }
                    }
                }
            });
        });
    }

    // Automatically scan QR codes from webcam feed using a basic detection mechanism
    // Note: This is a simplified approach; real-time QR code scanning would typically use a dedicated library
    function setupAutomaticScanning() {
        const video = document.getElementById('webcamVideo');
        const captureBtn = document.getElementById('captureBtn');

        if (!video || !captureBtn) return;

        // We'll check for QR codes every few seconds
        let scanInterval;

        video.addEventListener('play', function () {
            scanInterval = setInterval(function () {
                // Create canvas and draw video frame
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                // Here we would use a QR detection library to analyze the canvas
                // Since we don't have one integrated, this is just a placeholder
                // In a real implementation, you would use a library like jsQR

                // Simulate occasional QR code detection (approximately every 10 seconds)
                // This is just for UI demonstration purposes
                if (Math.random() < 0.02) {  // 2% chance each check (assuming check every 200ms)
                    // Flash the scanner overlay to indicate detection
                    const overlay = document.getElementById('scanner-overlay');
                    if (overlay) {
                        overlay.style.boxShadow = '0 0 0 1000px rgba(40, 167, 69, 0.3)';
                        setTimeout(() => {
                            overlay.style.boxShadow = '0 0 0 1000px rgba(0, 0, 0, 0.3)';
                        }, 300);
                    }

                    // In a real implementation, you would trigger the capture here
                    // captureBtn.click();
                }
            }, 200);  // Check every 200ms
        });

        // Clean up the interval when the video stops
        video.addEventListener('pause', function () {
            clearInterval(scanInterval);
        });

        // Also clean up when leaving the page
        window.addEventListener('beforeunload', function () {
            clearInterval(scanInterval);
        });
    }

    // Initialize automatic scanning
    setupAutomaticScanning();
});
