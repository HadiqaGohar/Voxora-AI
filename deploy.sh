#!/bin/bash

# Voxora AI - Edge TTS Backend Deployment
# Run this on the server (69.12.72.35)

echo "=== Voxora AI - Edge TTS Backend Setup ==="

# Install dependencies
echo "Installing edge-tts..."
pip3 install edge-tts flask flask-cors

# Create systemd service for the backend
echo "Creating systemd service..."
cat > /etc/systemd/system/voxora-tts.service << 'EOF'
[Unit]
Description=Voxora AI TTS Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/voxora-ai/backend
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable voxora-tts
systemctl start voxora-tts

echo "=== Backend started on port 5000 ==="
echo "Test: curl http://localhost:5000/api/voices"
echo ""
echo "=== Update nginx config to proxy /api/tts to port 5000 ==="
