# Cloudflare R2 Setup for Case Image Stacks

## 1. Create R2 Bucket

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com) > **R2** > **Overview**
2. Click **Create bucket**
3. Name it (e.g. `frcr-case-images`)
4. Choose a region or leave default

## 2. Create API Token

1. R2 > **Manage R2 API Tokens**
2. **Create API token**
3. Permissions: **Object Read & Write**
4. Copy **Access Key ID** and **Secret Access Key**
5. Note your **Account ID** (in the R2 URL or dashboard sidebar)

## 3. Configure CORS

In the bucket **Settings** > **CORS Policy**, add:

```json
[
  {
    "AllowedOrigins": [
      "https://your-app.vercel.app",
      "http://localhost:5000"
    ],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

(Use your actual app URL and localhost for dev.)

## 4. Environment Variables

Add to `.env` or Vercel environment:

```
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=frcr-case-images
```

## 5. Run Migration

```bash
vercel env pull .env.vercel --environment=production
python scripts/utilities/run_sql_migration_vercel_only.py migrations/add_case_image_stack_r2_columns.sql
```

## 6. Install boto3

```bash
pip install boto3
```

(boto3 is in `requirements.txt` for the project)
