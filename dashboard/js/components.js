// Shared report actions used across dashboard pages.
function viewReport(path) {
    window.location.href = `report.html?path=${encodeURIComponent(path)}`;
}

function viewReportWithFormats(path, htmlPath = '', pdfPath = '') {
    const params = new URLSearchParams({ path });
    if (htmlPath) params.set('html', htmlPath);
    if (pdfPath) params.set('pdf', pdfPath);
    window.location.href = `report.html?${params.toString()}`;
}

function improveReportFromDashboard(path, htmlPath = '', pdfPath = '') {
    const params = new URLSearchParams({ path, action: 'improve' });
    if (htmlPath) params.set('html', htmlPath);
    if (pdfPath) params.set('pdf', pdfPath);
    window.location.href = `report.html?${params.toString()}`;
}

function openArtifact(path) {
    window.open(path, '_blank', 'noopener');
}

async function exportReport(path) {
    const result = await API.exportReport(path);
    if (result.error) {
        alert(`Export failed: ${result.error}`);
        return;
    }

    if (result.data?.errors?.length) {
        alert(`Export completed with warnings:\n${result.data.errors.join('\n')}`);
    }

    const pdfPath = result.data?.artifacts?.pdf;
    if (pdfPath) {
        window.open(pdfPath, '_blank', 'noopener');
    }

    if (typeof loadReports === 'function') {
        await loadReports();
    } else {
        window.location.reload();
    }
}

// Component rendering functions
const Components = {
    // Render a project card
    renderProjectCard(project) {
        const statusClass = project.last_activity ? 'status-active' : 'status-idle';
        const statusText = project.last_activity ? 'Active' : 'Idle';
        const projectIdEscaped = Utils.escapeHtml(project.id);
        const projectIdUrl = encodeURIComponent(project.id);
        const isPersonal = project.scope === 'personal';
        const scopeBadge = isPersonal
            ? '<span class="scope-badge scope-personal" title="Personal project">👤 Personal</span>'
            : '<span class="scope-badge scope-team" title="Team project">👥 Team</span>';
        const integration = project.gitlab_id ? `GitLab #${project.gitlab_id}` :
                          project.github_repo ? `GitHub: ${project.github_repo}` :
                          project.site_url ? `Site: ${project.site_url}` :
                          isPersonal ? 'Local files' : 'No integration';
        const languages = Array.isArray(project.languages) && project.languages.length
            ? project.languages.join(', ')
            : (project.language || 'unknown');
        const frameworks = Array.isArray(project.frameworks) && project.frameworks.length
            ? project.frameworks.join(', ')
            : '';

        const actions = [
            `
                <a href="reports.html?project=${projectIdUrl}" class="btn btn-primary">
                    View Reports
                </a>
            `
        ];

        if (window.ReportGenerator && typeof window.ReportGenerator.openModal === 'function') {
            actions.push(`
                <button class="btn btn-success" onclick="ReportGenerator.openModal('${projectIdEscaped}')">
                    Generate Reports
                </button>
            `);
        }

        if (window.ProjectAdmin && typeof window.ProjectAdmin.openEditModal === 'function') {
            actions.push(`
                <button class="btn btn-secondary" onclick="ProjectAdmin.openEditModal('${projectIdEscaped}')">
                    Edit
                </button>
            `);
        }

        if (window.ProjectAdmin && typeof window.ProjectAdmin.confirmDelete === 'function') {
            actions.push(`
                <button class="btn btn-danger" onclick="ProjectAdmin.confirmDelete('${projectIdEscaped}')">
                    Delete
                </button>
            `);
        }
        
        return `
            <article class="card project-card" data-project-id="${projectIdEscaped}" data-scope="${Utils.escapeHtml(project.scope || 'team')}">
                <div class="card-header">
                    <h3 class="card-title">📁 ${Utils.escapeHtml(project.name)}</h3>
                    <div class="card-header-right">
                        ${scopeBadge}
                        <span class="card-status ${statusClass}">${statusText}</span>
                    </div>
                </div>
                <div class="card-body">
                    <p class="card-description">${Utils.escapeHtml(project.description || 'No description')}</p>
                    <ul class="card-meta">
                        <li>${Utils.escapeHtml(integration)}</li>
                        <li>Languages: ${Utils.escapeHtml(languages)}</li>
                        ${frameworks ? `<li>Frameworks: ${Utils.escapeHtml(frameworks)}</li>` : ''}
                        ${project.site_url ? `<li>${Utils.escapeHtml(project.site_url)}</li>` : ''}
                        ${project.audit_urls && project.audit_urls.length ? `<li>${project.audit_urls.length} extra audit URLs</li>` : ''}
                        <li>Last activity: ${Utils.formatDate(project.last_activity)}</li>
                        <li>📊 ${project.reports_count || 0} reports</li>
                    </ul>
                </div>
                <div class="card-actions">
                    ${actions.join('')}
                </div>
            </article>
        `;
    },
    
    // Render a report item
    renderReportItem(report) {
        const status = CONFIG.STATUS[report.status?.toUpperCase()] || CONFIG.STATUS.SUCCESS;
        const botInfo = CONFIG.BOTS.find(b => b.id === report.bot);
        const botIcon = botInfo ? botInfo.icon : '🤖';
        const formats = report.formats || { md: report.path };
        const markdownPath = Utils.escapeHtml(formats.md || report.path);
        const htmlPath = Utils.escapeHtml(formats.html || '');
        const pdfPath = Utils.escapeHtml(formats.pdf || '');
        const actionButtons = [
            `
                <button class="btn-icon" onclick="viewReportWithFormats('${markdownPath}', '${htmlPath}', '${pdfPath}')"
                   aria-label="View markdown report" title="View markdown report">
                    <span class="icon">📄</span>
                </button>
            `,
            `
                <button class="btn-icon" onclick="improveReportFromDashboard('${markdownPath}', '${htmlPath}', '${pdfPath}')"
                   aria-label="Improve report with ReportBot" title="Improve report with ReportBot">
                    <span class="icon">✨</span>
                </button>
            `
        ];

        if (formats.html) {
            actionButtons.push(`
                <button class="btn-icon" onclick="openArtifact('${htmlPath}')"
                   aria-label="Open HTML report" title="Open HTML report">
                    <span class="icon">🌐</span>
                </button>
            `);
        }

        if (formats.pdf) {
            actionButtons.push(`
                <a class="btn-icon" href="${Utils.escapeHtml(formats.pdf)}" target="_blank" rel="noopener"
                   aria-label="Open PDF report" title="Open PDF report">
                    <span class="icon">⬇️</span>
                </a>
            `);
        } else {
            actionButtons.push(`
                <button class="btn-icon" onclick="exportReport('${markdownPath}')"
                   aria-label="Export PDF" title="Export PDF">
                    <span class="icon">🖨️</span>
                </button>
            `);
        }
        
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
                    ${actionButtons.join('')}
                </div>
            </article>
        `;
    }
};

// Make Components globally available
window.Components = Components;
