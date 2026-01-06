# Setup & Installation Guide

Complete step-by-step guide to set up and run FRCR Examiner Tool locally or on a server.

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Production Setup](#production-setup)
3. [Database Configuration](#database-configuration)
4. [Environment Variables](#environment-variables)
5. [Troubleshooting](#troubleshooting)

---

## Local Development Setup

### System Requirements

- **Operating System**: Windows, macOS, or Linux
- **Python**: Version 3.7 or higher
- **Memory**: Minimum 2GB RAM
- **Disk Space**: At least 1GB free

### Step 1: Install Python

#### On Windows
1. Download from https://www.python.org/downloads/
2. Run installer
3. ✅ Check "Add Python to PATH"
4. Click Install

#### On macOS
```bash
# Using Homebrew (recommended)
brew install python@3.9
```

#### On Linux
```bash
# Ubuntu/Debian
sudo apt-get install python3 python3-pip python3-venv

# Fedora
sudo dnf install python3 python3-pip
```

### Step 2: Clone Repository

```bash
# Using Git
git clone https://github.com/visit-www/Frcr-examiner.git
cd Frcr-examiner
```

Or download as ZIP from GitHub and extract.

### Step 3: Create Virtual Environment

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal.

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- Flask (web framework)
- SQLAlchemy (database ORM)
- psycopg2 (PostgreSQL driver)
- And other required packages

### Step 5: Set Environment Variables

**On Windows (Command Prompt):**
```bash
set FLASK_ENV=development
set FLASK_APP=app.py
```

**On Windows (PowerShell):**
```powershell
$env:FLASK_ENV="development"
$env:FLASK_APP="app.py"
```

**On macOS/Linux:**
```bash
export FLASK_ENV=development
export FLASK_APP=app.py
```

### Step 6: Run the Application

```bash
flask run
```

Output should show:
```
 * Running on http://127.0.0.1:5000
```

### Step 7: Access the Application

Open your browser and go to: **http://localhost:5000**

🎉 You're done! The app is running.

### Step 8: Deactivate Virtual Environment

When finished, deactivate the environment:
```bash
deactivate
```

---

## Production Setup

### Server Requirements

- **Operating System**: Linux (Ubuntu 18.04+ or similar)
- **Python**: 3.7 or higher
- **PostgreSQL**: 10 or higher
- **Memory**: Minimum 2GB RAM
- **Disk Space**: At least 5GB free
- **SSL Certificate**: For HTTPS

### Deployment on Railway

Railway is recommended for easy deployment.

1. **Create Railway Account**
   - Go to https://railway.app
   - Sign up with GitHub account

2. **Connect Repository**
   - Link your GitHub repo
   - Select main branch

3. **Configure Environment**
   - Add `DATABASE_URL`: Your PostgreSQL connection string
   - Add `FLASK_ENV`: Set to `production`
   - Add `SECRET_KEY`: Generate a strong random string

4. **Deploy**
   - Railway automatically deploys on each push
   - Your app will be live with a unique URL

### Manual Server Setup

#### 1. SSH into Server
```bash
ssh user@your-server-ip
```

#### 2. Install System Dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv postgresql postgresql-contrib nginx

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### 3. Create Application User
```bash
sudo useradd -m frcr-app
sudo su frcr-app
cd ~
```

#### 4. Clone Repository
```bash
git clone https://github.com/visit-www/Frcr-examiner.git
cd Frcr-examiner
```

#### 5. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 6. Create PostgreSQL Database
```bash
# As root or sudo
sudo -u postgres psql

# In PostgreSQL shell
CREATE DATABASE frcr_examiner;
CREATE USER frcr_user WITH PASSWORD 'strong-password-here';
ALTER ROLE frcr_user SET client_encoding TO 'utf8';
ALTER ROLE frcr_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE frcr_user SET default_transaction_deferrable TO on;
ALTER ROLE frcr_user SET default_transaction_read_uncommitted TO off;
GRANT ALL PRIVILEGES ON DATABASE frcr_examiner TO frcr_user;
\q
```

#### 7. Configure Environment Variables
```bash
# In /home/frcr-app/Frcr-examiner/.env
cat > .env << EOF
FLASK_ENV=production
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
DATABASE_URL=postgresql://frcr_user:strong-password-here@localhost:5432/frcr_examiner
EOF
```

#### 8. Setup Gunicorn Service
```bash
# Install Gunicorn
pip install gunicorn

# Create service file
sudo cat > /etc/systemd/system/frcr-examiner.service << EOF
[Unit]
Description=FRCR Examiner Application
After=network.target

[Service]
User=frcr-app
WorkingDirectory=/home/frcr-app/Frcr-examiner
Environment="PATH=/home/frcr-app/Frcr-examiner/venv/bin"
ExecStart=/home/frcr-app/Frcr-examiner/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:8000 app:app

[Install]
WantedBy=multi-user.target
EOF

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable frcr-examiner
sudo systemctl start frcr-examiner
```

#### 9. Setup Nginx Reverse Proxy
```bash
# Create config
sudo cat > /etc/nginx/sites-available/frcr-examiner << EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/frcr-examiner /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 10. Setup SSL Certificate (Let's Encrypt)
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Database Configuration

### SQLite (Development - Default)

Automatically configured. Database file created at:
```
instance/frcr_examiner.db
```

### PostgreSQL (Production)

#### Connection String Format
```
postgresql://username:password@hostname:port/database_name
```

Example:
```
postgresql://frcr_user:mypassword@localhost:5432/frcr_examiner
```

#### Environment Variable
```bash
export DATABASE_URL="postgresql://frcr_user:mypassword@localhost:5432/frcr_examiner"
```

#### Connection Pooling
For production with multiple workers, configure in `app.py`:
```python
engine = create_engine(
    os.environ.get('DATABASE_URL'),
    pool_size=10,
    pool_recycle=3600,
    pool_pre_ping=True
)
```

---

## Environment Variables

### Development Variables
```bash
FLASK_ENV=development
FLASK_APP=app.py
FLASK_DEBUG=1
DATABASE_URL=sqlite:///./instance/frcr_examiner.db
```

### Production Variables
```bash
FLASK_ENV=production
FLASK_APP=app.py
SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql://user:pass@host:5432/db
BACKUP_ENABLED=1
BACKUP_INTERVAL=86400  # 24 hours in seconds
```

### Generate Strong Secret Key
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Database Backup

### Automatic Backups
The application creates automatic backups every 24 hours:
- Located in `backups/` directory
- Keep last 5 backups
- Database file format: `frcr_examiner_backup_YYYYMMDD_HHMMSS.db`

### Manual Backup (SQLite)
```bash
cp instance/frcr_examiner.db backups/manual_backup_$(date +%Y%m%d_%H%M%S).db
```

### Manual Backup (PostgreSQL)
```bash
pg_dump -U frcr_user -h localhost frcr_examiner > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore from Backup
```bash
psql -U frcr_user -h localhost frcr_examiner < backup_YYYYMMDD_HHMMSS.sql
```

---

## Troubleshooting

### Port Already in Use
```bash
# Change port
flask run --port 5001

# Or kill process using port 5000
# On macOS/Linux
lsof -ti:5000 | xargs kill -9

# On Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### Python Not Found
```bash
# Verify Python installation
python3 --version

# Use full path if needed
/usr/bin/python3 -m venv venv
```

### Module Not Found
```bash
# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Database Connection Failed
```bash
# Check database is running
sudo systemctl status postgresql

# Check connection string
echo $DATABASE_URL

# Test connection
psql -c "SELECT 1"
```

### Permission Denied (Files)
```bash
# Fix file permissions
chmod 755 backups/
chmod 644 instance/frcr_examiner.db

# Fix directory ownership
sudo chown -R frcr-app:frcr-app /home/frcr-app/Frcr-examiner
```

### Out of Memory
- Increase server RAM
- Reduce worker count in Gunicorn
- Enable caching for static files

---

## Next Steps

1. Read [HOW_TO_USE.md](HOW_TO_USE.md) for user guide
2. Read [README.md](README.md) for technical details
3. Check [CONTRIBUTING.md](CONTRIBUTING.md) to contribute

## Support

Need help? Contact: lotusheart2016@gmail.com
