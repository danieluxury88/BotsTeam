#!/usr/bin/env python3
"""
Generate JSON data files for DevBots Dashboard
Scans the data/ directory and projects registry to create index files
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

# Paths
HOME = Path.home()
DEVBOT_DIR = HOME / ".devbot"
PROJECTS_JSON = DEVBOT_DIR / "projects.json"
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
DASHBOARD_DIR = REPO_ROOT / "dashboard" / "data"

class DashboardDataGenerator:
    """Generate dashboard data from DevBots reports"""
    
    def __init__(self):
        self.projects = []
        self.reports = []
        self.bots = ["gitbot", "qabot", "pmbot", "orchestrator"]
    
    def load_projects(self) -> List[Dict[str, Any]]:
        """Load projects from ~/.devbot/projects.json

        The registry stores projects as a flat dict keyed by project name:
        {"my-project": {"name": "...", "path": "...", ...}, ...}

        We convert each entry into a dict with an "id" field derived from the key.
        """
        if not PROJECTS_JSON.exists():
            print(f"⚠️  Projects file not found: {PROJECTS_JSON}")
            print("   Using empty project list.")
            return []

        try:
            with open(PROJECTS_JSON, 'r') as f:
                data = json.load(f)
                # Registry format: flat dict keyed by project name
                projects = []
                for key, proj in data.items():
                    proj["id"] = key
                    if "name" not in proj:
                        proj["name"] = key
                    # Map registry field names to dashboard field names
                    if "gitlab_project_id" in proj and "gitlab_id" not in proj:
                        proj["gitlab_id"] = proj["gitlab_project_id"]
                    projects.append(proj)
                return projects
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
                    report_path: Path) -> Optional[Dict[str, Any]]:
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
                # Handle ISO format with hyphens instead of colons
                timestamp = datetime.fromisoformat(timestamp_str.replace('-', ':', 2))
            except:
                timestamp = mtime
            
            # Determine status from content
            status = self.determine_status(content)
            
            # Generate report ID
            report_id = f"{bot}-{project_id}-{timestamp_str}"
            
            # Build URL path served by the dashboard server
            url_path = f"reports/{project_id}/{bot}/{report_path.name}"

            return {
                "id": report_id,
                "bot": bot,
                "project_id": project_id,
                "timestamp": timestamp.isoformat(),
                "status": status,
                "summary": summary,
                "path": url_path,
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
            "last_updated": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
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
            "last_updated": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
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
            "last_updated": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
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
