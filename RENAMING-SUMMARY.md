# WTl-S-LCARS Renaming Summary

This document summarizes the renaming from **WTL-PM** / **WTs-PM** to **WTl-S-LCARS** (Lab Core Access Retrieval System).

## New Naming Convention

Following the **WTl-Naming-Specification.md**:
- **WTl** = Wayne Tech lab (root namespace)
- **S** = System category
- **LCARS** = Lab Core Access Retrieval System

## Files Renamed

1. `wtl-pm-backend.service` → `wtl-s-lcars-backend.service`
2. `wtl-pm-nginx.conf` → `wtl-s-lcars-nginx.conf`

## Files Updated

All references updated in:
- `index.html` - Titles, banners, footer
- `scripts/index_scripts.js` - localStorage keys (`wtl-s-lcars-*`)
- `backend/app.py` - Docstring
- `README.txt` - Full documentation
- `deploy.sh` - Paths and references
- `backend/start.sh` - Comments
- `nginx-example.conf` - Comments and paths
- `css/classic.css` - Style comments
- `backend/api/printer.py` - Client ID

## Deployment Paths

- Old: `/var/www/html/wtl-pm/`
- New: `/var/www/html/wtl-s-lcars/`

## Service Names

- Old: `wtl-pm-backend.service`
- New: `wtl-s-lcars-backend.service`

## localStorage Keys

- Old: `wtl-pm-profile`, `wtl-pm-volume`, `wtl-pm-standby-timeout`
- New: `wtl-s-lcars-profile`, `wtl-s-lcars-volume`, `wtl-s-lcars-standby-timeout`

## Next Steps After Folder Rename

1. Update systemd service (if installed):
   ```bash
   sudo systemctl stop wtl-pm-backend  # if old service exists
   sudo systemctl disable wtl-pm-backend
   sudo cp wtl-s-lcars-backend.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable wtl-s-lcars-backend
   sudo systemctl start wtl-s-lcars-backend
   ```

2. Update nginx config (if using):
   ```bash
   sudo cp wtl-s-lcars-nginx.conf /etc/nginx/sites-available/wtl-s-lcars
   sudo ln -sf /etc/nginx/sites-available/wtl-s-lcars /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

3. Update deployment paths in scripts if needed

## Conversation Context

This renaming was done as part of establishing the WTl naming convention to avoid confusion between:
- WTl (Wayne Tech lab - the workspace)
- WTL-PM (old name that didn't follow the convention)
- WTl-S-LCARS (new name following WTl-<Category>-<Name> format)

The system is a workspace management interface that provides:
- Project management
- System monitoring
- Server control (Minecraft)
- App launcher
- Pironman 5 case controls
