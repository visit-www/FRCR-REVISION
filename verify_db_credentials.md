# How to Verify Credentials are Stored in Database

## Method 1: API Endpoint (Recommended for Production)

1. **Log in as admin** on your Vercel deployment
2. **Visit**: `https://frcr-revision.vercel.app/auth/debug/verify-db-users`
3. **You'll see**:
   - Total number of users
   - For each user:
     - Email, name, admin status
     - Whether password_hash exists
     - Length of password hash
     - Preview of first 20 characters of hash

**Example Response:**
```json
{
  "success": true,
  "total_users": 1,
  "users": [
    {
      "id": 1,
      "email": "user@example.com",
      "password_hash_exists": true,
      "password_hash_length": 102,
      "password_hash_preview": "pbkdf2:sha256:600000$...",
      "has_valid_password_hash": true
    }
  ]
}
```

## Method 2: Local Python Script

Run this script locally (connects to your database):

```bash
python check_users_in_db.py
```

This will show:
- ✅ All users in database
- ✅ Whether each user has a password hash
- ✅ Length of password hash (should be 100+ characters)
- ✅ Preview of hash (first 30 chars)

## Method 3: Direct SQL Query (If you have database access)

If you're using **Supabase** or have direct PostgreSQL access:

### Check Users Table:
```sql
SELECT 
    id,
    email,
    full_name,
    is_admin,
    created_at,
    CASE 
        WHEN password_hash IS NULL THEN '❌ MISSING'
        WHEN LENGTH(password_hash) < 50 THEN '⚠️ TOO SHORT'
        ELSE '✅ EXISTS'
    END as password_status,
    LENGTH(password_hash) as hash_length,
    LEFT(password_hash, 30) || '...' as hash_preview
FROM "user"
ORDER BY id;
```

### Count Users with Password Hashes:
```sql
SELECT 
    COUNT(*) as total_users,
    COUNT(password_hash) as users_with_hash,
    COUNT(*) - COUNT(password_hash) as users_missing_hash
FROM "user";
```

### Check Specific User:
```sql
SELECT 
    id,
    email,
    CASE 
        WHEN password_hash IS NULL THEN 'NO HASH'
        ELSE 'HASH EXISTS (' || LENGTH(password_hash) || ' chars)'
    END as password_info
FROM "user"
WHERE email = 'your-email@example.com';
```

## What to Look For:

✅ **Good Signs:**
- `password_hash_exists: true`
- `password_hash_length: 100+` (Werkzeug hashes are usually 100-120 characters)
- Hash starts with `pbkdf2:sha256:` (Werkzeug format)

❌ **Bad Signs:**
- `password_hash_exists: false`
- `password_hash_length: 0` or very short (< 50)
- No users in database at all

## Understanding Password Hashes

- **Password hashes are NOT the actual password** - they're one-way encrypted versions
- **Format**: `pbkdf2:sha256:600000$salt$hash` (example)
- **Length**: Usually 100-120 characters
- **Security**: Even if someone sees the hash, they can't get your password back

## If Users Are Missing:

1. Check Vercel logs during registration
2. Look for `[REGISTER] User committed to database` messages
3. Check for database connection errors
4. Verify `DATABASE_URL` environment variable is set correctly
