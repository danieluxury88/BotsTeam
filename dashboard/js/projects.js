// Projects page logic

function viewReport(path) {
    window.location.href = `report.html?path=${encodeURIComponent(path)}`;
}

async function initProjects() {
    UI.initTheme();

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadAllProjects());
    }

    const searchInput = document.getElementById('project-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => filterProjects(e.target.value));
    }

    await Promise.all([API.getBots(), loadAllProjects()]);
}

let allProjects = [];

async function loadAllProjects() {
    const grid = document.getElementById('projects-grid');
    if (!grid) return;

    UI.showLoading(grid);

    try {
        const data = await API.getProjects();

        if (!data || !data.projects || data.projects.length === 0) {
            UI.showEmpty(grid, 'No projects found. Register projects using the orchestrator CLI.');
            return;
        }

        allProjects = data.projects.sort((a, b) => {
            if (!a.last_activity) return 1;
            if (!b.last_activity) return -1;
            return new Date(b.last_activity) - new Date(a.last_activity);
        });

        renderProjects(allProjects);
    } catch (error) {
        console.error('Error loading projects:', error);
        UI.showError(grid, 'Failed to load projects');
    }
}

function renderProjects(projects) {
    const grid = document.getElementById('projects-grid');
    if (!grid) return;

    if (projects.length === 0) {
        UI.showEmpty(grid, 'No projects match your search.');
        return;
    }

    grid.innerHTML = projects.map(p => Components.renderProjectCard(p)).join('');
}

function filterProjects(query) {
    const q = query.toLowerCase().trim();
    if (!q) {
        renderProjects(allProjects);
        return;
    }

    const filtered = allProjects.filter(p =>
        p.name.toLowerCase().includes(q) ||
        (p.description && p.description.toLowerCase().includes(q)) ||
        (p.github_repo && p.github_repo.toLowerCase().includes(q))
    );

    renderProjects(filtered);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProjects);
} else {
    initProjects();
}
