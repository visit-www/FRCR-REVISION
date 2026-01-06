# GitHub Push and Release Guide

## Initial Setup (First Time)

If you haven't pushed to GitHub yet:

### 1. Create GitHub Repository

Already done: https://github.com/visit-www/Frcr-examiner

### 2. Initialize Git (if not already done)

```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
git init
```

### 3. Configure Git

```bash
git config user.name "visit-www"
git config user.email "your-email@example.com"
```

### 4. Connect to GitHub

```bash
git remote add origin https://github.com/visit-www/Frcr-examiner.git
```

Or if using SSH:
```bash
git remote add origin git@github.com:visit-www/Frcr-examiner.git
```

---

## Pushing to GitHub

### Step 1: Stage All Changes

```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# Add all files
git add .

# Or add specific files
git add app.py models.py templates/ static/ dist/
```

### Step 2: Commit Changes

```bash
git commit -m "Production ready: Add distribution packages and installers

- Added Windows installer with desktop shortcuts
- Added macOS installer with app bundle
- Created comprehensive installation guides
- Added GitHub release workflow
- Updated color scheme to soft, professional palette
- Prepared for v1.0.0 release"
```

### Step 3: Push to GitHub

```bash
# Push to main branch
git push -u origin main

# Or if your branch is named master
git push -u origin master
```

If you get an error about divergent branches:
```bash
git pull origin main --rebase
git push origin main
```

---

## Creating a Release

### Option 1: Automated via GitHub Actions

```bash
# 1. Ensure all changes are pushed
git push origin main

# 2. Create and push a version tag
git tag -a v1.0.0 -m "Release version 1.0.0 - Production ready"
git push origin v1.0.0

# 3. GitHub Actions will automatically:
#    - Build distribution packages
#    - Create GitHub release
#    - Upload packages
```

### Option 2: Manual Release

```bash
# 1. Build packages locally
cd dist
./build-release.sh
# Enter version: 1.0.0

# 2. Go to GitHub releases
# https://github.com/visit-www/Frcr-examiner/releases/new

# 3. Create release:
#    - Tag: v1.0.0
#    - Title: FRCR Examiner Tool v1.0.0
#    - Description: Copy from dist/RELEASE_NOTES.md
#    - Upload ZIP files from release-v1.0.0/
#    - Publish release
```

---

## Complete Push Workflow

Here's the complete command sequence to push everything:

```bash
# Navigate to project
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# Check status
git status

# Add all changes
git add .

# Commit with descriptive message
git commit -m "Production v1.0.0: Complete distribution package"

# Push to GitHub
git push origin main

# Create release tag
git tag -a v1.0.0 -m "Production release v1.0.0"

# Push tag (triggers automatic release)
git push origin v1.0.0
```

---

## Troubleshooting

### Authentication Issues

**HTTPS:**
```bash
# You may need a personal access token
# Generate at: https://github.com/settings/tokens
# Use token as password when prompted
```

**SSH:**
```bash
# Ensure SSH key is added to GitHub
# Test connection:
ssh -T git@github.com
```

### Push Rejected

```bash
# Pull latest changes first
git pull origin main --rebase

# Then push
git push origin main
```

### Large Files

If you have large files (>100MB):
```bash
# Use Git LFS
git lfs install
git lfs track "*.db"
git lfs track "*.zip"
```

Or add them to .gitignore:
```bash
echo "instance/*.db" >> .gitignore
echo "release-*/" >> .gitignore
```

### Reset if Needed

**Careful! This discards local changes:**
```bash
git reset --hard origin/main
```

---

## After Pushing

### 1. Verify on GitHub
- Check https://github.com/visit-www/Frcr-examiner
- Ensure all files are present
- Verify workflows are running (if using Actions)

### 2. Check Release
- Go to Releases tab
- Verify packages are uploaded
- Test download links

### 3. Update Repository Settings
- Add description: "FRCR Examiner Tool - Professional examination management for FRCR viva exams"
- Add topics: `frcr`, `examination`, `medical`, `radiology`, `flask`, `python`
- Enable issues
- Add README to profile

---

## Quick Reference

```bash
# Full workflow
git add .
git commit -m "Your message"
git push origin main

# Create release
git tag v1.0.0
git push origin v1.0.0

# Check status
git status
git log --oneline -5

# View remotes
git remote -v
```

---

## Next Steps After Push

1. ✅ Code pushed to GitHub
2. ✅ Release created
3. 📢 Announce release
4. 📝 Update documentation if needed
5. 🐛 Monitor issues
6. 🔄 Plan next version

---

## Need Help?

- GitHub Docs: https://docs.github.com
- Git Documentation: https://git-scm.com/doc
- Contact: lotusheart2016@gmail.com
