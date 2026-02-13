// AMARA OS Animation Controller with Feathered Edge Masking

// State management
const state = {
    canvas: null,
    ctx: null,
    baseImage: null,
    isInitiated: false,
    isAnimating: false,
    autoBlinkInterval: null
};

// ROI Configuration for 640x640 canvas with feather parameters
const ROI = {
    eyesLeft: { x: 175, y: 135, w: 75, h: 85, feather: 15 },
    eyesRight: { x: 390, y: 135, w: 75, h: 85, feather: 15 },
    mouth: { x: 240, y: 370, w: 160, h: 100, feather: 20 }
};

// Image paths
const IMAGES = {
    base: 'public/robot_base.png',
    eyesLit: 'public/eyes_lit.png',
    eyesBlink: 'public/eyes_blink.png',
    mouthTalk: 'public/mouth_talk.png',
    headTurn: 'public/head_turn.png'
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', init);

function init() {
    state.canvas = document.getElementById('robotCanvas');
    state.ctx = state.canvas.getContext('2d');
    
    // Load base image immediately on default load
    const baseImg = document.getElementById('robotBase');
    state.baseImage = new Image();
    state.baseImage.onload = () => {
        baseImg.src = state.baseImage.src;
        console.log('Base robot image loaded');
    };
    state.baseImage.onerror = () => {
        showError('Failed to load robot base image. Please ensure robot_base.png exists in /public directory.');
    };
    state.baseImage.src = IMAGES.base;
    
    // Setup event listeners for control buttons
    document.getElementById('initiateBtn').addEventListener('click', initiateRobot);
    document.getElementById('blinkBtn').addEventListener('click', blinkRobot);
    document.getElementById('talkBtn').addEventListener('click', talkRobot);
    document.getElementById('headTurnBtn').addEventListener('click', headTurnRobot);
}

/**
 * Create feathered mask using radial gradient for smooth edge blending
 * @param {Object} roi - Region of interest {x, y, w, h, feather}
 * @returns {ImageData} - ImageData with alpha channel for masking
 */
function createFeatheredMask(roi) {
    const maskCanvas = document.createElement('canvas');
    maskCanvas.width = roi.w;
    maskCanvas.height = roi.h;
    const maskCtx = maskCanvas.getContext('2d');
    
    // Calculate center and radius for radial gradient
    const centerX = roi.w / 2;
    const centerY = roi.h / 2;
    const maxRadius = Math.max(roi.w, roi.h) / 2;
    const innerRadius = maxRadius - roi.feather;
    
    // Create radial gradient from center
    const gradient = maskCtx.createRadialGradient(
        centerX, centerY, innerRadius,
        centerX, centerY, maxRadius
    );
    
    // Full opacity in center, fade to transparent at edges
    gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    
    // Fill with gradient
    maskCtx.fillStyle = gradient;
    maskCtx.fillRect(0, 0, roi.w, roi.h);
    
    return maskCtx.getImageData(0, 0, roi.w, roi.h);
}

/**
 * Draw overlay with feathered edges for seamless blending
 * @param {HTMLImageElement} overlayImg - Overlay image to draw
 * @param {Object} roi - Region of interest with feather parameter
 */
function drawOverlayWithFeather(overlayImg, roi) {
    // Create temporary canvas for overlay processing
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = roi.w;
    tempCanvas.height = roi.h;
    const tempCtx = tempCanvas.getContext('2d');
    
    // Draw overlay image section
    tempCtx.drawImage(
        overlayImg,
        roi.x, roi.y, roi.w, roi.h,
        0, 0, roi.w, roi.h
    );
    
    // Get overlay image data
    const overlayData = tempCtx.getImageData(0, 0, roi.w, roi.h);
    
    // Create and apply feathered mask to alpha channel
    const mask = createFeatheredMask(roi);
    
    for (let i = 0; i < overlayData.data.length; i += 4) {
        const maskAlpha = mask.data[i + 3] / 255;
        overlayData.data[i + 3] *= maskAlpha;
    }
    
    // Put processed data back
    tempCtx.putImageData(overlayData, 0, 0);
    
    // Use lighten composite mode for smooth integration
    state.ctx.globalCompositeOperation = 'lighten';
    state.ctx.drawImage(tempCanvas, roi.x, roi.y);
    state.ctx.globalCompositeOperation = 'source-over';
}

/**
 * Clear canvas overlay
 */
function clearOverlay() {
    state.ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
}

/**
 * Initiate robot - Light up eyes with feathered blend
 */
async function initiateRobot() {
    if (state.isAnimating) return;
    
    state.isAnimating = true;
    disableButtons(true);
    
    try {
        const eyesLit = await loadImage(IMAGES.eyesLit);
        
        clearOverlay();
        
        // Draw lit eyes with feathered masking
        drawOverlayWithFeather(eyesLit, ROI.eyesLeft);
        drawOverlayWithFeather(eyesLit, ROI.eyesRight);
        
        state.isInitiated = true;
        
        // Start auto-blink after initiation
        scheduleAutoBlink();
        
        console.log('Robot initiated with feathered eyes');
    } catch (error) {
        showError('Failed to load eyes_lit.png: ' + error.message);
    }
    
    state.isAnimating = false;
    disableButtons(false);
}

/**
 * Blink animation with feathered eye regions
 */
async function blinkRobot() {
    if (state.isAnimating || !state.isInitiated) return;
    
    state.isAnimating = true;
    disableButtons(true);
    
    try {
        const eyesBlink = await loadImage(IMAGES.eyesBlink);
        const eyesLit = await loadImage(IMAGES.eyesLit);
        
        // Blink closed
        clearOverlay();
        drawOverlayWithFeather(eyesBlink, ROI.eyesLeft);
        drawOverlayWithFeather(eyesBlink, ROI.eyesRight);
        
        await sleep(150);
        
        // Eyes open
        clearOverlay();
        drawOverlayWithFeather(eyesLit, ROI.eyesLeft);
        drawOverlayWithFeather(eyesLit, ROI.eyesRight);
        
        console.log('Blink animation completed');
    } catch (error) {
        showError('Failed to load blink images: ' + error.message);
    }
    
    state.isAnimating = false;
    disableButtons(false);
}

/**
 * Talk animation - Mouth animation 2 cycles with ROI feathering
 */
async function talkRobot() {
    if (state.isAnimating || !state.isInitiated) return;
    
    state.isAnimating = true;
    disableButtons(true);
    
    try {
        const mouthTalk = await loadImage(IMAGES.mouthTalk);
        const eyesLit = await loadImage(IMAGES.eyesLit);
        
        // 2 cycles of mouth movement
        for (let i = 0; i < 2; i++) {
            // Mouth open
            clearOverlay();
            drawOverlayWithFeather(eyesLit, ROI.eyesLeft);
            drawOverlayWithFeather(eyesLit, ROI.eyesRight);
            drawOverlayWithFeather(mouthTalk, ROI.mouth);
            
            await sleep(200);
            
            // Mouth closed
            clearOverlay();
            drawOverlayWithFeather(eyesLit, ROI.eyesLeft);
            drawOverlayWithFeather(eyesLit, ROI.eyesRight);
            
            await sleep(150);
        }
        
        console.log('Talk animation completed');
    } catch (error) {
        showError('Failed to load mouth_talk.png: ' + error.message);
    }
    
    state.isAnimating = false;
    disableButtons(false);
}

/**
 * Head turn animation - 3D head rotation effect
 */
async function headTurnRobot() {
    if (state.isAnimating || !state.isInitiated) return;
    
    state.isAnimating = true;
    disableButtons(true);
    
    try {
        const headTurn = await loadImage(IMAGES.headTurn);
        const baseImg = document.getElementById('robotBase');
        
        // Turn right
        baseImg.style.transform = 'rotateY(25deg)';
        await sleep(300);
        
        // Turn left
        baseImg.style.transform = 'rotateY(-25deg)';
        await sleep(300);
        
        // Back to center
        baseImg.style.transform = 'rotateY(0deg)';
        await sleep(200);
        
        console.log('Head turn animation completed');
    } catch (error) {
        showError('Failed to perform head turn: ' + error.message);
    }
    
    state.isAnimating = false;
    disableButtons(false);
}

/**
 * Schedule automatic blink every 5 seconds with 70% chance
 */
function scheduleAutoBlink() {
    if (state.autoBlinkInterval) {
        clearInterval(state.autoBlinkInterval);
    }
    
    state.autoBlinkInterval = setInterval(() => {
        if (!state.isAnimating && state.isInitiated && Math.random() < 0.7) {
            blinkRobot();
        }
    }, 5000);
}

/**
 * Helper: Load image
 */
function loadImage(src) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error(`Failed to load ${src}`));
        img.src = src;
    });
}

/**
 * Helper: Sleep/delay
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Helper: Disable/enable control buttons
 */
function disableButtons(disabled) {
    document.querySelectorAll('.btn-control').forEach(btn => {
        btn.disabled = disabled;
    });
}

/**
 * Helper: Show error message
 */
function showError(message) {
    const errorDisplay = document.getElementById('errorDisplay');
    errorDisplay.textContent = message;
    errorDisplay.classList.add('show');
    console.error(message);
    
    setTimeout(() => {
        errorDisplay.classList.remove('show');
    }, 5000);
}
