#!/bin/bash
# Quick Start Guide for Diagrams-as-Code Pipeline

echo "🚀 Diagrams-as-Code Pipeline - Quick Start"
echo "=========================================="
echo ""

# Check Python
if command -v python3 &> /dev/null; then
    echo "✓ Python3 found: $(python3 --version)"
else
    echo "✗ Python3 not found. Please install Python 3.x"
    exit 1
fi

# Check mmdc
if command -v mmdc &> /dev/null; then
    echo "✓ mmdc found: $(mmdc --version)"
else
    echo "✗ mmdc not found. Install with: npm install -g @mermaid-js/mermaid-cli"
    exit 1
fi

# Check watchdog
if python3 -c "import watchdog" 2>/dev/null; then
    echo "✓ watchdog installed"
else
    echo "⚠ watchdog not installed (optional, for --watch mode)"
    echo "  Install with: pip install watchdog"
fi

echo ""
echo "📚 Examples:"
echo "------------"
echo ""
echo "1. Basic compilation (files in mmd_files/):"
echo "   python3 compiler.py input.mmd"
echo ""
echo "2. Custom output and high resolution:"
echo "   python3 compiler.py input.mmd -o my_diagram.png --scale 5"
echo ""
echo "3. Watch mode (auto-recompile on changes):"
echo "   python3 compiler.py input.mmd --watch"
echo ""
echo "4. Test with simple example:"
echo "   python3 compiler.py simple_example.mmd"
echo ""
echo "📂 Note: .mmd files go in mmd_files/ and .png outputs save there too"
echo "📖 See README.md for full documentation"
