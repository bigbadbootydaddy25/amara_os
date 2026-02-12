// AMARA OS Animation System with Feathered Edge Masking
// No black rectangles - smooth, soft edge blending

// Constants
const DEGREES_TO_RADIANS = Math.PI / 180;

// ROI Configuration (640x640 canvas)
const ROI_CONFIG = {
    eyesLeft: { x: 175, y: 135, w: 75, h: 85, feather: 15 },
    eyesRight: { x: 390, y: 135, w: 75, h: 85, feather: 15 },
    mouth: { x: 240, y: 370, w: 160, h: 100, feather: 20 }
};

// Global state
let isSplitView = false;
let autoBlinkTimer = null;

// Canvas references
const baseCanvas = document.getElementById('baseCanvas');
const litCanvas = document.getElementById('litCanvas');
const baseCtx = baseCanvas.getContext('2d', { willReadFrequently: true });
const litCtx = litCanvas.getContext('2d', { willReadFrequently: true });

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeCanvases();
    setupEventListeners();
});

function initializeCanvases() {
    // Draw base robot face on both canvases
    drawBaseRobot(baseCtx);
    drawBaseRobot(litCtx);
}

function drawBaseRobot(ctx) {
    // Clear canvas
    ctx.fillStyle = '#2a2a2a';
    ctx.fillRect(0, 0, 640, 640);
    
    // Draw robot head outline
    ctx.fillStyle = '#4a4a4a';
    ctx.fillRect(80, 80, 480, 480);
    
    // Draw antenna
    ctx.fillStyle = '#666';
    ctx.fillRect(310, 30, 20, 50);
    ctx.beginPath();
    ctx.arc(320, 25, 10, 0, Math.PI * 2);
    ctx.fill();
    
    // Draw eyes (dark/off state)
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(ROI_CONFIG.eyesLeft.x, ROI_CONFIG.eyesLeft.y, 
                 ROI_CONFIG.eyesLeft.w, ROI_CONFIG.eyesLeft.h);
    ctx.fillRect(ROI_CONFIG.eyesRight.x, ROI_CONFIG.eyesRight.y, 
                 ROI_CONFIG.eyesRight.w, ROI_CONFIG.eyesRight.h);
    
    // Draw mouth (dark/off state)
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(ROI_CONFIG.mouth.x, ROI_CONFIG.mouth.y, 
                 ROI_CONFIG.mouth.w, ROI_CONFIG.mouth.h);
}

function createFeatheredMask(width, height, roi) {
    // Create temporary canvas for the mask
    const maskCanvas = document.createElement('canvas');
    maskCanvas.width = width;
    maskCanvas.height = height;
    const maskCtx = maskCanvas.getContext('2d');
    
    const { x, y, w, h, feather } = roi;
    
    // Draw base rectangle with full opacity
    maskCtx.fillStyle = 'white';
    maskCtx.fillRect(x + feather, y + feather, w - feather * 2, h - feather * 2);
    
    // Create feathered edges using gradients on all four sides
    // Top edge
    const topGradient = maskCtx.createLinearGradient(x, y, x, y + feather);
    topGradient.addColorStop(0, 'rgba(255, 255, 255, 0)');
    topGradient.addColorStop(1, 'rgba(255, 255, 255, 1)');
    maskCtx.fillStyle = topGradient;
    maskCtx.fillRect(x + feather, y, w - feather * 2, feather);
    
    // Bottom edge
    const bottomGradient = maskCtx.createLinearGradient(x, y + h - feather, x, y + h);
    bottomGradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    bottomGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    maskCtx.fillStyle = bottomGradient;
    maskCtx.fillRect(x + feather, y + h - feather, w - feather * 2, feather);
    
    // Left edge
    const leftGradient = maskCtx.createLinearGradient(x, y, x + feather, y);
    leftGradient.addColorStop(0, 'rgba(255, 255, 255, 0)');
    leftGradient.addColorStop(1, 'rgba(255, 255, 255, 1)');
    maskCtx.fillStyle = leftGradient;
    maskCtx.fillRect(x, y + feather, feather, h - feather * 2);
    
    // Right edge
    const rightGradient = maskCtx.createLinearGradient(x + w - feather, y, x + w, y);
    rightGradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    rightGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    maskCtx.fillStyle = rightGradient;
    maskCtx.fillRect(x + w - feather, y + feather, feather, h - feather * 2);
    
    // Corner feathering using radial gradients
    // Top-left corner
    const tlGradient = maskCtx.createRadialGradient(x + feather, y + feather, 0, x + feather, y + feather, feather);
    tlGradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    tlGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    maskCtx.fillStyle = tlGradient;
    maskCtx.fillRect(x, y, feather, feather);
    
    // Top-right corner
    const trGradient = maskCtx.createRadialGradient(x + w - feather, y + feather, 0, x + w - feather, y + feather, feather);
    trGradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    trGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    maskCtx.fillStyle = trGradient;
    maskCtx.fillRect(x + w - feather, y, feather, feather);
    
    // Bottom-left corner
    const blGradient = maskCtx.createRadialGradient(x + feather, y + h - feather, 0, x + feather, y + h - feather, feather);
    blGradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    blGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    maskCtx.fillStyle = blGradient;
    maskCtx.fillRect(x, y + h - feather, feather, feather);
    
    // Bottom-right corner
    const brGradient = maskCtx.createRadialGradient(x + w - feather, y + h - feather, 0, x + w - feather, y + h - feather, feather);
    brGradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    brGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    maskCtx.fillStyle = brGradient;
    maskCtx.fillRect(x + w - feather, y + h - feather, feather, feather);
    
    return maskCanvas;
}

function drawOverlayWithFeathering(ctx, roi, color, alpha = 1.0) {
    const { x, y, w, h } = roi;
    
    // Create temporary canvas for overlay
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = 640;
    tempCanvas.height = 640;
    const tempCtx = tempCanvas.getContext('2d');
    
    // Draw colored rectangle
    tempCtx.fillStyle = color;
    tempCtx.globalAlpha = alpha;
    tempCtx.fillRect(x, y, w, h);
    
    // Apply feathered mask
    const mask = createFeatheredMask(640, 640, roi);
    tempCtx.globalCompositeOperation = 'destination-in';
    tempCtx.drawImage(mask, 0, 0);
    
    // Composite onto main canvas with lighten blend mode
    ctx.globalCompositeOperation = 'lighten';
    ctx.drawImage(tempCanvas, 0, 0);
    ctx.globalCompositeOperation = 'source-over';
}

function initiateRobot() {
    console.log('Initiating robot...');
    
    // Redraw base
    drawBaseRobot(litCtx);
    
    // Light up eyes with feathered blend
    drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesLeft, '#00ff88', 0.8);
    drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesRight, '#00ff88', 0.8);
    
    // Light up mouth
    drawOverlayWithFeathering(litCtx, ROI_CONFIG.mouth, '#ff6600', 0.6);
    
    // Start auto-blink
    scheduleAutoBlink();
}

function talkRobot() {
    console.log('Robot talking...');
    
    // Ensure eyes are lit
    drawBaseRobot(litCtx);
    drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesLeft, '#00ff88', 0.8);
    drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesRight, '#00ff88', 0.8);
    
    let cycle = 0;
    const maxCycles = 2;
    
    const talkInterval = setInterval(() => {
        if (cycle >= maxCycles * 2) {
            clearInterval(talkInterval);
            // Return to normal state
            drawOverlayWithFeathering(litCtx, ROI_CONFIG.mouth, '#ff6600', 0.6);
            return;
        }
        
        // Redraw base and eyes
        drawBaseRobot(litCtx);
        drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesLeft, '#00ff88', 0.8);
        drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesRight, '#00ff88', 0.8);
        
        // Alternate mouth state
        if (cycle % 2 === 0) {
            // Open mouth (brighter)
            drawOverlayWithFeathering(litCtx, ROI_CONFIG.mouth, '#ffaa00', 0.9);
        } else {
            // Closed mouth (dimmer)
            drawOverlayWithFeathering(litCtx, ROI_CONFIG.mouth, '#ff6600', 0.4);
        }
        
        cycle++;
    }, 200);
}

function blinkRobot() {
    console.log('Robot blinking...');
    
    // Save current state of eye regions only (more efficient than full canvas)
    const padding = ROI_CONFIG.eyesLeft.feather;
    const leftEyeData = litCtx.getImageData(
        ROI_CONFIG.eyesLeft.x - padding, 
        ROI_CONFIG.eyesLeft.y - padding,
        ROI_CONFIG.eyesLeft.w + padding * 2, 
        ROI_CONFIG.eyesLeft.h + padding * 2
    );
    const rightEyeData = litCtx.getImageData(
        ROI_CONFIG.eyesRight.x - padding, 
        ROI_CONFIG.eyesRight.y - padding,
        ROI_CONFIG.eyesRight.w + padding * 2, 
        ROI_CONFIG.eyesRight.h + padding * 2
    );
    
    // Close eyes (redraw dark eyes)
    litCtx.fillStyle = '#1a1a1a';
    litCtx.fillRect(ROI_CONFIG.eyesLeft.x, ROI_CONFIG.eyesLeft.y, 
                    ROI_CONFIG.eyesLeft.w, ROI_CONFIG.eyesLeft.h);
    litCtx.fillRect(ROI_CONFIG.eyesRight.x, ROI_CONFIG.eyesRight.y, 
                    ROI_CONFIG.eyesRight.w, ROI_CONFIG.eyesRight.h);
    
    // Reopen after 150ms
    setTimeout(() => {
        litCtx.putImageData(leftEyeData, ROI_CONFIG.eyesLeft.x - padding, ROI_CONFIG.eyesLeft.y - padding);
        litCtx.putImageData(rightEyeData, ROI_CONFIG.eyesRight.x - padding, ROI_CONFIG.eyesRight.y - padding);
    }, 150);
}

function headTurnRobot() {
    console.log('Robot turning head...');
    
    let angle = 0;
    const maxAngle = 15; // degrees
    const steps = 30;
    const stepAngle = maxAngle / (steps / 2);
    let direction = 1;
    let currentStep = 0;
    
    const turnInterval = setInterval(() => {
        if (currentStep >= steps) {
            clearInterval(turnInterval);
            // Reset to center
            litCtx.setTransform(1, 0, 0, 1, 0, 0);
            drawBaseRobot(litCtx);
            drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesLeft, '#00ff88', 0.8);
            drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesRight, '#00ff88', 0.8);
            drawOverlayWithFeathering(litCtx, ROI_CONFIG.mouth, '#ff6600', 0.6);
            return;
        }
        
        // Change direction at halfway point
        if (currentStep === steps / 2) {
            direction = -1;
        }
        
        angle += stepAngle * direction;
        
        // Apply 3D perspective transform
        litCtx.setTransform(1, 0, 0, 1, 0, 0);
        litCtx.clearRect(0, 0, 640, 640);
        
        // Translate to center, rotate, translate back
        litCtx.translate(320, 320);
        litCtx.rotate(angle * DEGREES_TO_RADIANS);
        litCtx.scale(1 - Math.abs(angle) / 100, 1);
        litCtx.translate(-320, -320);
        
        // Redraw robot
        drawBaseRobot(litCtx);
        drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesLeft, '#00ff88', 0.8);
        drawOverlayWithFeathering(litCtx, ROI_CONFIG.eyesRight, '#00ff88', 0.8);
        drawOverlayWithFeathering(litCtx, ROI_CONFIG.mouth, '#ff6600', 0.6);
        
        currentStep++;
    }, 50);
}

function scheduleAutoBlink() {
    if (autoBlinkTimer) {
        clearTimeout(autoBlinkTimer);
    }
    
    autoBlinkTimer = setTimeout(() => {
        // 70% chance to blink
        if (Math.random() < 0.7) {
            blinkRobot();
        }
        // Schedule next auto-blink
        scheduleAutoBlink();
    }, 5000);
}

function setupEventListeners() {
    document.getElementById('toggleView').addEventListener('click', () => {
        isSplitView = !isSplitView;
        const mainContent = document.getElementById('mainContent');
        const baseWrapper = document.getElementById('baseWrapper');
        const litWrapper = document.getElementById('litWrapper');
        
        if (isSplitView) {
            mainContent.classList.remove('single-view');
            mainContent.classList.add('split-view');
            baseWrapper.style.display = 'block';
            litWrapper.style.display = 'block';
        } else {
            mainContent.classList.remove('split-view');
            mainContent.classList.add('single-view');
            baseWrapper.style.display = 'none';
            litWrapper.style.display = 'block';
        }
    });
    
    document.getElementById('initiateBtn').addEventListener('click', initiateRobot);
    document.getElementById('talkBtn').addEventListener('click', talkRobot);
    document.getElementById('blinkBtn').addEventListener('click', blinkRobot);
    document.getElementById('headTurnBtn').addEventListener('click', headTurnRobot);
}
