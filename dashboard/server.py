#!/usr/bin/env python3
"""
Simple HTTP server for DevBots Dashboard
Serves static files and provides CORS support for local development
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Default port
PORT = 8080

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler with CORS support and report file serving"""

    def translate_path(self, path):
        # Strip query string and fragment before matching
        path = path.split('?', 1)[0].split('#', 1)[0]

        # Serve /reports/... from the repo root data/ directory
        if path.startswith('/reports/'):
            # /reports/project/bot/file.md -> DATA_DIR/project/reports/bot/file.md
            parts = path[len('/reports/'):].split('/', 2)
            if len(parts) == 3:
                project, bot, filename = parts
                return str(DATA_DIR / project / "reports" / bot / filename)
        return super().translate_path(path)

    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Custom logging format
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

def run_server(port=PORT):
    """Start the dashboard server"""
    dashboard_dir = Path(__file__).parent
    os.chdir(dashboard_dir)
    
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print("=" * 60)
        print("🤖 DevBots Dashboard Server")
        print("=" * 60)
        print(f"📊 Server running at http://localhost:{port}")
        print(f"📁 Serving from: {dashboard_dir}")
        print()
        print("📝 Available pages:")
        print(f"   • Main Dashboard: http://localhost:{port}/")
        print(f"   • Projects:       http://localhost:{port}/projects.html")
        print(f"   • Bots:           http://localhost:{port}/bots.html")
        print(f"   • Activity:       http://localhost:{port}/activity.html")
        print(f"   • Reports:        http://localhost:{port}/reports.html")
        print()
        print("Press Ctrl+C to stop the server")
        print("=" * 60)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped. Goodbye!")

if __name__ == "__main__":
    # Get port from command line argument if provided
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(port)
