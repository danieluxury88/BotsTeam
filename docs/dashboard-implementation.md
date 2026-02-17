# 🛠️ BotsTeam Dashboard - Implementation Guide

## Overview

This document provides a detailed technical guide for implementing the BotsTeam Dashboard. It covers file structure, code examples, and step-by-step implementation instructions.

## Directory Structure

```
dashboard/
├── index.html                  # Main entry point
├── projects.html              # Projects listing page
├── reports.html               # Reports viewer page
├── bots.html                  # Bot status page
├── activity.html              # Activity feed page
├── settings.html              # Settings page
│
├── css/
│   ├── reset.css              # CSS reset/normalize
│   ├── variables.css          # Design tokens (colors, spacing, fonts)
│   ├── base.css               # Base styles (typography, links)
│   ├── layout.css             # Grid and layout utilities
│   ├── components.css         # Reusable components
│   ├── pages.css              # Page-specific styles
│   └── responsive.css         # Media queries and breakpoints
│
├── js/
│   ├── config.js              # Configuration and constants
│   ├── api.js                 # Data loading from JSON files
│   ├── ui.js                  # UI utilities and helpers
│   ├── components.js          # Component rendering functions
│   ├── dashboard.js           # Dashboard page logic
│   ├── projects.js            # Projects page logic
│   ├── reports.js             # Reports page logic
│   ├── bots.js                # Bots page logic
│   ├── activity.js            # Activity page logic
│   ├── settings.js            # Settings page logic
│   └── utils.js               # General utilities
│
├── data/
│   ├── dashboard.json         # Dashboard state and metadata
│   ├── projects.json          # Projects registry (copied from ~/.devbot/)
│   └── index.json             # Reports index
│
├── assets/
│   ├── icons/                 # SVG icons
│   └── images/                # Images if needed
│
└── server.py                  # Simple Python server to serve the dashboard
```

## Core HTML Template

### index.html (Main Dashboard)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="description" content="DevBots Dashboard - Unified interface for AI-powered development bots">
    <title>DevBots Dashboard</title>
    
    <!-- CSS -->
    <link rel="stylesheet" href="css/reset.css">
    <link rel="stylesheet" href="css/variables.css">
    <link rel="stylesheet" href="css/base.css">
    <link rel="stylesheet" href="css/layout.css">
    <link rel="stylesheet" href="css/components.css">
    <link rel="stylesheet" href="css/pages.css">
    <link rel="stylesheet" href="css/responsive.css">
    
    <!-- Preload critical resources -->
    <link rel="preload" href="js/config.js" as="script">
    <link rel="preload" href="data/dashboard.json" as="fetch" crossorigin>
</head>
<body>
    <!-- Header -->
    <header class="header" role="banner">
        <div class="header-content">
            <div class="header-brand">
                <span class="header-logo">🤖</span>
                <h1 class="header-title">DevBots Dashboard</h1>
            </div>
            <nav class="header-nav" role="navigation" aria-label="Main navigation">
                <a href="index.html" class="nav-link active" aria-current="page">Dashboard</a>
                <a href="projects.html" class="nav-link">Projects</a>
                <a href="bots.html" class="nav-link">Bots</a>
                <a href="activity.html" class="nav-link">Activity</a>
            </nav>
            <div class="header-actions">
                <button class="btn-icon" id="refresh-btn" aria-label="Refresh data" title="Refresh">
                    <span class="icon">🔄</span>
                </button>
                <button class="btn-icon" id="theme-toggle" aria-label="Toggle theme" title="Toggle theme">
                    <span class="icon">☀️</span>
                </button>
                <a href="settings.html" class="btn-icon" aria-label="Settings" title="Settings">
                    <span class="icon">⚙️</span>
                </a>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="main" role="main">
        <div class="container">
            <!-- Summary Cards -->
            <section class="summary-section" aria-label="Dashboard summary">
                <div class="summary-grid">
                    <div class="summary-card">
                        <div class="summary-icon">📊</div>
                        <div class="summary-content">
                            <h2 class="summary-title">Projects</h2>
                            <p class="summary-value" id="projects-count">0</p>
                            <p class="summary-label">Total projects</p>
                        </div>
                        <a href="projects.html" class="summary-link">View All →</a>
                    </div>

                    <div class="summary-card">
                        <div class="summary-icon">🤖</div>
                        <div class="summary-content">
                            <h2 class="summary-title">Bots</h2>
                            <p class="summary-value">4</p>
                            <p class="summary-label">Active bots</p>
                        </div>
                        <a href="bots.html" class="summary-link">View Status →</a>
                    </div>

                    <div class="summary-card">
                        <div class="summary-icon">📈</div>
                        <div class="summary-content">
                            <h2 class="summary-title">Activity</h2>
                            <p class="summary-value" id="activity-count">0</p>
                            <p class="summary-label">Recent actions</p>
                        </div>
                        <a href="activity.html" class="summary-link">View Feed →</a>
                    </div>
                </div>
            </section>

            <!-- Recent Projects -->
            <section class="projects-section" aria-label="Recent projects">
                <div class="section-header">
                    <h2 class="section-title">Recent Projects</h2>
                    <a href="projects.html" class="section-link">View All →</a>
                </div>
                <div class="projects-grid" id="projects-grid">
                    <!-- Projects will be loaded here via JavaScript -->
                    <div class="loading">Loading projects...</div>
                </div>
            </section>

            <!-- Recent Reports -->
            <section class="reports-section" aria-label="Recent reports">
                <div class="section-header">
                    <h2 class="section-title">Recent Reports</h2>
                    <a href="reports.html" class="section-link">View All →</a>
                </div>
                <div class="reports-list" id="reports-list">
                    <!-- Reports will be loaded here via JavaScript -->
                    <div class="loading">Loading reports...</div>
                </div>
            </section>
        </div>
    </main>

    <!-- Footer -->
    <footer class="footer" role="contentinfo">
        <div class="footer-content">
            <p>&copy; 2026 DevBots. Built with ❤️ and no frameworks.</p>
        </div>
    </footer>

    <!-- Scripts -->
    <script src="js/config.js"></script>
    <script src="js/utils.js"></script>
    <script src="js/api.js"></script>
    <script src="js/ui.js"></script>
    <script src="js/components.js"></script>
    <script src="js/dashboard.js"></script>

    <!-- No-JS fallback -->
    <noscript>
        <div class="no-js-message">
            <p>This dashboard works best with JavaScript enabled.</p>
            <p>However, you can still access the CLI tools directly.</p>
        </div>
    </noscript>
</body>
</html>
```

## CSS Implementation

### css/variables.css (Design Tokens)

```css
:root {
    /* Colors - Light Mode */
    --color-bg-primary: #ffffff;
    --color-bg-secondary: #f5f7fa;
    --color-bg-tertiary: #e4e9f0;
    --color-text-primary: #2c3e50;
    --color-text-secondary: #7f8c8d;
    --color-text-tertiary: #95a5a6;
    --color-border: #dce1e8;
    --color-shadow: rgba(0, 0, 0, 0.1);
    
    /* Accent Colors */
    --color-primary: #3498db;
    --color-primary-hover: #2980b9;
    --color-success: #27ae60;
    --color-warning: #f39c12;
    --color-error: #e74c3c;
    --color-info: #3498db;
    
    /* Typography */
    --font-family-base: -apple-system, BlinkMacSystemFont, 'Segoe UI', 
                        'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell',
                        'Helvetica Neue', sans-serif;
    --font-family-mono: 'SF Mono', Monaco, 'Cascadia Code', 'Courier New', monospace;
    
    --font-size-xs: 0.75rem;      /* 12px */
    --font-size-sm: 0.875rem;     /* 14px */
    --font-size-base: 1rem;       /* 16px */
    --font-size-lg: 1.125rem;     /* 18px */
    --font-size-xl: 1.25rem;      /* 20px */
    --font-size-2xl: 1.5rem;      /* 24px */
    --font-size-3xl: 2rem;        /* 32px */
    
    --font-weight-normal: 400;
    --font-weight-medium: 500;
    --font-weight-semibold: 600;
    --font-weight-bold: 700;
    
    --line-height-tight: 1.25;
    --line-height-normal: 1.5;
    --line-height-relaxed: 1.75;
    
    /* Spacing */
    --space-xs: 0.25rem;   /* 4px */
    --space-sm: 0.5rem;    /* 8px */
    --space-md: 1rem;      /* 16px */
    --space-lg: 1.5rem;    /* 24px */
    --space-xl: 2rem;      /* 32px */
    --space-2xl: 3rem;     /* 48px */
    --space-3xl: 4rem;     /* 64px */
    
    /* Layout */
    --container-max-width: 1200px;
    --header-height: 64px;
    --footer-height: 48px;
    
    /* Border Radius */
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-xl: 16px;
    --radius-round: 50%;
    
    /* Shadows */
    --shadow-sm: 0 1px 3px var(--color-shadow);
    --shadow-md: 0 4px 6px var(--color-shadow);
    --shadow-lg: 0 10px 15px var(--color-shadow);
    
    /* Transitions */
    --transition-fast: 150ms ease;
    --transition-base: 250ms ease;
    --transition-slow: 350ms ease;
    
    /* Z-index */
    --z-dropdown: 1000;
    --z-sticky: 1020;
    --z-fixed: 1030;
    --z-modal-backdrop: 1040;
    --z-modal: 1050;
    --z-tooltip: 1070;
}

/* Dark Mode */
[data-theme="dark"] {
    --color-bg-primary: #1e1e1e;
    --color-bg-secondary: #2d2d2d;
    --color-bg-tertiary: #3a3a3a;
    --color-text-primary: #e0e0e0;
    --color-text-secondary: #a0a0a0;
    --color-text-tertiary: #808080;
    --color-border: #404040;
    --color-shadow: rgba(0, 0, 0, 0.3);
}

/* Prefers dark mode */
@media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
        --color-bg-primary: #1e1e1e;
        --color-bg-secondary: #2d2d2d;
        --color-bg-tertiary: #3a3a3a;
        --color-text-primary: #e0e0e0;
        --color-text-secondary: #a0a0a0;
        --color-text-tertiary: #808080;
        --color-border: #404040;
        --color-shadow: rgba(0, 0, 0, 0.3);
    }
}
```

### css/components.css (Component Styles)

```css
/* Card Component */
.card {
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    padding: var(--space-lg);
    transition: all var(--transition-base);
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
}

.card:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-md);
}

.card-title {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
    margin: 0;
}

.card-status {
    padding: var(--space-xs) var(--space-sm);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
}

.status-active {
    background: var(--color-success);
    color: white;
}

.status-idle {
    background: var(--color-text-tertiary);
    color: white;
}

.status-warning {
    background: var(--color-warning);
    color: white;
}

.status-error {
    background: var(--color-error);
    color: white;
}

.card-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
}

.card-description {
    color: var(--color-text-secondary);
    line-height: var(--line-height-normal);
}

.card-meta {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
}

.card-actions {
    display: flex;
    gap: var(--space-sm);
    padding-top: var(--space-md);
    border-top: 1px solid var(--color-border);
}

/* Button Component */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-lg);
    min-height: 48px;
    min-width: 48px;
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-medium);
    font-family: var(--font-family-base);
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    text-decoration: none;
    white-space: nowrap;
}

.btn:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
}

.btn:active {
    transform: translateY(0);
}

.btn:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
}

.btn-primary {
    background: var(--color-primary);
    color: white;
}

.btn-primary:hover {
    background: var(--color-primary-hover);
}

.btn-secondary {
    background: var(--color-bg-tertiary);
    color: var(--color-text-primary);
}

.btn-secondary:hover {
    background: var(--color-border);
}

.btn-icon {
    padding: var(--space-sm);
    min-width: 48px;
    min-height: 48px;
    background: transparent;
    border: none;
    cursor: pointer;
    border-radius: var(--radius-md);
    transition: background var(--transition-fast);
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-icon:hover {
    background: var(--color-bg-tertiary);
}

.btn-icon .icon {
    font-size: var(--font-size-xl);
}

/* Loading State */
.loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-2xl);
    color: var(--color-text-secondary);
    font-size: var(--font-size-lg);
}

.loading::before {
    content: "⏳";
    margin-right: var(--space-sm);
    animation: spin 2s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

/* Empty State */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-3xl);
    text-align: center;
    color: var(--color-text-secondary);
}

.empty-state-icon {
    font-size: 4rem;
    margin-bottom: var(--space-lg);
}

.empty-state-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
    margin-bottom: var(--space-sm);
}

.empty-state-description {
    font-size: var(--font-size-base);
    max-width: 400px;
}
```

## JavaScript Implementation

### js/config.js (Configuration)

```javascript
// Configuration and constants
const CONFIG = {
    // API endpoints (relative to dashboard root)
    API: {
        DASHBOARD: 'data/dashboard.json',
        PROJECTS: 'data/projects.json',
        REPORTS_INDEX: 'data/index.json'
    },
    
    // UI settings
    UI: {
        ITEMS_PER_PAGE: 10,
        AUTO_REFRESH_INTERVAL: 300000, // 5 minutes in milliseconds
        ANIMATION_DURATION: 250
    },
    
    // LocalStorage keys
    STORAGE: {
        THEME: 'devbots-theme',
        SETTINGS: 'devbots-settings'
    },
    
    // Bot configuration
    BOTS: [
        {
            id: 'gitbot',
            name: 'GitBot',
            icon: '🔍',
            description: 'Git history analyzer'
        },
        {
            id: 'qabot',
            name: 'QABot',
            icon: '🧪',
            description: 'Test suggestion and execution'
        },
        {
            id: 'pmbot',
            name: 'PMBot',
            icon: '📊',
            description: 'Issue analyzer and sprint planner'
        },
        {
            id: 'orchestrator',
            name: 'Orchestrator',
            icon: '🎭',
            description: 'Conversational bot interface'
        }
    ],
    
    // Status configuration
    STATUS: {
        SUCCESS: { icon: '✅', color: 'success', label: 'Success' },
        PARTIAL: { icon: '⚠️', color: 'warning', label: 'Partial' },
        FAILED: { icon: '❌', color: 'error', label: 'Failed' },
        ERROR: { icon: '❌', color: 'error', label: 'Error' },
        IDLE: { icon: '⚪', color: 'idle', label: 'Idle' },
        RUNNING: { icon: '▶️', color: 'info', label: 'Running' }
    }
};

// Make CONFIG globally available
window.CONFIG = CONFIG;
```

### js/api.js (Data Loading)

```javascript
// API module for loading data
const API = {
    // Fetch JSON data
    async fetchJSON(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`Error fetching ${url}:`, error);
            return null;
        }
    },
    
    // Load dashboard data
    async getDashboard() {
        return await this.fetchJSON(CONFIG.API.DASHBOARD);
    },
    
    // Load projects
    async getProjects() {
        return await this.fetchJSON(CONFIG.API.PROJECTS);
    },
    
    // Load reports index
    async getReportsIndex() {
        return await this.fetchJSON(CONFIG.API.REPORTS_INDEX);
    },
    
    // Load a specific markdown report
    async getReport(path) {
        try {
            const response = await fetch(path);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.text();
        } catch (error) {
            console.error(`Error fetching report ${path}:`, error);
            return null;
        }
    }
};

// Make API globally available
window.API = API;
```

### js/components.js (Component Rendering)

```javascript
// Component rendering functions
const Components = {
    // Render a project card
    renderProjectCard(project) {
        const statusClass = project.last_activity ? 'status-active' : 'status-idle';
        const statusText = project.last_activity ? 'Active' : 'Idle';
        const integration = project.gitlab_id ? `GitLab #${project.gitlab_id}` :
                          project.github_repo ? `GitHub: ${project.github_repo}` :
                          'No integration';
        
        return `
            <article class="card project-card" data-project-id="${project.id}">
                <div class="card-header">
                    <h3 class="card-title">📁 ${project.name}</h3>
                    <span class="card-status ${statusClass}">${statusText}</span>
                </div>
                <div class="card-body">
                    <p class="card-description">${project.description || 'No description'}</p>
                    <ul class="card-meta">
                        <li>${integration}</li>
                        <li>Last activity: ${this.formatDate(project.last_activity)}</li>
                        <li>📊 ${project.reports_count || 0} reports</li>
                    </ul>
                </div>
                <div class="card-actions">
                    <a href="reports.html?project=${project.id}" class="btn btn-primary">
                        View Reports
                    </a>
                    <button class="btn btn-secondary" onclick="runBot('${project.id}')">
                        Run Bot
                    </button>
                </div>
            </article>
        `;
    },
    
    // Render a report item
    renderReportItem(report) {
        const status = CONFIG.STATUS[report.status] || CONFIG.STATUS.SUCCESS;
        
        return `
            <article class="report-item" data-report-id="${report.id}">
                <div class="report-status">
                    <span class="status-icon">${status.icon}</span>
                </div>
                <div class="report-content">
                    <h3 class="report-title">
                        ${CONFIG.BOTS.find(b => b.id === report.bot)?.icon || '🤖'} 
                        ${report.bot} - ${report.project}
                    </h3>
                    <p class="report-summary">${report.summary}</p>
                    <div class="report-meta">
                        <span>${this.formatDate(report.timestamp)}</span>
                        <span>•</span>
                        <span>${status.label}</span>
                        ${report.duration ? `<span>•</span><span>${report.duration}</span>` : ''}
                    </div>
                </div>
                <div class="report-actions">
                    <a href="report-view.html?id=${report.id}" class="btn-icon" 
                       aria-label="View report" title="View report">
                        <span class="icon">📄</span>
                    </a>
                </div>
            </article>
        `;
    },
    
    // Format date for display
    formatDate(dateString) {
        if (!dateString) return 'Never';
        
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        
        // Less than 1 minute
        if (diff < 60000) return 'Just now';
        
        // Less than 1 hour
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        }
        
        // Less than 1 day
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        }
        
        // Less than 1 week
        if (diff < 604800000) {
            const days = Math.floor(diff / 86400000);
            return `${days} day${days > 1 ? 's' : ''} ago`;
        }
        
        // Format as date
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }
};

// Make Components globally available
window.Components = Components;
```

## Python Server

### server.py (Simple HTTP Server)

```python
#!/usr/bin/env python3
"""
Simple HTTP server for DevBots Dashboard
Serves static files and provides a basic REST-like interface to project data
"""

import http.server
import socketserver
import json
import os
from pathlib import Path

PORT = 8080
DASHBOARD_DIR = Path(__file__).parent

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler with CORS support and JSON responses"""
    
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    """Start the dashboard server"""
    os.chdir(DASHBOARD_DIR)
    
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"🤖 DevBots Dashboard")
        print(f"📊 Server running at http://localhost:{PORT}")
        print(f"📁 Serving from: {DASHBOARD_DIR}")
        print(f"\nPress Ctrl+C to stop the server")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped")

if __name__ == "__main__":
    run_server()
```

## Implementation Checklist

### Phase 1: Foundation
- [ ] Create directory structure
- [ ] Implement HTML templates (index, projects, reports, etc.)
- [ ] Implement CSS system (variables, base, components, layout)
- [ ] Create basic Python server
- [ ] Test static file serving

### Phase 2: Data Layer
- [ ] Define JSON data schemas
- [ ] Create data generation scripts
- [ ] Implement data loading (api.js)
- [ ] Create mock data for testing
- [ ] Test data API

### Phase 3: UI Components
- [ ] Implement component rendering (components.js)
- [ ] Create reusable UI utilities (ui.js)
- [ ] Build page-specific logic (dashboard.js, projects.js, etc.)
- [ ] Add interactivity (filtering, sorting, search)
- [ ] Test components

### Phase 4: Features
- [ ] Theme switcher (light/dark mode)
- [ ] Settings persistence (LocalStorage)
- [ ] Report viewer with markdown rendering
- [ ] Activity feed with live updates
- [ ] Touch gestures (swipe, pull-to-refresh)

### Phase 5: Polish
- [ ] Responsive design testing (mobile, tablet, desktop)
- [ ] Accessibility audit (keyboard nav, screen readers, ARIA)
- [ ] Performance optimization
- [ ] Error handling and loading states
- [ ] Documentation and deployment guide

## Testing Strategy

### Manual Testing
1. **Desktop browsers**: Chrome, Firefox, Safari, Edge
2. **Mobile devices**: iOS Safari, Android Chrome
3. **Tablet devices**: iPad, Android tablets
4. **Touch interactions**: Swipe, tap, long-press
5. **Accessibility**: Keyboard navigation, screen readers

### Automated Testing (Optional)
- HTML validation: W3C validator
- CSS validation: CSS validator
- Accessibility: axe DevTools
- Performance: Lighthouse
- Cross-browser: BrowserStack

## Deployment Options

### Option 1: Local Development
```bash
cd dashboard
python3 server.py
# Access at http://localhost:8080
```

### Option 2: DevBots CLI Integration
Add to orchestrator CLI:
```bash
uv run orchestrator dashboard
# Starts dashboard server and opens browser
```

### Option 3: Static Hosting
Deploy dashboard directory to:
- GitHub Pages
- Netlify
- Vercel
- Any static hosting service

## Next Steps

1. Create initial HTML/CSS/JS files based on templates above
2. Implement data generation scripts to create JSON from bot reports
3. Build out component library with all UI elements
4. Add interactivity and JavaScript functionality
5. Test thoroughly on multiple devices
6. Document usage and deployment procedures
7. Consider adding bot integration for live data updates

This implementation guide provides a solid foundation for building the dashboard without any frameworks or build tools, keeping everything simple and touch-friendly as required.
