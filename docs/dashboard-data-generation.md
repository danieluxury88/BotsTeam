# 📁 Dashboard Data Generation Strategy

## Overview

This document describes how to generate the JSON data files that the dashboard consumes from the existing DevBots reports and project registry.

## Data Flow

```
DevBots Reports (Markdown)
         ↓
  Data Generator Script
         ↓
  JSON Index Files
         ↓
  Dashboard (Browser)
```

## JSON Schema Definitions

### 1. dashboard.json

Central dashboard state and metadata.

```json
{
  "version": "1.0.0",
  "last_updated": "2026-02-16T20:30:00Z",
  "statistics": {
    "total_projects": 5,
    "active_projects": 3,
    "total_reports": 127,
    "total_bots": 4
  },
  "recent_activity": [
    {
      "timestamp": "2026-02-16T18:30:00Z",
      "bot": "gitbot",
      "project": "uni-li",
      "status": "success",
      "summary": "Analyzed 50 commits"
    }
  ]
}
```

### 2. projects.json

Projects registry (synchronized from ~/.devbot/projects.json).

```json
{
  "projects": [
    {
      "id": "uni-li",
      "name": "uni.li",
      "path": "/home/user/projects/uni.li",
      "description": "University Liechtenstein Project",
      "gitlab_id": 76261915,
      "gitlab_url": "https://gitlab.com",
      "github_repo": null,
      "last_activity": "2026-02-16T18:30:00Z",
      "reports_count": 15,
      "bots_run": ["gitbot", "qabot", "pmbot"]
    }
  ]
}
```

### 3. index.json

Master index of all reports across all projects and bots.

```json
{
  "reports": [
    {
      "id": "gitbot-uni-li-2026-02-16T18-30-00",
      "bot": "gitbot",
      "project_id": "uni-li",
      "project_name": "uni.li",
      "timestamp": "2026-02-16T18:30:00Z",
      "status": "success",
      "summary": "Analyzed 50 commits from Feb 1-16",
      "duration": "45s",
      "path": "../../data/uni.li/reports/gitbot/2026-02-16T18-30-00.md",
      "size_bytes": 12458,
      "metadata": {
        "commits_analyzed": 50,
        "files_changed": 42,
        "authors": 3
      }
    }
  ],
  "last_updated": "2026-02-16T20:30:00Z",
  "total_reports": 127
}
```

## Data Generator Script

### generate_dashboard_data.py

```python
#!/usr/bin/env python3
"""
Generate JSON data files for DevBots Dashboard
Scans the data/ directory and projects registry to create index files
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import re

# Paths
HOME = Path.home()
DEVBOT_DIR = HOME / ".devbot"
PROJECTS_JSON = DEVBOT_DIR / "projects.json"
DATA_DIR = Path(__file__).parent.parent / "data"
DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard" / "data"

class DashboardDataGenerator:
    """Generate dashboard data from DevBots reports"""
    
    def __init__(self):
        self.projects = []
        self.reports = []
        self.bots = ["gitbot", "qabot", "pmbot", "orchestrator"]
    
    def load_projects(self) -> List[Dict[str, Any]]:
        """Load projects from ~/.devbot/projects.json"""
        if not PROJECTS_JSON.exists():
            print(f"⚠️  Projects file not found: {PROJECTS_JSON}")
            return []
        
        try:
            with open(PROJECTS_JSON, 'r') as f:
                data = json.load(f)
                return data.get('projects', [])
        except Exception as e:
            print(f"❌ Error loading projects: {e}")
            return []
    
    def scan_reports(self, project_id: str) -> List[Dict[str, Any]]:
        """Scan report directory for a project"""
        reports = []
        project_data_dir = DATA_DIR / project_id / "reports"
        
        if not project_data_dir.exists():
            return reports
        
        # Scan each bot's reports
        for bot in self.bots:
            bot_reports_dir = project_data_dir / bot
            if not bot_reports_dir.exists():
                continue
            
            # Find all markdown files (skip latest.md)
            for report_file in bot_reports_dir.glob("*.md"):
                if report_file.name == "latest.md":
                    continue
                
                report = self.parse_report(project_id, bot, report_file)
                if report:
                    reports.append(report)
        
        return reports
    
    def parse_report(self, project_id: str, bot: str, 
                    report_path: Path) -> Dict[str, Any] | None:
        """Parse a report file and extract metadata"""
        try:
            # Get file stats
            stat = report_path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            
            # Read first few lines to extract summary
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read(500)  # First 500 chars
                summary = self.extract_summary(content)
            
            # Parse timestamp from filename (e.g., 2026-02-16T18-30-00.md)
            timestamp_str = report_path.stem
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('-', ':', 2))
            except:
                timestamp = mtime
            
            # Determine status from content
            status = self.determine_status(content)
            
            # Generate report ID
            report_id = f"{bot}-{project_id}-{timestamp_str}"
            
            # Get relative path from dashboard
            rel_path = os.path.relpath(report_path, DASHBOARD_DIR.parent)
            
            return {
                "id": report_id,
                "bot": bot,
                "project_id": project_id,
                "timestamp": timestamp.isoformat(),
                "status": status,
                "summary": summary,
                "path": rel_path,
                "size_bytes": stat.st_size
            }
        
        except Exception as e:
            print(f"⚠️  Error parsing {report_path}: {e}")
            return None
    
    def extract_summary(self, content: str) -> str:
        """Extract a summary from report content"""
        # Look for a summary section or first paragraph
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # Skip headers
            if line.startswith('#'):
                continue
            # Take first non-empty line
            if line.strip():
                # Truncate to reasonable length
                summary = line.strip()[:200]
                return summary
        
        return "No summary available"
    
    def determine_status(self, content: str) -> str:
        """Determine report status from content"""
        content_lower = content.lower()
        
        if '❌' in content or 'failed' in content_lower or 'error' in content_lower:
            return 'failed'
        elif '⚠️' in content or 'warning' in content_lower or 'partial' in content_lower:
            return 'partial'
        else:
            return 'success'
    
    def generate_projects_json(self, projects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate projects.json with enriched data"""
        enriched_projects = []
        
        for project in projects:
            project_id = project.get('id')
            if not project_id:
                continue
            
            # Scan reports for this project
            reports = self.scan_reports(project_id)
            
            # Calculate last activity
            last_activity = None
            if reports:
                last_activity = max(r['timestamp'] for r in reports)
            
            # Determine which bots have been run
            bots_run = list(set(r['bot'] for r in reports))
            
            enriched = {
                "id": project_id,
                "name": project.get('name', project_id),
                "path": project.get('path', ''),
                "description": project.get('description', ''),
                "gitlab_id": project.get('gitlab_id'),
                "gitlab_url": project.get('gitlab_url'),
                "github_repo": project.get('github_repo'),
                "last_activity": last_activity,
                "reports_count": len(reports),
                "bots_run": bots_run
            }
            
            enriched_projects.append(enriched)
        
        return {
            "projects": enriched_projects,
            "last_updated": datetime.utcnow().isoformat() + 'Z'
        }
    
    def generate_index_json(self) -> Dict[str, Any]:
        """Generate master reports index"""
        all_reports = []
        
        # Scan all projects
        for project in self.projects:
            project_id = project.get('id')
            if not project_id:
                continue
            
            reports = self.scan_reports(project_id)
            for report in reports:
                report['project_name'] = project.get('name', project_id)
                all_reports.append(report)
        
        # Sort by timestamp (newest first)
        all_reports.sort(key=lambda r: r['timestamp'], reverse=True)
        
        return {
            "reports": all_reports,
            "last_updated": datetime.utcnow().isoformat() + 'Z',
            "total_reports": len(all_reports)
        }
    
    def generate_dashboard_json(self) -> Dict[str, Any]:
        """Generate dashboard.json with statistics"""
        all_reports = self.reports
        
        # Calculate statistics
        active_projects = sum(1 for p in self.projects 
                            if p.get('last_activity'))
        
        # Recent activity (last 10)
        recent_activity = [
            {
                "timestamp": r['timestamp'],
                "bot": r['bot'],
                "project": r['project_name'],
                "status": r['status'],
                "summary": r['summary'][:100]
            }
            for r in all_reports[:10]
        ]
        
        return {
            "version": "1.0.0",
            "last_updated": datetime.utcnow().isoformat() + 'Z',
            "statistics": {
                "total_projects": len(self.projects),
                "active_projects": active_projects,
                "total_reports": len(all_reports),
                "total_bots": len(self.bots)
            },
            "recent_activity": recent_activity
        }
    
    def save_json(self, filename: str, data: Dict[str, Any]):
        """Save JSON data to file"""
        output_path = DASHBOARD_DIR / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Generated: {output_path}")
    
    def run(self):
        """Main execution"""
        print("🤖 DevBots Dashboard Data Generator")
        print("=" * 50)
        
        # Load projects
        print("\n📁 Loading projects...")
        projects = self.load_projects()
        print(f"   Found {len(projects)} projects")
        
        # Generate projects.json
        print("\n📊 Generating projects.json...")
        projects_data = self.generate_projects_json(projects)
        self.projects = projects_data['projects']
        self.save_json('projects.json', projects_data)
        
        # Generate index.json
        print("\n📋 Generating index.json...")
        index_data = self.generate_index_json()
        self.reports = index_data['reports']
        self.save_json('index.json', index_data)
        
        # Generate dashboard.json
        print("\n📈 Generating dashboard.json...")
        dashboard_data = self.generate_dashboard_json()
        self.save_json('dashboard.json', dashboard_data)
        
        print("\n✨ Done! Dashboard data generated successfully.")
        print(f"\n📊 Summary:")
        print(f"   Projects: {len(self.projects)}")
        print(f"   Reports: {len(self.reports)}")
        print(f"   Output: {DASHBOARD_DIR}")

if __name__ == "__main__":
    generator = DashboardDataGenerator()
    generator.run()
```

## Usage

### Manual Generation

```bash
# Run the data generator
cd /path/to/BotsTeam
python3 docs/generate_dashboard_data.py

# Generated files will be in dashboard/data/
ls dashboard/data/
# dashboard.json  index.json  projects.json
```

### Automatic Generation

#### Option 1: Post-Bot Hook
Add a hook to each bot that regenerates dashboard data after completion:

```python
# In each bot's analyzer.py
from dashboard.generate_data import DashboardDataGenerator

def get_bot_result(...):
    # ... bot logic ...
    
    # After saving report
    generator = DashboardDataGenerator()
    generator.run()
    
    return result
```

#### Option 2: Watch Script
Create a file watcher that regenerates data when reports change:

```bash
#!/bin/bash
# watch_reports.sh
while inotifywait -r -e modify,create data/*/reports; do
    python3 docs/generate_dashboard_data.py
done
```

#### Option 3: Cron Job
Set up a cron job to regenerate data periodically:

```bash
# Add to crontab
*/5 * * * * cd /path/to/BotsTeam && python3 docs/generate_dashboard_data.py
```

## Integration with Orchestrator

### Add Dashboard Command

Update `bots/orchestrator/cli.py`:

```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def dashboard(
    port: int = typer.Option(8080, help="Port to serve dashboard on"),
    regenerate: bool = typer.Option(True, help="Regenerate data before serving")
):
    """
    Launch the DevBots Dashboard web interface.
    Generates data and starts a local web server.
    """
    import subprocess
    import webbrowser
    from pathlib import Path
    
    dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
    
    if regenerate:
        console.print("🔄 Generating dashboard data...", style="cyan")
        from docs.generate_dashboard_data import DashboardDataGenerator
        generator = DashboardDataGenerator()
        generator.run()
    
    console.print(f"\n🚀 Starting dashboard server on port {port}...", style="green")
    console.print(f"📊 Dashboard URL: http://localhost:{port}\n")
    
    # Open browser
    webbrowser.open(f"http://localhost:{port}")
    
    # Start server
    os.chdir(dashboard_dir)
    subprocess.run(["python3", "server.py", str(port)])
```

Usage:

```bash
# Launch dashboard
uv run orchestrator dashboard

# Launch on different port
uv run orchestrator dashboard --port 3000

# Launch without regenerating data
uv run orchestrator dashboard --no-regenerate
```

## Data Refresh Strategy

### Client-Side Polling

```javascript
// In dashboard.js
const REFRESH_INTERVAL = 300000; // 5 minutes

async function refreshData() {
    console.log('🔄 Refreshing dashboard data...');
    
    // Reload all data
    const [dashboard, projects, reports] = await Promise.all([
        API.getDashboard(),
        API.getProjects(),
        API.getReportsIndex()
    ]);
    
    // Update UI
    updateDashboard(dashboard);
    updateProjects(projects);
    updateReports(reports);
    
    console.log('✅ Data refreshed');
}

// Auto-refresh
setInterval(refreshData, REFRESH_INTERVAL);

// Manual refresh button
document.getElementById('refresh-btn').addEventListener('click', refreshData);
```

### Server-Sent Events (Future Enhancement)

```python
# In server.py (future enhancement)
class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/events':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            # Send updates when data changes
            while True:
                data = json.dumps(get_latest_stats())
                self.wfile.write(f"data: {data}\n\n".encode())
                time.sleep(5)
        else:
            super().do_GET()
```

## Testing Data Generator

### Test with Sample Data

```bash
# Create test structure
mkdir -p data/test-project/reports/{gitbot,qabot,pmbot}

# Create sample reports
echo "# GitBot Report\n\nAnalyzed 10 commits." > \
    data/test-project/reports/gitbot/2026-02-16T10-00-00.md

echo "# QABot Report\n\nSuggested 5 tests." > \
    data/test-project/reports/qabot/2026-02-16T11-00-00.md

# Generate data
python3 docs/generate_dashboard_data.py

# Verify output
cat dashboard/data/index.json | jq '.reports | length'
```

## Troubleshooting

### No Reports Found
- Check DATA_DIR path is correct
- Verify report directory structure matches expected format
- Check file permissions

### JSON Generation Fails
- Ensure Python 3.6+ is installed
- Check file encoding (should be UTF-8)
- Verify markdown files are readable

### Dashboard Shows No Data
- Check browser console for errors
- Verify JSON files exist in dashboard/data/
- Check CORS headers if serving from different domain
- Validate JSON syntax with `jq` or online validator

## Performance Considerations

### Large Repositories
- Limit reports to last N days in index
- Implement pagination in generator
- Cache parsed reports to avoid re-parsing

### Optimization Tips
- Generate index incrementally (only new reports)
- Use file modification time to skip unchanged files
- Compress JSON files for faster transfer
- Implement lazy loading in dashboard UI

## Future Enhancements

1. **Incremental Updates** - Only regenerate changed data
2. **Real-Time Updates** - WebSocket or SSE for live data
3. **Report Caching** - Cache parsed markdown content
4. **Search Index** - Full-text search across reports
5. **Analytics** - Track bot usage and success rates
6. **Export** - Export data to CSV, PDF, etc.

## Summary

This data generation strategy provides:
- ✅ Automated JSON generation from existing reports
- ✅ Integration with DevBots CLI
- ✅ Flexible refresh strategies
- ✅ Minimal dependencies (just Python standard library)
- ✅ Easy to extend and customize

The dashboard can now consume the generated JSON files without needing direct file system access, making it portable and easy to deploy.
