# AJCC TNM Cookie Sync Browser Extension

This Chrome extension automatically syncs your AJCC authentication cookies with the local RadInsights app, enabling seamless data extraction.

## Installation

### Step 1: Load the Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select this `browser_extension` folder
5. The extension will appear with a blue "A" icon

### Step 2: Grant Permissions

When prompted, allow the extension to:
- Access cookies for `ajccstaging.org` and `login.facs.org`
- Send data to `localhost:5000` (your local Flask app)

## Usage

### Automatic Mode (Recommended)

1. Make sure your Flask app is running (`flask run`)
2. Click the extension icon to see the current status
3. Click **Open AJCC Login** to log in to AJCC in a new tab
4. Log in with your credentials
5. The extension automatically captures and syncs cookies
6. You'll see a green checkmark when authenticated

### Manual Sync

If cookies don't sync automatically:
1. Click the extension icon
2. Click **Sync Cookies Now**

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  1. You log in to AJCC in your browser                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Extension detects cookie changes on AJCC domains        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Extension sends cookies to Flask app at localhost:5000  │
│     POST /api/admin/tnm/extension-cookies                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Flask app stores cookies for TNM data extraction        │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Extension shows "Not Authenticated"
- Make sure you're logged into AJCC in your browser
- Click "Sync Cookies Now" to force a sync
- Check that your Flask app is running on port 5000

### Cookies not syncing
- Open Chrome DevTools (F12) → Console to see extension logs
- Make sure the Flask app is accessible at `http://localhost:5000`
- Try logging out and back in to AJCC

### Error connecting to local app
- Verify Flask is running: `flask run`
- Check the Flask console for errors
- Make sure no firewall is blocking localhost connections

## Security Notes

- Cookies are only synced to `localhost:5000` (your local machine)
- The extension only captures cookies from AJCC/FACS domains
- No data is sent to external servers

## Files

- `manifest.json` - Extension configuration
- `background.js` - Cookie monitoring and sync logic
- `popup.html` - Extension popup UI
- `popup.js` - Popup interaction logic
- `icons/` - Extension icons
