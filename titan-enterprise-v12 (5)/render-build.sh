#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install Node dependencies and Build React Frontend
echo "🚀 Building React Frontend..."
npm install
npm run build

# 2. Install Python dependencies
echo "🐍 Installing Python Dependencies..."
pip install -r requirements.txt

echo "✅ Build Complete."