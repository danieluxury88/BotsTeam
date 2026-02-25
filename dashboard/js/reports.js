// Reports page logic

function viewReport(path) {
    window.location.href = `report.html?path=${encodeURIComponent(path)}`;
}

let allReports = [];
let allProjectsList = [];

async function initReports() {
    UI.initTheme();

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadReports());
    }

    const filterProject = document.getElementById('filter-project');
    const filterBot = document.getElementById('filter-bot');

    if (filterProject) {
        filterProject.addEventListener('change', applyFilters);
    }
    if (filterBot) {
        filterBot.addEventListener('change', applyFilters);
    }

    await loadReports();

    // Apply query params after loading
    applyQueryParams();
}

async function loadReports() {
    const list = document.getElementById('reports-list');
    if (!list) return;

    UI.showLoading(list);

    try {
        const [reportsData, projectsData] = await Promise.all([
            API.getReportsIndex(),
            API.getProjects(),
            API.getBots()
        ]);

        allReports = (reportsData && reportsData.reports) ? reportsData.reports : [];
        allProjectsList = (projectsData && projectsData.projects) ? projectsData.projects : [];

        populateFilters();
        renderReports(allReports);
    } catch (error) {
        console.error('Error loading reports:', error);
        UI.showError(list, 'Failed to load reports');
    }
}

function populateFilters() {
    const filterProject = document.getElementById('filter-project');
    const filterBot = document.getElementById('filter-bot');

    if (filterProject) {
        // Get unique project IDs from reports
        const projectIds = [...new Set(allReports.map(r => r.project_id).filter(Boolean))];
        const projectOptions = projectIds.map(id => {
            const proj = allProjectsList.find(p => p.id === id);
            const name = proj ? proj.name : id;
            return `<option value="${Utils.escapeHtml(id)}">${Utils.escapeHtml(name)}</option>`;
        });
        filterProject.innerHTML = '<option value="">All Projects</option>' + projectOptions.join('');
    }

    if (filterBot) {
        const botOptions = CONFIG.BOTS.map(bot =>
            `<option value="${Utils.escapeHtml(bot.id)}">${bot.icon} ${Utils.escapeHtml(bot.name)}</option>`
        );
        filterBot.innerHTML = '<option value="">All Bots</option>' + botOptions.join('');
    }
}

function applyQueryParams() {
    const params = new URLSearchParams(window.location.search);
    const project = params.get('project');
    const bot = params.get('bot');

    const filterProject = document.getElementById('filter-project');
    const filterBot = document.getElementById('filter-bot');

    if (project && filterProject) {
        filterProject.value = project;
    }
    if (bot && filterBot) {
        filterBot.value = bot;
    }

    if (project || bot) {
        applyFilters();
    }
}

function applyFilters() {
    const filterProject = document.getElementById('filter-project');
    const filterBot = document.getElementById('filter-bot');

    const selectedProject = filterProject ? filterProject.value : '';
    const selectedBot = filterBot ? filterBot.value : '';

    let filtered = allReports;

    if (selectedProject) {
        filtered = filtered.filter(r => r.project_id === selectedProject);
    }
    if (selectedBot) {
        filtered = filtered.filter(r => r.bot === selectedBot);
    }

    renderReports(filtered);
}

function renderReports(reports) {
    const list = document.getElementById('reports-list');
    if (!list) return;

    if (reports.length === 0) {
        UI.showEmpty(list, 'No reports match the current filters.');
        return;
    }

    list.innerHTML = reports.map(r => Components.renderReportItem(r)).join('');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReports);
} else {
    initReports();
}
