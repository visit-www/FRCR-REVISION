# Creating a GitHub Release for FRCR Examiner Tool

## Quick Release Process

### Option 1: Using GitHub Actions (Automated)

1. **Push a version tag:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **The workflow automatically:**
   - Creates Windows and macOS packages
   - Generates checksums
   - Creates a GitHub release
   - Uploads all files

### Option 2: Manual Release

1. **Build packages locally:**
   ```bash
   cd dist
   ./build-release.sh
   ```
   Enter the version when prompted (e.g., 1.0.0)

2. **Create GitHub Release:**
   - Go to: https://github.com/visit-www/Frcr-examiner/releases/new
   - Click "Draft a new release"
   - Create a new tag: `v1.0.0`
   - Release title: `FRCR Examiner Tool v1.0.0`
   - Copy contents from `dist/RELEASE_NOTES.md` into description
   - Upload the ZIP files from `release-v1.0.0/` folder
   - Upload `checksums.txt`
   - Click "Publish release"

---

## Detailed Steps

### Before Creating Release

1. **Update version numbers:**
   - Check `dist/RELEASE_NOTES.md`
   - Update any version references

2. **Test the application:**
   - Run full test suite
   - Test on Windows and macOS
   - Verify all features work

3. **Update documentation:**
   - Review README.md
   - Update CHANGELOG.md
   - Check HOW_TO_USE.md

4. **Commit all changes:**
   ```bash
   git add .
   git commit -m "Prepare for v1.0.0 release"
   git push origin main
   ```

### Creating the Release

#### Using GitHub Actions (Recommended)

```bash
# Tag the release
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push the tag
git push origin v1.0.0

# GitHub Actions will automatically:
# - Build packages
# - Create release
# - Upload files
```

#### Manual Build and Release

```bash
# 1. Build packages
cd dist
./build-release.sh
# Enter version: 1.0.0

# 2. Packages created in release-v1.0.0/ folder

# 3. Go to GitHub
# https://github.com/visit-www/Frcr-examiner/releases/new

# 4. Fill in:
# - Tag: v1.0.0
# - Title: FRCR Examiner Tool v1.0.0
# - Description: Copy from dist/RELEASE_NOTES.md
# - Upload files from release-v1.0.0/

# 5. Publish release
```

### After Release

1. **Announce the release:**
   - Update README.md with download link
   - Share on relevant platforms
   - Notify users

2. **Monitor feedback:**
   - Check GitHub issues
   - Respond to questions
   - Note any bugs for next release

3. **Archive build artifacts:**
   - Keep a backup of release packages
   - Store in secure location

---

## Release Checklist

- [ ] All features tested
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] RELEASE_NOTES.md current
- [ ] Version numbers correct
- [ ] All changes committed
- [ ] Code pushed to main branch
- [ ] Tag created and pushed
- [ ] Release created on GitHub
- [ ] Files uploaded and verified
- [ ] Checksums verified
- [ ] Installation tested on Windows
- [ ] Installation tested on macOS
- [ ] Release announced

---

## Versioning

We follow Semantic Versioning (SemVer):

- **Major** (1.x.x): Breaking changes
- **Minor** (x.1.x): New features, backwards compatible
- **Patch** (x.x.1): Bug fixes, backwards compatible

Examples:
- `v1.0.0` - First production release
- `v1.1.0` - Added new feature
- `v1.1.1` - Fixed a bug
- `v2.0.0` - Major redesign

---

## Troubleshooting

### GitHub Actions fails

- Check workflow logs in Actions tab
- Verify GITHUB_TOKEN has proper permissions
- Ensure all files exist in repository

### Build script fails

- Check file paths
- Verify zip is installed
- Ensure all required files exist

### Upload fails

- File size limit is 2GB per file
- Check internet connection
- Try again or upload manually

---

## Contact

For questions about releases:
- **Email:** lotusheart2016@gmail.com
- **GitHub Issues:** https://github.com/visit-www/Frcr-examiner/issues
