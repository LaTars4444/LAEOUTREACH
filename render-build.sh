#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install Node dependencies and Build React Frontend
echo "🚀 Building React Frontend..."
npm install
npm run build

# Verify build output
echo "📂 Listing dist folder contents:"
ls -la dist

# 2. Install Python dependencies
echo "🐍 Installing Python Dependencies..."
pip install -r requirements.txt

echo "✅ Build Complete."
