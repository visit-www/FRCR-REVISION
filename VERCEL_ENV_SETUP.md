# Vercel Environment Variables Setup

## Required Environment Variables

### 1. CLAUDE_API_KEY
- **Purpose**: API key for Claude (Anthropic) AI integration
- **Required for**: AI preliminary case data generation
- **Format**: Starts with `sk-ant-...`
- **Where to get**: [Anthropic Console](https://console.anthropic.com/)

### 2. DATABASE_URL (or DATABASE_POSTGRES_URL_NON_POOLING)
- **Purpose**: PostgreSQL connection string for production database
- **Required for**: Database connectivity
- **Format**: `postgresql://user:password@host:port/database`

### 3. SECRET_KEY
- **Purpose**: Flask session encryption key
- **Required for**: Secure sessions, CSRF protection
- **Format**: Strong random string (e.g., generated with `secrets.token_hex(32)`)

## How to Add in Vercel Dashboard

1. Go to https://vercel.com/dashboard
2. Select your project: `frcr-revision`
3. Navigate to **Settings** → **Environment Variables**
4. Click **Add New**
5. Enter:
   - **Key**: `CLAUDE_API_KEY`
   - **Value**: `sk-ant-api03-...` (your actual key)
   - **Environment**: Select all (Production, Preview, Development) or just Production
6. Click **Save**
7. **Important**: Redeploy your application for changes to take effect

## How to Add via Vercel CLI

```bash
# Link project (if not already linked)
vercel link

# Add environment variable for production
vercel env add CLAUDE_API_KEY production
# (Enter your API key when prompted)

# Add for preview environment (optional)
vercel env add CLAUDE_API_KEY preview

# Add for development environment (optional)
vercel env add CLAUDE_API_KEY development

# Verify it was added
vercel env ls

# Redeploy to apply changes
vercel --prod
```

## Verification

After adding the environment variable:

1. Deploy a new version (or trigger redeploy)
2. Check Vercel deployment logs for errors
3. Test AI generation feature in the app
4. If you see "CLAUDE_API_KEY is not configured" error, the variable wasn't set correctly

## Security Notes

- ✅ Environment variables in Vercel are encrypted at rest
- ✅ They are only accessible at runtime (not in build logs)
- ✅ Never commit `.env` files or API keys to git
- ✅ Use different keys for development vs production if possible
