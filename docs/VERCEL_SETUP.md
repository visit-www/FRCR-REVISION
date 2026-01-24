# Vercel Environment Variables Setup

## Required Environment Variables

### 1. DATABASE_URL (Neon PostgreSQL)
- **Purpose**: PostgreSQL connection string for production database
- **Required for**: Database connectivity
- **Format**: `postgresql://user:password@ep-xxx.region.aws.neon.tech/database?sslmode=require`
- **Where to get**: [Neon Console](https://console.neon.tech/) → Your Project → Connection Details

### 2. CLAUDE_API_KEY
- **Purpose**: API key for Claude (Anthropic) AI integration
- **Required for**: AI preliminary case data generation
- **Format**: Starts with `sk-ant-...`
- **Where to get**: [Anthropic Console](https://console.anthropic.com/)

### 3. SECRET_KEY
- **Purpose**: Flask session encryption key
- **Required for**: Secure sessions, CSRF protection
- **Format**: Strong random string (e.g., generated with `secrets.token_hex(32)`)

## How to Add in Vercel Dashboard

1. Go to https://vercel.com/dashboard
2. Select your project: `frcr-revision`
3. Navigate to **Settings** → **Environment Variables**
4. Add the following variables:

| Key | Value | Environment |
|-----|-------|-------------|
| `DATABASE_URL` | `postgresql://...@neon.tech/...` | Production |
| `CLAUDE_API_KEY` | `sk-ant-...` | Production |
| `SECRET_KEY` | (random 64-char string) | Production |

5. Click **Save** for each
6. **Important**: Redeploy your application for changes to take effect

## Neon Database Setup

1. Go to [Neon Console](https://console.neon.tech/)
2. Create a new project (or use existing)
3. Copy the connection string from **Connection Details**
4. Use the **Direct connection** string (not pooled) for migrations
5. Add to Vercel as `DATABASE_URL`

### Connection String Format
```
postgresql://username:password@ep-example-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
```

## How to Add via Vercel CLI

```bash
# Link project (if not already linked)
vercel link

# Add environment variables for production
vercel env add DATABASE_URL production
vercel env add CLAUDE_API_KEY production
vercel env add SECRET_KEY production

# Verify they were added
vercel env ls

# Redeploy to apply changes
vercel --prod
```

## Database Migration

After setting up Neon, run migrations:

```bash
# Set DATABASE_URL locally for migration
export DATABASE_URL="postgresql://...@neon.tech/..."

# Run migrations
flask db upgrade
```

## Verification

After deployment:

1. Check Vercel deployment logs for database connection
2. Look for `[DB] Using PostgreSQL:` message
3. Test login and case viewing
4. If you see connection errors, verify the Neon connection string

## Security Notes

- ✅ Environment variables in Vercel are encrypted at rest
- ✅ They are only accessible at runtime (not in build logs)
- ✅ Never commit `.env` files or API keys to git
- ✅ Use Neon's connection pooling for high-traffic deployments
- ✅ Neon supports automatic scaling and branching for development
