#!/bin/bash
# KnowledgeBot Environment Setup Script
# =====================================
# This script sets up a Python virtual environment for the KnowledgeBot project.
# It works on both macOS and Windows (via Git Bash or WSL).

set -e

echo "=========================================="
echo "KnowledgeBot Environment Setup"
echo "=========================================="
echo

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
    # Try to find Python 3.10+ on macOS
    if command -v /opt/homebrew/bin/python3.11 &> /dev/null; then
        PYTHON_CMD="/opt/homebrew/bin/python3.11"
    elif command -v /opt/homebrew/bin/python3.12 &> /dev/null; then
        PYTHON_CMD="/opt/homebrew/bin/python3.12"
    elif command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3.12 &> /dev/null; then
        PYTHON_CMD="python3.12"
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    else
        echo "Error: Python 3.10+ not found. Please install it:"
        echo "  brew install python@3.11"
        exit 1
    fi
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    PLATFORM="Windows"
    PYTHON_CMD="python"
else
    PLATFORM="Linux"
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3.12 &> /dev/null; then
        PYTHON_CMD="python3.12"
    else
        PYTHON_CMD="python3"
    fi
fi

echo "Platform: $PLATFORM"
echo "Python command: $PYTHON_CMD"

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PYTHON_VERSION"

MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [[ $MAJOR -lt 3 ]] || [[ $MAJOR -eq 3 && $MINOR -lt 10 ]]; then
    echo "Error: Python 3.10+ is required. Found: $PYTHON_VERSION"
    echo "Please install Python 3.10 or newer."
    exit 1
fi

echo

# Create virtual environment
if [ -d ".venv" ]; then
    echo "Existing .venv found. Removing..."
    rm -rf .venv
fi

echo "Creating virtual environment..."
$PYTHON_CMD -m venv .venv

# Activate virtual environment
if [[ "$PLATFORM" == "Windows" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

echo "Upgrading pip..."
pip install --upgrade pip

echo
echo "Installing requirements..."
pip install -r requirements.txt

# Check for ai_engine sibling directory
AI_ENGINE_PATH="../ai_engine"
if [ -d "$AI_ENGINE_PATH" ]; then
    echo
    echo "Found ai_engine at $AI_ENGINE_PATH"
    echo "Installing ai_core as editable package..."
    pip install -e "$AI_ENGINE_PATH"
else
    echo
    echo "Warning: ai_engine not found at $AI_ENGINE_PATH"
    echo "You'll need to install ai_core manually:"
    echo "  pip install -e /path/to/ai_engine"
fi

# Check for notion_md_converter sibling directory
NOTION_CONVERTER_PATH="../notion_md_converter"
if [ -d "$NOTION_CONVERTER_PATH" ]; then
    echo
    echo "Found notion_md_converter at $NOTION_CONVERTER_PATH"
    echo "Installing notion_markdown_converter as editable package..."
    pip install -e "$NOTION_CONVERTER_PATH"
else
    echo
    echo "Warning: notion_md_converter not found at $NOTION_CONVERTER_PATH"
    echo "You'll need to install notion_markdown_converter manually:"
    echo "  pip install -e /path/to/notion_md_converter"
fi

echo
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
echo "To activate the virtual environment:"
if [[ "$PLATFORM" == "Windows" ]]; then
    echo "  .venv\\Scripts\\activate"
else
    echo "  source .venv/bin/activate"
fi
echo
echo "Before running, make sure to:"
echo "1. Copy .env.example to .env (if exists) and fill in your API keys"
echo "2. Set the following environment variables (optional - paths are auto-detected):"
echo "   - KNOWLEDGEBOT_PATH: Path to KnowledgeBot data folder"
echo "   - OBSIDIAN_VAULT_PATH: Path to your Obsidian vault"
echo
echo "To run the services:"
echo "  python obsidian_ai.py    # File watcher + keyboard listener"
echo "  python kb_service.py     # Knowledge processing service"


