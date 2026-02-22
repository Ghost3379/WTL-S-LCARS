#!/bin/bash
# Deployment script for WTl-S-LCARS
# Copies project to www folder and sets up backend

# Default www folder (adjust if yours is different)
WWW_FOLDER="${1:-/var/www/html}"

echo "Deploying WTl-S-LCARS to $WWW_FOLDER..."

# Check if www folder exists
if [ ! -d "$WWW_FOLDER" ]; then
    echo "Error: $WWW_FOLDER does not exist!"
    echo "Usage: ./deploy.sh [www_folder_path]"
    exit 1
fi

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Create backup of existing deployment (if any)
if [ -d "$WWW_FOLDER/wtl-s-lcars" ]; then
    echo "Backing up existing deployment..."
    sudo cp -r "$WWW_FOLDER/wtl-s-lcars" "$WWW_FOLDER/wtl-s-lcars.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Copy entire project to www folder
echo "Copying files to $WWW_FOLDER/wtl-s-lcars..."
sudo mkdir -p "$WWW_FOLDER/wtl-s-lcars"
sudo cp -r "$PROJECT_DIR"/* "$WWW_FOLDER/wtl-s-lcars/"

# Set permissions
echo "Setting permissions..."
sudo chown -R www-data:www-data "$WWW_FOLDER/wtl-s-lcars" 2>/dev/null || sudo chown -R $USER:$USER "$WWW_FOLDER/wtl-s-lcars"
sudo chmod -R 755 "$WWW_FOLDER/wtl-s-lcars"

echo ""
echo "Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Install Python dependencies:"
echo "   cd $WWW_FOLDER/wtl-s-lcars/backend"
echo "   pip3 install -r ../requirements.txt"
echo ""
echo "2. Run the backend server:"
echo "   cd $WWW_FOLDER/wtl-s-lcars/backend"
echo "   python3 app.py"
echo ""
echo "3. Or configure nginx to proxy /api/* to Flask (port 5000)"
echo "   and serve static files from $WWW_FOLDER/wtl-s-lcars"
