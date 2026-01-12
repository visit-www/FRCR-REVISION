# Database Sync Guide: Local SQLite → Production Supabase

This guide explains how to sync your local SQLite database with your production Supabase PostgreSQL database.

## Methods

### Method 1: Automated Script (Recommended)

Use the provided Python script to automatically export and import all data.

#### Step 1: Set Production Database URL

```bash
# Set the production database connection string
export DATABASE_POSTGRES_URL_NON_POOLING="postgresql://postgres:[password]@[host]:5432/postgres"

# Or use DATABASE_URL
export DATABASE_URL="postgresql://postgres:[password]@[host]:5432/postgres"
```

**Get the connection string from:**
- Supabase Dashboard → Settings → Database → Connection string (Direct connection)

#### Step 2: Run the Sync Script

```bash
python3 sync_local_to_production.py
```

The script will:
1. ✅ Export all data from local SQLite database
2. ✅ Connect to production Supabase database
3. ✅ Import all data (users, cases, Q&A, images, etc.)
4. ✅ Handle ID mapping for relationships
5. ✅ Skip duplicates (users with same email)

#### What Gets Synced

- ✅ **Users** - All user accounts (skips duplicates by email)
- ✅ **Cases** - All medical cases
- ✅ **Questions & Answers** - All Q&A pairs for each case
- ✅ **Images** - All case images with descriptions
- ✅ **Revision Sessions** - Student revision sessions
- ✅ **Case Flags** - Student case flags
- ✅ **Highlights** - Text highlights
- ✅ **Notes** - Student notes

### Method 2: Manual Export/Import

#### Step 1: Export from Local Database

1. Start your local Flask app
2. Log in as admin
3. Go to **Admin Dashboard** → **Backup Manager**
4. Click **Download Backup**
5. Save the JSON file

#### Step 2: Import to Production

1. Deploy your app to Vercel
2. Log in as admin on production
3. Go to **Admin Dashboard** → **Backup Manager**
4. Click **Upload Backup**
5. Select the JSON file from Step 1
6. Confirm overwrite

**⚠️ Warning**: This will **replace** all data in production database!

### Method 3: Using Supabase Dashboard

#### Step 1: Export from SQLite

```bash
# Export SQLite to SQL
sqlite3 instance/frcr_examiner.db .dump > local_dump.sql
```

#### Step 2: Convert SQL for PostgreSQL

SQLite SQL needs to be converted for PostgreSQL:
- Remove SQLite-specific syntax
- Convert data types
- Handle auto-increment IDs

**Note**: This method is complex and error-prone. Use Method 1 instead.

## Important Notes

### ID Mapping

When syncing, the script handles ID mapping:
- Old user IDs → New user IDs
- Old case IDs → New case IDs
- Relationships are preserved

### Duplicates

The script prevents duplicates:
- **Users**: Skips if email already exists
- **Case Flags**: Skips if user+case combination exists
- **Other data**: May create duplicates (review manually)

### Passwords

User passwords are synced as-is (hashed). Users can log in with the same passwords.

### Images

Case images are exported as binary data (hex-encoded) and imported back. Large images may take time.

## Troubleshooting

### "Production database URL not found"

Make sure you set the environment variable:
```bash
export DATABASE_POSTGRES_URL_NON_POOLING="[your-connection-string]"
```

### "Connection failed"

- Verify connection string is correct
- Check Supabase database is accessible
- Ensure connection string uses `postgresql://` not `postgres://`
- Remove query parameters like `?pgbouncer=true`

### "Foreign key constraint failed"

This means relationships are broken. The script should handle this, but if it fails:
- Check user_id_map and case_id_map are working
- Verify all referenced users/cases exist

### "Duplicate key error"

Some data already exists. The script skips users by email, but other data may duplicate. Review and clean up manually if needed.

## Best Practices

1. **Backup Production First**
   - Before syncing, backup production database
   - Use Supabase dashboard or backup feature

2. **Test on Staging**
   - If possible, test sync on a staging database first
   - Verify all data imports correctly

3. **Sync During Maintenance**
   - Sync when users are not actively using the app
   - Or sync to a new database and switch over

4. **Verify After Sync**
   - Check user counts match
   - Check case counts match
   - Test login with synced users
   - Verify cases display correctly

## One-Way vs Two-Way Sync

**Current Script**: One-way sync (Local → Production)

For two-way sync:
- Export from production
- Import to local
- Merge conflicts manually

**Recommendation**: Use production as source of truth. Sync local → production only.

## Alternative: Use Production Database Locally

Instead of syncing, you can connect your local app directly to Supabase:

```bash
# .env.local
DATABASE_POSTGRES_URL_NON_POOLING=postgresql://postgres:[password]@[host]:5432/postgres
```

Then run your local app - it will use the same database as production.

**⚠️ Warning**: This means local changes affect production! Use with caution.

## Questions?

- Check script output for detailed error messages
- Review Vercel logs for production issues
- Check Supabase logs for database errors
