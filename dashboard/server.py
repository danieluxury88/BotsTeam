#!/usr/bin/env python3
"""
Simple HTTP server for DevBots Dashboard
Serves static files and provides CORS support for local development
"""

import http.server
import socketserver
import json
import os
import sys
from pathlib import Path

# Default port
PORT = 8080

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# Ensure dashboard directory is on sys.path so api module can be imported
DASHBOARD_DIR = Path(__file__).resolve().parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from api import list_projects, get_project, create_project, update_project, delete_project, generate_reports  # noqa: E402


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler with CORS support, report file serving, and project API"""

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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        path = self._clean_path()
        api = self._parse_api_path(path)
        if api is not None:
            self._handle_api_get(api)
        else:
            super().do_GET()

    def do_POST(self):
        path = self._clean_path()
        api = self._parse_api_path(path)
        if api is None:
            self._send_json({"error": "Not found"}, 404)
            return

        # POST /api/projects/{name}/reports — generate reports
        if '/' in api:
            name, action = api.split('/', 1)
            if action == 'reports' and name:
                body = self._read_json_body()
                if body is None:
                    return
                self._call_api(generate_reports, name, body)
                return
            self._send_json({"error": "Not found"}, 404)
            return

        # POST /api/projects — create project
        if api != "":
            self._send_json({"error": "Not found"}, 404)
            return
        body = self._read_json_body()
        if body is None:
            return
        self._call_api(create_project, body)

    def do_PUT(self):
        path = self._clean_path()
        api = self._parse_api_path(path)
        if api is None or api == "":
            self._send_json({"error": "Project name required in URL"}, 400)
            return
        body = self._read_json_body()
        if body is None:
            return
        self._call_api(update_project, api, body)

    def do_DELETE(self):
        path = self._clean_path()
        api = self._parse_api_path(path)
        if api is None or api == "":
            self._send_json({"error": "Project name required in URL"}, 400)
            return
        self._call_api(delete_project, api)

    # --- Helpers ---

    def _call_api(self, func, *args):
        """Call an API function with error handling to always return JSON."""
        try:
            result = func(*args)
            if isinstance(result, tuple):
                self._send_json(result[0], result[1])
            else:
                self._send_json(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": str(e)}, 500)

    def _clean_path(self):
        return self.path.split('?', 1)[0].split('#', 1)[0]

    def _parse_api_path(self, path):
        """Return project name if path matches /api/projects[/{name}], else None.
        Returns '' for /api/projects (collection), 'name' for /api/projects/name."""
        prefix = '/api/projects'
        if path == prefix:
            return ""
        if path.startswith(prefix + '/'):
            return path[len(prefix) + 1:]
        return None

    def _handle_api_get(self, api_name):
        try:
            if api_name == "":
                self._send_json(list_projects())
            else:
                result = get_project(api_name)
                if result is None:
                    self._send_json({"error": "Project not found"}, 404)
                else:
                    self._send_json(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": str(e)}, 500)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_json({"error": "Request body required"}, 400)
            return None
        try:
            raw = self.rfile.read(content_length)
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "Invalid JSON"}, 400)
            return None

    def log_message(self, format, *args):
        # Custom logging format
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

def run_server(port=PORT):
    """Start the dashboard server"""
    dashboard_dir = Path(__file__).parent
    os.chdir(dashboard_dir)

    socketserver.TCPServer.allow_reuse_address = True
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
