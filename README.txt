Wayne Tech Lab - Lab Core Access Retrieval System (WTl-S-LCARS)
================================================================

A Star Trek LCARS-style interface for the Wayne Tech Lab workspace.

Features:
- System monitoring (CPU, RAM, temp, uptime)
- Pironman 5 case controls
- Project management
- Minecraft server control
- App launcher (KiCad, Bambu Studio, etc.)

Setup:
1. Install Python dependencies:
   pip3 install -r requirements.txt

2. Configure environment variables (optional):
   export MC_SERVER_DIR=/opt/minecraft
   export KICAD_PATH=/usr/bin/kicad

3. Run the backend server:
   cd backend
   python3 app.py

   Or set PORT environment variable:
   PORT=8080 python3 app.py

4. Access the web interface:
   http://localhost:5000 (or your configured port)

Deployment:
- Copy the entire project folder to your nginx document root
- Configure nginx to proxy /api/* requests to the Flask backend
- Or run Flask directly and serve static files from nginx

Notes:
- Some features require sudo permissions (reboot, shutdown)
- Pironman 5 controls need SDK integration
- Adjust paths in backend/api/*.py files based on your system
