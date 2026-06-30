// AMARA OS - Robot Face Animation System with Feathered Edge Masking
// Eliminates black rectangle artifacts and creates smooth overlay blending

// Configuration
const CONFIG = {
    canvas: {
        width: 640,
        height: 640
    },
    // ROI Configuration with feathered edges
    roi: {
        eyesLeft: { x: 175, y: 135, w: 75, h: 85, feather: 15 },
        eyesRight: { x: 390, y: 135, w: 75, h: 85, feather: 15 },
        mouth: { x: 240, y: 370, w: 160, h: 100, feather: 20 }
    },
    autoBlink: {
        interval: 5000, // 5 seconds
        probability: 0.7 // 70% chance
    },
    animations: {
        talkCycles: 2,
        blinkDuration: 150,
        headTurnSteps: 10
    }
};

// State Management
const state = {
    isLit: false,
    isSplitView: false,
    autoBlinkTimer: null,
    isAnimating: false
};

// Canvas Elements
let robotCanvas, robotCtx;
let baseCanvas, baseCtx;
let litCanvas, litCtx;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', init);

function init() {
    // Get canvas elements
    robotCanvas = document.getElementById('robotCanvas');
    robotCtx = robotCanvas.getContext('2d');
    baseCanvas = document.getElementById('baseCanvas');
    baseCtx = baseCanvas.getContext('2d');
    litCanvas = document.getElementById('litCanvas');
    litCtx = litCanvas.getContext('2d');

    // Setup event listeners
    document.getElementById('toggleViewBtn').addEventListener('click', toggleView);
    document.getElementById('blinkBtn').addEventListener('click', () => blinkRobot());
    document.getElementById('talkBtn').addEventListener('click', () => talkRobot());
    document.getElementById('turnBtn').addEventListener('click', () => headTurnRobot());
    document.getElementById('litBtn').addEventListener('click', () => initiateRobot());

    // Draw initial robot face
    drawRobotBase(robotCtx);
    drawRobotBase(baseCtx);
    drawRobotBase(litCtx);

    // Start auto-blink
    scheduleAutoBlink();

    console.log('AMARA OS initialized with feathered masking');
}

// ============================================================================
// FEATHERED MASKING FUNCTIONS
// ============================================================================

/**
 * Creates a feathered mask using radial gradient
 * Generates smooth alpha fade over configurable feather distance
 * @param {Object} roi - Region of interest {x, y, w, h, feather}
 * @returns {ImageData} - Mask with proper alpha channel
 */
function createFeatheredMask(roi) {
    const maskCanvas = document.createElement('canvas');
    maskCanvas.width = roi.w;
    maskCanvas.height = roi.h;
    const maskCtx = maskCanvas.getContext('2d');

    // Calculate center point
    const centerX = roi.w / 2;
    const centerY = roi.h / 2;
    
    // Create radial gradient from center
    const maxRadius = Math.max(roi.w, roi.h) / 2;
    const gradient = maskCtx.createRadialGradient(
        centerX, centerY, Math.max(0, maxRadius - roi.feather),
        centerX, centerY, maxRadius
    );
    
    // Gradient from full opacity to transparent
    gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    
    // Apply gradient
    maskCtx.fillStyle = gradient;
    maskCtx.fillRect(0, 0, roi.w, roi.h);
    
    return maskCtx.getImageData(0, 0, roi.w, roi.h);
}

/**
 * Draws overlay with feathered blending
 * Applies feathered mask to alpha channel for smooth integration
 * Uses lighten composite mode to eliminate black rectangles
 * @param {CanvasRenderingContext2D} ctx - Target context
 * @param {HTMLImageElement|string} overlay - Image or color
 * @param {Object} roi - Region of interest with feather
 */
function drawOverlayWithFeather(ctx, overlay, roi) {
    // Create temporary canvas for overlay composition
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = roi.w;
    tempCanvas.height = roi.h;
    const tempCtx = tempCanvas.getContext('2d');

    // Draw overlay (either image or solid color)
    if (typeof overlay === 'string') {
        // Solid color overlay
        tempCtx.fillStyle = overlay;
        tempCtx.fillRect(0, 0, roi.w, roi.h);
    } else {
        // Image overlay
        tempCtx.drawImage(overlay, 0, 0, roi.w, roi.h);
    }

    // Apply feathered mask to alpha channel
    const imageData = tempCtx.getImageData(0, 0, roi.w, roi.h);
    const maskData = createFeatheredMask(roi);
    
    // Multiply alpha channels for feathered edge
    for (let i = 0; i < imageData.data.length; i += 4) {
        const maskAlpha = maskData.data[i + 3] / 255;
        imageData.data[i + 3] *= maskAlpha;
    }
    
    tempCtx.putImageData(imageData, 0, 0);

    // Composite with lighten mode for smooth integration
    ctx.save();
    ctx.globalCompositeOperation = 'lighten';
    ctx.drawImage(tempCanvas, roi.x, roi.y);
    ctx.restore();
}

// ============================================================================
// ROBOT DRAWING FUNCTIONS
// ============================================================================

/**
 * Draws the base robot face (unlit state)
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 */
function drawRobotBase(ctx) {
    // Clear canvas
    ctx.clearRect(0, 0, CONFIG.canvas.width, CONFIG.canvas.height);
    
    // Background
    ctx.fillStyle = '#1a1a3e';
    ctx.fillRect(0, 0, CONFIG.canvas.width, CONFIG.canvas.height);
    
    // Robot head (circle)
    ctx.fillStyle = '#2a2a4e';
    ctx.strokeStyle = '#4a4a7e';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(320, 320, 250, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    
    // Left eye socket
    drawEyeSocket(ctx, CONFIG.roi.eyesLeft);
    
    // Right eye socket
    drawEyeSocket(ctx, CONFIG.roi.eyesRight);
    
    // Mouth area
    drawMouthSocket(ctx, CONFIG.roi.mouth);
}

/**
 * Draws an eye socket (dark recessed area)
 */
function drawEyeSocket(ctx, roi) {
    ctx.fillStyle = '#0a0a1e';
    ctx.strokeStyle = '#1a1a3e';
    ctx.lineWidth = 2;
    
    // Rounded rectangle for eye socket
    const radius = 15;
    ctx.beginPath();
    ctx.roundRect(roi.x, roi.y, roi.w, roi.h, radius);
    ctx.fill();
    ctx.stroke();
}

/**
 * Draws mouth socket (dark recessed area)
 */
function drawMouthSocket(ctx, roi) {
    ctx.fillStyle = '#0a0a1e';
    ctx.strokeStyle = '#1a1a3e';
    ctx.lineWidth = 2;
    
    // Rounded rectangle for mouth
    const radius = 20;
    ctx.beginPath();
    ctx.roundRect(roi.x, roi.y, roi.w, roi.h, radius);
    ctx.fill();
    ctx.stroke();
}

// ============================================================================
// ANIMATION FUNCTIONS
// ============================================================================

/**
 * Initiates robot - lights up the eyes with feathered blend
 */
function initiateRobot() {
    if (state.isAnimating) return;
    
    state.isLit = !state.isLit;
    
    if (state.isLit) {
        // Light up eyes with feathered masking
        const eyeColor = 'rgba(0, 240, 255, 0.9)';
        
        if (state.isSplitView) {
            drawOverlayWithFeather(litCtx, eyeColor, CONFIG.roi.eyesLeft);
            drawOverlayWithFeather(litCtx, eyeColor, CONFIG.roi.eyesRight);
        } else {
            drawOverlayWithFeather(robotCtx, eyeColor, CONFIG.roi.eyesLeft);
            drawOverlayWithFeather(robotCtx, eyeColor, CONFIG.roi.eyesRight);
        }
        
        // Add feathered visual feedback
        robotCanvas.classList.add('feathered-active');
        console.log('Eyes lit with feathered masking');
    } else {
        // Turn off - redraw base
        drawRobotBase(state.isSplitView ? litCtx : robotCtx);
        robotCanvas.classList.remove('feathered-active');
        console.log('Eyes off');
    }
}

/**
 * Talk animation - mouth opens/closes with feathered ROI blending
 * Runs for 2 cycles
 */
async function talkRobot() {
    if (state.isAnimating) return;
    
    state.isAnimating = true;
    const ctx = state.isSplitView ? litCtx : robotCtx;
    
    for (let cycle = 0; cycle < CONFIG.animations.talkCycles; cycle++) {
        // Open mouth
        drawOverlayWithFeather(ctx, 'rgba(255, 100, 100, 0.7)', CONFIG.roi.mouth);
        await sleep(300);
        
        // Close mouth
        drawRobotBase(ctx);
        if (state.isLit) {
            // Restore lit eyes
            const eyeColor = 'rgba(0, 240, 255, 0.9)';
            drawOverlayWithFeather(ctx, eyeColor, CONFIG.roi.eyesLeft);
            drawOverlayWithFeather(ctx, eyeColor, CONFIG.roi.eyesRight);
        }
        await sleep(200);
    }
    
    state.isAnimating = false;
    console.log('Talk animation complete (2 cycles)');
}

/**
 * Blink animation - eyes close/open with feathered masking
 */
async function blinkRobot() {
    if (state.isAnimating) return;
    
    state.isAnimating = true;
    const ctx = state.isSplitView ? litCtx : robotCtx;
    const wasLit = state.isLit;
    
    // Close eyes (draw dark overlay)
    drawOverlayWithFeather(ctx, 'rgba(10, 10, 30, 0.9)', CONFIG.roi.eyesLeft);
    drawOverlayWithFeather(ctx, 'rgba(10, 10, 30, 0.9)', CONFIG.roi.eyesRight);
    
    await sleep(CONFIG.animations.blinkDuration);
    
    // Open eyes (restore previous state)
    drawRobotBase(ctx);
    if (wasLit) {
        const eyeColor = 'rgba(0, 240, 255, 0.9)';
        drawOverlayWithFeather(ctx, eyeColor, CONFIG.roi.eyesLeft);
        drawOverlayWithFeather(ctx, eyeColor, CONFIG.roi.eyesRight);
    }
    
    state.isAnimating = false;
    console.log('Blink animation complete');
}

/**
 * Head turn animation - 3D rotation effect
 * Simple implementation with scaling/skewing
 */
async function headTurnRobot() {
    if (state.isAnimating) return;
    
    state.isAnimating = true;
    const ctx = state.isSplitView ? litCtx : robotCtx;
    const steps = CONFIG.animations.headTurnSteps;
    
    for (let i = 0; i <= steps; i++) {
        const progress = i / steps;
        const angle = Math.sin(progress * Math.PI) * 0.3;
        
        ctx.save();
        ctx.clearRect(0, 0, CONFIG.canvas.width, CONFIG.canvas.height);
        ctx.translate(CONFIG.canvas.width / 2, CONFIG.canvas.height / 2);
        ctx.rotate(angle);
        ctx.scale(1 - Math.abs(angle), 1);
        ctx.translate(-CONFIG.canvas.width / 2, -CONFIG.canvas.height / 2);
        
        drawRobotBase(ctx);
        
        if (state.isLit) {
            const eyeColor = 'rgba(0, 240, 255, 0.9)';
            drawOverlayWithFeather(ctx, eyeColor, CONFIG.roi.eyesLeft);
            drawOverlayWithFeather(ctx, eyeColor, CONFIG.roi.eyesRight);
        }
        
        ctx.restore();
        await sleep(50);
    }
    
    state.isAnimating = false;
    console.log('Head turn animation complete');
}

/**
 * Schedules automatic blinking every 5 seconds (70% probability)
 */
function scheduleAutoBlink() {
    if (state.autoBlinkTimer) {
        clearTimeout(state.autoBlinkTimer);
    }
    
    state.autoBlinkTimer = setTimeout(() => {
        if (!state.isAnimating && Math.random() < CONFIG.autoBlink.probability) {
            blinkRobot();
        }
        scheduleAutoBlink();
    }, CONFIG.autoBlink.interval);
}

// ============================================================================
// VIEW MANAGEMENT
// ============================================================================

/**
 * Toggles between single and split view
 */
function toggleView() {
    state.isSplitView = !state.isSplitView;
    
    const singleView = document.getElementById('singleView');
    const splitView = document.getElementById('splitView');
    
    if (state.isSplitView) {
        singleView.classList.remove('active');
        splitView.classList.add('active');
        
        // Update both canvases
        drawRobotBase(baseCtx);
        drawRobotBase(litCtx);
        
        // Show lit version on right
        const eyeColor = 'rgba(0, 240, 255, 0.9)';
        drawOverlayWithFeather(litCtx, eyeColor, CONFIG.roi.eyesLeft);
        drawOverlayWithFeather(litCtx, eyeColor, CONFIG.roi.eyesRight);
        
        console.log('Split view activated');
    } else {
        splitView.classList.remove('active');
        singleView.classList.add('active');
        
        // Restore single canvas state
        drawRobotBase(robotCtx);
        if (state.isLit) {
            const eyeColor = 'rgba(0, 240, 255, 0.9)';
            drawOverlayWithFeather(robotCtx, eyeColor, CONFIG.roi.eyesLeft);
            drawOverlayWithFeather(robotCtx, eyeColor, CONFIG.roi.eyesRight);
        }
        
        console.log('Single view activated');
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Sleep utility for animations
 * @param {number} ms - Milliseconds to sleep
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Add roundRect polyfill for older browsers
if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
        if (w < 2 * r) r = w / 2;
        if (h < 2 * r) r = h / 2;
        this.beginPath();
        this.moveTo(x + r, y);
        this.arcTo(x + w, y, x + w, y + h, r);
        this.arcTo(x + w, y + h, x, y + h, r);
        this.arcTo(x, y + h, x, y, r);
        this.arcTo(x, y, x + w, y, r);
        this.closePath();
        return this;
    };
}
