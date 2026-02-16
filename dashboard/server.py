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

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler with CORS support and proper MIME types"""
    
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
