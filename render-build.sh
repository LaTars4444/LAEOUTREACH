#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "🚀 Installing Node dependencies..."
npm install

echo "🚀 Building React Frontend..."
npm run build

echo "📂 Verifying build output..."
if [ -d "dist" ]; then
  echo "✅ 'dist' folder created successfully."
  ls -la dist
else
  echo "❌ ERROR: 'dist' folder NOT found!"
  ls -la
  exit 1
fi

echo "🐍 Installing Python Dependencies..."
pip install -r requirements.txt

echo "✅ Build Complete."
