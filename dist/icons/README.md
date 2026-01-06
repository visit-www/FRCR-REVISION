# App Icon Files

This folder should contain the application icons:

## Required Files

### Windows
- `app_icon.ico` - Windows icon file (256x256 or higher)

### macOS
- `app_icon.icns` - macOS icon file
- `app_icon.png` - PNG version (1024x1024)

## Creating Icons

### From PNG to ICO (Windows)
You can use online tools like:
- https://convertio.co/png-ico/
- https://www.icoconverter.com/

Recommended sizes: 16x16, 32x32, 48x48, 256x256

### From PNG to ICNS (macOS)
Use `iconutil` on macOS:

```bash
# Create iconset folder
mkdir app_icon.iconset

# Add different sizes (you'll need to create these from your PNG)
# icon_16x16.png
# icon_32x32.png
# icon_128x128.png
# icon_256x256.png
# icon_512x512.png
# icon_1024x1024.png

# Convert to icns
iconutil -c icns app_icon.iconset
```

Or use online tools like:
- https://cloudconvert.com/png-to-icns
- https://anyconv.com/png-to-icns-converter/

## Icon Design Guidelines

### Style
- Medical theme (stethoscope, radiograph, etc.)
- Professional appearance
- Clear at small sizes
- High contrast

### Colors
- Use your app's color scheme
- Ensure readability on both light and dark backgrounds

### Suggested Design Elements
- Stethoscope icon
- Medical cross
- Radiograph/X-ray imagery
- FRCR initials
- Book/examination theme

## Current Status

**Note:** Currently using placeholder icons. For production release, create proper icons and place them in this folder with the names specified above.

## Tools for Icon Creation

- **Figma** - Free design tool
- **Canva** - Simple icon creator
- **GIMP** - Free image editor
- **Adobe Illustrator** - Professional design tool
- **Inkscape** - Free vector graphics editor
