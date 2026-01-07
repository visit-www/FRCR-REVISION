# How to Migrate Your Local Database to Vercel

## Step 1: Create Vercel Postgres Database

Go to [vercel.com](https://vercel.com) → Select "frcr-examiner" project → Storage tab → Click "Create Database"

Or use the Vercel CLI:
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
vercel postgres create
```

## Step 2: Copy the DATABASE_URL

After creating the database:
1. Go to Vercel Dashboard
2. Select project "frcr-examiner"
3. Go to Settings → Environment Variables
4. Copy the `DATABASE_URL` value

## Step 3: Set Environment Variable Locally

```bash
# Create or update .env file
echo "DATABASE_URL=<paste-your-database-url-here>" >> .env

# Example (your actual URL will be different):
# DATABASE_URL=postgresql://user:password@host:5432/dbname
```

## Step 4: Run Migration Script

```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# Install required package if needed
pip install psycopg2-binary

# Run the migration
python migrate_to_vercel.py
```

Expected output:
```
🔄 Starting SQLite → PostgreSQL migration...

📊 Extracting data from local SQLite database...
Found 8 tables:
  • exam_session: 2 records
  • packet: 8 records
  • case: 12 records
  ...

📤 Uploading to PostgreSQL...
  ✓ exam_session: 2 records
  ✓ packet: 8 records
  ...

✅ Migration complete: 50 total records transferred

🎉 Your Vercel app now has all your data!
```

## Step 5: Set Database URL in Vercel

```bash
# Set the environment variable in Vercel
vercel env add DATABASE_URL

# Paste your DATABASE_URL when prompted
```

## Step 6: Redeploy

```bash
# Redeploy your app to use the new database
git add .
git commit -m "Add database migration script"
git push
vercel --prod
```

## Verification

Test that your data is now in production:
```bash
# Should return your exam sessions from the database
curl https://frcr-examiner.vercel.app/api/exam/sessions
```

## What Happens After Migration

- **Local app**: Still uses SQLite (unchanged)
- **Vercel app**: Uses PostgreSQL with persistent data
- **Data persistence**: Your data will no longer reset every 24 hours
- **Both apps work**: You can run locally and deploy separately

## Troubleshooting

### Error: "DATABASE_URL environment variable not set"
- Make sure you added it to `.env` file
- Check: `cat .env`

### Error: "could not connect to server"
- Copy the DATABASE_URL exactly (with all special characters)
- Make sure it starts with `postgresql://`
- Check that Vercel Postgres database is running

### Migration seems stuck
- Check for network issues
- Try running again: `python migrate_to_vercel.py`

### Data not showing in Vercel
- Verify DATABASE_URL is set: `vercel env list`
- Check logs: `vercel logs`
- Redeploy: `vercel --prod`

## Need Help?

Check [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) for more deployment details.
