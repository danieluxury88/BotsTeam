// Main dashboard page logic

// Global function for viewing reports (called from components)
function viewReport(path) {
    window.location.href = `report.html?path=${encodeURIComponent(path)}`;
}

// Initialize dashboard
async function initDashboard() {
    // Initialize theme
    UI.initTheme();
    
    // Setup refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadDashboard());
    }
    
    // Load dashboard data
    await loadDashboard();
}

// Load all dashboard data
async function loadDashboard() {
    await Promise.all([
        loadSummary(),
        loadProjects(),
        loadReports()
    ]);
}

// Load summary statistics
async function loadSummary() {
    try {
        const data = await API.getDashboard();
        
        if (data && data.statistics) {
            const stats = data.statistics;
            
            // Update projects count
            const projectsCount = document.getElementById('projects-count');
            if (projectsCount) {
                projectsCount.textContent = stats.total_projects || 0;
            }
            
            // Update activity count
            const activityCount = document.getElementById('activity-count');
            if (activityCount) {
                activityCount.textContent = data.recent_activity?.length || 0;
            }
        }
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

// Load projects
async function loadProjects() {
    const projectsGrid = document.getElementById('projects-grid');
    if (!projectsGrid) return;
    
    UI.showLoading(projectsGrid);
    
    try {
        const data = await API.getProjects();
        
        if (!data || !data.projects || data.projects.length === 0) {
            UI.showEmpty(projectsGrid, 'No projects found. Register projects using the orchestrator CLI.');
            return;
        }
        
        // Sort by last_activity (most recent first)
        const sortedProjects = data.projects.sort((a, b) => {
            if (!a.last_activity) return 1;
            if (!b.last_activity) return -1;
            return new Date(b.last_activity) - new Date(a.last_activity);
        });
        
        // Show only the 4 most recent projects on dashboard
        const recentProjects = sortedProjects.slice(0, 4);
        
        // Render project cards
        const html = recentProjects.map(project => 
            Components.renderProjectCard(project)
        ).join('');
        
        projectsGrid.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading projects:', error);
        UI.showError(projectsGrid, 'Failed to load projects');
    }
}

// Load reports
async function loadReports() {
    const reportsList = document.getElementById('reports-list');
    if (!reportsList) return;
    
    UI.showLoading(reportsList);
    
    try {
        const data = await API.getReportsIndex();
        
        if (!data || !data.reports || data.reports.length === 0) {
            UI.showEmpty(reportsList, 'No reports found. Run bots to generate reports.');
            return;
        }
        
        // Show only the 5 most recent reports on dashboard
        const recentReports = data.reports.slice(0, 5);
        
        // Render report items
        const html = recentReports.map(report => 
            Components.renderReportItem(report)
        ).join('');
        
        reportsList.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading reports:', error);
        UI.showError(reportsList, 'Failed to load reports');
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}
