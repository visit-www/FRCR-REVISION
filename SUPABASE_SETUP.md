# Supabase + Vercel Setup Guide

## Understanding the Environment Variables

When you connect Supabase to Vercel, Supabase automatically creates many environment variables. However, your Flask app needs a specific one that might not be auto-created.

### Variables Created by Supabase Integration

These are automatically created when you connect Supabase:
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Public API key (for frontend)
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` - Public publishable key
- `SUPABASE_SERVICE_ROLE_KEY` - Admin/service role key
- `SUPABASE_SECRET_KEY` - JWT secret key
- `SUPABASE_ANON_KEY` - Anonymous key
- `POSTGRES_HOST` - Database hostname
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DATABASE` - Database name

### What Your Flask App Needs

Your `app.py` looks for (in priority order):
1. `DATABASE_POSTGRES_URL_NON_POOLING` ⭐ **REQUIRED**
2. `DATABASE_URL` (fallback)
3. `DATABASE_POSTGRES_URL` (fallback)

## Solution: Add Connection String Manually

Since Supabase integration might not create `DATABASE_POSTGRES_URL_NON_POOLING`, you need to add it manually.

### Step 1: Get Connection String from Supabase

1. Go to your Supabase project dashboard
2. Click **Settings** → **Database**
3. Scroll to **Connection string**
4. Select **URI** tab
5. Select **Direct connection** (not Session mode)
6. Copy the connection string

It should look like:
```
postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

**Important**: Use the **Direct connection** string, not the pooled connection.

### Step 2: Add to Vercel Environment Variables

1. Go to Vercel Dashboard → Your Project → **Settings** → **Environment Variables**
2. Click **Add New**
3. Add:
   - **Key**: `DATABASE_POSTGRES_URL_NON_POOLING`
   - **Value**: [paste the connection string from Step 1]
   - **Environment**: Select **Production**, **Preview**, and **Development** (or just Production)
4. Click **Save**

### Step 3: Verify

After adding, you should have:
- ✅ `DATABASE_POSTGRES_URL_NON_POOLING` (manually added)
- ✅ `SECRET_KEY` (you added earlier)
- ✅ `PYTHON_VERSION` (you added earlier)
- ✅ All the Supabase auto-created variables (can leave them, they won't hurt)

### Alternative: Build Connection String from Existing Variables

If you want to use the existing Supabase variables, you can build the connection string:

```
postgresql://postgres:[POSTGRES_PASSWORD]@[POSTGRES_HOST]:5432/[POSTGRES_DATABASE]
```

But you'll need to:
1. Get the actual values (they're hidden in Vercel)
2. Replace the placeholders
3. Make sure to use port 5432 (direct connection) not 6543 (pooled)

**Note**: This is more complex and error-prone. Better to get the connection string directly from Supabase.

## About the "Already Connected" Message

If Vercel says "project is already connected to db via env variables", it means:
- Supabase integration detected existing database variables
- You can't use the "Connect Database" button again
- **Solution**: Just manually add `DATABASE_POSTGRES_URL_NON_POOLING` as described above

## Cleanup (Optional)

The Supabase integration created many variables you don't need for Flask:
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Only needed for Next.js/Supabase client
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` - Only needed for frontend
- `SUPABASE_SERVICE_ROLE_KEY` - Only needed for Supabase admin operations
- `SUPABASE_SECRET_KEY` - Only needed for Supabase JWT
- `SUPABASE_ANON_KEY` - Only needed for Supabase client

**You can safely leave them** - they won't interfere with your Flask app. Or delete them if you want a cleaner environment.

## Verification

After deployment, check Vercel logs to verify:
1. App starts without errors
2. Database connection works
3. No "SECRET_KEY not set" errors
4. No "Database connection failed" errors

## Troubleshooting

### "Database connection failed"
- Verify `DATABASE_POSTGRES_URL_NON_POOLING` is set correctly
- Check connection string uses `postgresql://` not `postgres://`
- Ensure it's the "Direct connection" string, not pooled

### "SECRET_KEY not set"
- Make sure `SECRET_KEY` environment variable is set
- Redeploy after adding environment variables

### Too many variables
- You can ignore the Supabase client variables
- Only `DATABASE_POSTGRES_URL_NON_POOLING` is critical for Flask
