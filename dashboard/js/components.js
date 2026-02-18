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
            <article class="card project-card" data-project-id="${Utils.escapeHtml(project.id)}">
                <div class="card-header">
                    <h3 class="card-title">📁 ${Utils.escapeHtml(project.name)}</h3>
                    <span class="card-status ${statusClass}">${statusText}</span>
                </div>
                <div class="card-body">
                    <p class="card-description">${Utils.escapeHtml(project.description || 'No description')}</p>
                    <ul class="card-meta">
                        <li>${Utils.escapeHtml(integration)}</li>
                        <li>Last activity: ${Utils.formatDate(project.last_activity)}</li>
                        <li>📊 ${project.reports_count || 0} reports</li>
                    </ul>
                </div>
                <div class="card-actions">
                    <a href="reports.html?project=${encodeURIComponent(project.id)}" class="btn btn-primary">
                        View Reports
                    </a>
                    <button class="btn btn-success" onclick="ReportGenerator.openModal('${Utils.escapeHtml(project.id)}')">
                        Generate Reports
                    </button>
                    <button class="btn btn-secondary" onclick="ProjectAdmin.openEditModal('${Utils.escapeHtml(project.id)}')">
                        Edit
                    </button>
                    <button class="btn btn-danger" onclick="ProjectAdmin.confirmDelete('${Utils.escapeHtml(project.id)}')">
                        Delete
                    </button>
                </div>
            </article>
        `;
    },
    
    // Render a report item
    renderReportItem(report) {
        const status = CONFIG.STATUS[report.status?.toUpperCase()] || CONFIG.STATUS.SUCCESS;
        const botInfo = CONFIG.BOTS.find(b => b.id === report.bot);
        const botIcon = botInfo ? botInfo.icon : '🤖';
        
        return `
            <article class="report-item" data-report-id="${Utils.escapeHtml(report.id)}">
                <div class="report-status">
                    <span class="status-icon">${status.icon}</span>
                </div>
                <div class="report-content">
                    <h3 class="report-title">
                        ${botIcon} ${Utils.escapeHtml(report.bot)} - ${Utils.escapeHtml(report.project_name || report.project_id)}
                    </h3>
                    <p class="report-summary">${Utils.escapeHtml(Utils.truncate(report.summary, 150))}</p>
                    <div class="report-meta">
                        <span>${Utils.formatDate(report.timestamp)}</span>
                        <span>•</span>
                        <span>${status.label}</span>
                        ${report.duration ? `<span>•</span><span>${Utils.escapeHtml(report.duration)}</span>` : ''}
                    </div>
                </div>
                <div class="report-actions">
                    <button class="btn-icon" onclick="viewReport('${Utils.escapeHtml(report.path)}')" 
                       aria-label="View report" title="View report">
                        <span class="icon">📄</span>
                    </button>
                </div>
            </article>
        `;
    }
};

// Make Components globally available
window.Components = Components;
