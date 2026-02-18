// Project administration — modal form for add/edit/delete
const ProjectAdmin = {
    _editingName: null, // non-null when editing an existing project

    openAddModal() {
        this._editingName = null;
        const modal = document.getElementById('project-modal');
        document.getElementById('modal-title').textContent = 'Add Project';
        document.getElementById('project-form').reset();
        document.getElementById('field-name').disabled = false;
        document.getElementById('form-error').textContent = '';
        modal.hidden = false;
        document.getElementById('field-name').focus();
    },

    openEditModal(projectName) {
        const project = allProjects.find(p => p.id === projectName);
        if (!project) return;

        this._editingName = projectName;
        const modal = document.getElementById('project-modal');
        document.getElementById('modal-title').textContent = 'Edit Project';

        document.getElementById('field-name').value = project.id;
        document.getElementById('field-name').disabled = true;
        document.getElementById('field-path').value = project.path || '';
        document.getElementById('field-description').value = project.description || '';
        document.getElementById('field-language').value = project.language || 'python';
        document.getElementById('field-gitlab-id').value = project.gitlab_id || '';
        document.getElementById('field-gitlab-url').value = project.gitlab_url || '';
        document.getElementById('field-github-repo').value = project.github_repo || '';
        document.getElementById('form-error').textContent = '';

        modal.hidden = false;
        document.getElementById('field-path').focus();
    },

    closeModal() {
        document.getElementById('project-modal').hidden = true;
        this._editingName = null;
    },

    async handleSubmit(event) {
        event.preventDefault();
        const errorEl = document.getElementById('form-error');
        errorEl.textContent = '';

        const body = {
            name: document.getElementById('field-name').value.trim(),
            path: document.getElementById('field-path').value.trim(),
            description: document.getElementById('field-description').value.trim(),
            language: document.getElementById('field-language').value,
            gitlab_project_id: document.getElementById('field-gitlab-id').value.trim() || null,
            gitlab_url: document.getElementById('field-gitlab-url').value.trim() || null,
            github_repo: document.getElementById('field-github-repo').value.trim() || null,
        };

        let result;
        if (this._editingName) {
            result = await API.updateProject(this._editingName, body);
        } else {
            result = await API.createProject(body);
        }

        if (result.error) {
            errorEl.textContent = result.error;
            return;
        }

        this.closeModal();
        await loadAllProjects();
    },

    async confirmDelete(projectName) {
        if (!confirm(`Delete project "${projectName}"? This only removes it from the registry, not from disk.`)) {
            return;
        }
        const result = await API.deleteProject(projectName);
        if (result.error) {
            alert(`Failed to delete: ${result.error}`);
            return;
        }
        await loadAllProjects();
    }
};

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('project-modal');
        if (modal && !modal.hidden) {
            ProjectAdmin.closeModal();
        }
    }
});

// Close modal when clicking backdrop
document.addEventListener('click', (e) => {
    if (e.target.id === 'project-modal') {
        ProjectAdmin.closeModal();
    }
});

window.ProjectAdmin = ProjectAdmin;
