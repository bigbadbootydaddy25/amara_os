# AMARA OS - Robot Animation System

Web animation project with robot face and interactive controls, featuring advanced feathered edge masking for seamless overlay blending.

## Features

- **Single View Interface**: Streamlined, centered robot view with no unnecessary complexity
- **Feathered Edge Masking**: Advanced canvas alpha gradients eliminate harsh edges and black rectangle artifacts
- **Smooth Animations**: Initiate, Blink, Talk, and Head Turn animations with professional visual effects
- **Auto-Blink System**: Automatic blinking every 5 seconds (70% probability) for realistic behavior
- **Responsive Design**: Fully responsive layout that works on desktop, tablet, and mobile devices
- **Unified Dark Theme**: Beautiful gradient background (#0a0e27 → #1a1a3e → #0d0f1f)

## Technical Implementation

### Feathered Masking System
The application uses radial gradient masks to create smooth, feathered edges on all overlay animations:

- **createFeatheredMask()**: Generates radial gradient masks with configurable feather distance (15-20px)
- **drawOverlayWithFeather()**: Applies masks to overlay alpha channels using `lighten` composite mode
- **ROI Configuration**: Precise regions of interest for eyes (175×135, 75×85px) and mouth (240×370, 160×100px)

### Animation Functions
- **Initiate**: Lights up robot eyes with cyan glow and feathered blending
- **Blink**: Eye closing/opening animation with smooth transitions
- **Talk**: Mouth animation running for 2 complete cycles
- **Head Turn**: 3D rotation effect using CSS transforms

## Quick Start

1. Clone the repository
2. Serve the files using any HTTP server (e.g., `python3 -m http.server 8080`)
3. Open `http://localhost:8080/index.html` in your browser
4. Click "Initiate" to start the robot
5. Use control buttons to trigger animations

## File Structure

```
amara_os/
├── index.html          # Single view HTML structure
├── style.css           # Unified dark gradient styling
├── main.js             # Animation controller with feathered masking
└── public/             # Robot image assets
    ├── robot_base.png
    ├── eyes_lit.png
    ├── eyes_blink.png
    ├── mouth_talk.png
    └── head_turn.png
```

## Requirements Met

✅ No black rectangles over eyes/mouth  
✅ Smooth feathered edges on all overlays  
✅ All animations work seamlessly (blink, talk, head turn, lit)  
✅ Unified dark gradient background (no two-tone boxes)  
✅ Single centered robot view only (no split view)  
✅ 4 control buttons clearly visible  
✅ Base robot image visible on default load  
✅ No "Split View" text or unused code anywhere  
✅ Responsive design works on all screen sizes
