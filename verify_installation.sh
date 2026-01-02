#!/bin/bash

# FRCR Examiner - Installation Verification Script

echo "=========================================="
echo "FRCR EXAMINER - Verification Checklist"
echo "=========================================="
echo ""

PROJECT_DIR="/Users/zen/myRepos/projects/FRCR_EXAMINER"
ERRORS=0
WARNINGS=0

# Check directory
echo "✓ Checking project directory..."
if [ -d "$PROJECT_DIR" ]; then
    echo "  ✅ Project directory exists"
else
    echo "  ❌ Project directory not found"
    ERRORS=$((ERRORS + 1))
fi

# Check Python files
echo ""
echo "✓ Checking Python files..."
PYTHON_FILES=("app.py" "models.py" "load_sample_data.py")
for file in "${PYTHON_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        echo "  ✅ $file found"
    else
        echo "  ❌ $file missing"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check templates
echo ""
echo "✓ Checking templates..."
TEMPLATES=("base.html" "index.html" "start_exam.html" "view_packet.html" "view_case.html")
for file in "${TEMPLATES[@]}"; do
    if [ -f "$PROJECT_DIR/templates/$file" ]; then
        echo "  ✅ templates/$file found"
    else
        echo "  ❌ templates/$file missing"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check static files
echo ""
echo "✓ Checking static files..."
if [ -f "$PROJECT_DIR/static/style.css" ]; then
    echo "  ✅ static/style.css found"
else
    echo "  ❌ static/style.css missing"
    ERRORS=$((ERRORS + 1))
fi

# Check configuration files
echo ""
echo "✓ Checking configuration files..."
CONFIG_FILES=("requirements.txt" "run.sh" "README.md" "SETUP.md" "PROJECT_OVERVIEW.md" "QUICK_REFERENCE.md" ".gitignore")
for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        echo "  ✅ $file found"
    else
        echo "  ⚠️  $file missing"
        WARNINGS=$((WARNINGS + 1))
    fi
done

# Check instance directory
echo ""
echo "✓ Checking instance directory..."
if [ -d "$PROJECT_DIR/instance" ]; then
    echo "  ✅ instance/ directory exists"
else
    echo "  ❌ instance/ directory missing"
    ERRORS=$((ERRORS + 1))
fi

# Check Python installation
echo ""
echo "✓ Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "  ✅ Python 3 installed (version $PYTHON_VERSION)"
else
    echo "  ❌ Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi

# Check if pip is available
echo ""
echo "✓ Checking pip..."
if command -v pip3 &> /dev/null; then
    echo "  ✅ pip3 available"
else
    echo "  ⚠️  pip3 not found (may need to install)"
    WARNINGS=$((WARNINGS + 1))
fi

# File count summary
echo ""
echo "✓ File count summary..."
TOTAL_FILES=$(find "$PROJECT_DIR" -type f ! -path '*/\.*' | wc -l)
echo "  ✅ Total project files: $TOTAL_FILES"

# Summary
echo ""
echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ All checks passed! Ready to run."
    echo ""
    echo "Next steps:"
    echo "  1. cd $PROJECT_DIR"
    echo "  2. ./run.sh"
    echo "  3. Open http://localhost:5000 in browser"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  Warnings: $WARNINGS (non-critical)"
    echo "✅ Project is ready to run"
    exit 0
else
    echo "❌ Errors found: $ERRORS"
    echo "⚠️  Warnings: $WARNINGS"
    echo ""
    echo "Please fix the errors above before running the application."
    exit 1
fi
