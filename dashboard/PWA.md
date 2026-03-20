# PWA Setup Guide

The DevBots Dashboard is now a Progressive Web App (PWA)!

## Features

- **Installable**: Can be installed on desktop and mobile devices
- **Offline Support**: Works offline with cached assets
- **App Icon**: Custom robot icon for home screen
- **Standalone Mode**: Runs like a native app

## Setup

### 1. Generate Icons

The dashboard needs PNG icons in multiple sizes. Run:

```bash
# Install cairosvg first (one-time setup)
uv pip install cairosvg

# Generate all icon sizes
uv run dashboard generate-icons
```

Or manually:

```bash
cd dashboard/icons
uv run python generate_icons.py
```

This will generate:
- icon-72x72.png
- icon-96x96.png
- icon-128x128.png
- icon-144x144.png
- icon-152x152.png
- icon-192x192.png
- icon-384x384.png
- icon-512x512.png

### 2. Start the Dashboard

```bash
uv run dashboard
```

### 3. Install the PWA

Once the server is running:

**On Desktop (Chrome/Edge):**
1. Open the dashboard in Chrome/Edge
2. Click the install icon in the address bar
3. Follow the prompts

**On Desktop (Firefox):**
1. Open the dashboard in Firefox
2. Click the install icon in the address bar
3. Follow the prompts

**On Mobile (Chrome/Android):**
1. Open the dashboard in Chrome
2. Tap "Add to Home Screen" from the menu
3. Follow the prompts

**On Mobile (iOS/Safari):**
1. Open the dashboard in Safari
2. Tap the Share button
3. Select "Add to Home Screen"
4. Follow the prompts

## Files Added

- `manifest.json` - PWA manifest with app metadata
- `service-worker.js` - Caching and offline support
- `icons/icon.svg` - SVG source for icons
- `icons/generate_icons.py` - Script to generate PNG icons
- `js/sw-register.js` - Service worker registration

## Browser Support

- ✅ Chrome/Edge (Desktop & Mobile)
- ✅ Firefox (Desktop & Mobile)
- ✅ Safari (Desktop & Mobile)
- ⚠️ iOS Safari has some limitations (no service workers in standalone mode)

## Production Deployment

For production, ensure:

1. **HTTPS** is enabled (required for service workers)
2. Icons are generated and present in `icons/` directory
3. The manifest.json is served with correct MIME type
4. The service-worker.js is served from the root

## Troubleshooting

**Icons not showing?**
- Make sure icons are generated: `uv run dashboard generate-icons`
- Check browser console for 404 errors

**Service worker not registering?**
- Open DevTools > Application > Service Workers
- Check for console errors

**PWA not installable?**
- Must be served over HTTPS (localhost is exempt)
- Check that all icons exist
- Ensure manifest.json is valid

**cairosvg not found?**
- Install with: `uv pip install cairosvg`

## Updating the PWA

To update the PWA:

1. Update version in `service-worker.js` (change `CACHE_NAME`)
2. Update assets as needed
3. Clear cache or wait for automatic update
