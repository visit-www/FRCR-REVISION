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

### Keeping the Vercel/Neon DB in sync with model enums

When you add or change enum values in `models.py` (e.g. `BodyPart`, `FRCRModule`), the database type must be updated too:

1. **Create a migration** for the enum change, e.g.:
   ```bash
   flask db revision -m "add_bodypart_enum_values"
   ```
   Then edit the new file in `migrations/versions/` to run the appropriate `ALTER TYPE ... ADD VALUE` (or use the existing `add_bodypart_5new` migration if you added the five new body parts).

2. **Run it against your Neon DB** before or right after deploying:
   ```bash
   export DATABASE_URL="postgresql://...@neon.tech/..."   # or use POSTGRES_URL_NON_POOLING
   flask db upgrade
   ```

3. **Optional: run migrations on deploy**  
   If you run the app on Vercel serverless (e.g. via `api/index.py`), run `flask db upgrade` from a build step or a one-off job after deploy so the production DB schema (including new enum values) stays in sync. Otherwise run it manually whenever you add migrations.

Until the migration is applied, new enum values exist in Python but not in PostgreSQL, so inserts/updates using those values can fail and dropdowns driven from the DB may omit them.

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
