# AJCC TNM Extraction Setup Instructions

## Required Environment Variables

The AJCC TNM extraction requires authentication credentials to access the AJCC website API.

### Step 1: Add Credentials to .env File

Add these lines to your `.env` file:

```bash
AJCC_USERNAME=your_ajcc_email@example.com
AJCC_PASSWORD=your_ajcc_password
```

**Note:** The credentials you provided earlier were:
- Username: `gaurav0133@gmail.com`
- Password: `AadiArhan!2023`

These have been added to your `.env` file automatically.

### Step 2: Restart Flask Server

**IMPORTANT:** After adding credentials, you MUST restart your Flask server for the environment variables to be loaded:

```bash
# Stop the current server (Ctrl+C)
# Then restart:
flask run
```

### Step 3: Test Authentication

Once the server is restarted, try extracting TNM data again from the admin panel.

## Troubleshooting

### Error: "AJCC credentials not configured"

- **Solution:** Make sure `.env` file exists and contains `AJCC_USERNAME` and `AJCC_PASSWORD`
- **Solution:** Restart Flask server after adding credentials

### Error: "Extraction failed - no data retrieved"

This can happen due to:

1. **Authentication failure:**
   - Check credentials are correct
   - AJCC website may require manual login first
   - Check if AJCC website structure has changed

2. **No data available:**
   - The disease/year combination may not exist
   - Try a different year (2026, 2025, 2024)
   - Try a different disease

3. **Network issues:**
   - Check internet connection
   - AJCC website may be temporarily unavailable

### Error: "No content found for [disease]/[year]"

- The AJCC API may not have data for that specific combination
- Try a different year
- Verify the disease slug is correct

## Manual Testing

You can test authentication manually:

```python
from ajcc_auth_service import authenticate_ajcc

success = authenticate_ajcc()
if success:
    print("✓ Authentication successful")
else:
    print("✗ Authentication failed")
```

## Next Steps

1. ✅ Credentials added to `.env`
2. ⏳ **Restart Flask server** (required!)
3. ⏳ Try extraction again
4. ⏳ Check server logs for detailed error messages
