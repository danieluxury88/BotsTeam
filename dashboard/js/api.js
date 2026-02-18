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
    
    // Mutate helper for POST/PUT/DELETE
    async _mutate(url, method, body) {
        try {
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: body != null ? JSON.stringify(body) : undefined
            });
            const contentType = response.headers.get('Content-Type') || '';
            if (!contentType.includes('application/json')) {
                return { error: `Server error (HTTP ${response.status})`, status: response.status };
            }
            const data = await response.json();
            if (!response.ok) {
                return { error: data.error || `HTTP ${response.status}`, status: response.status };
            }
            return { data, status: response.status };
        } catch (error) {
            console.error(`Error in ${method} ${url}:`, error);
            return { error: error.message, status: 0 };
        }
    },

    // Create a new project
    async createProject(body) {
        return await this._mutate(CONFIG.API.PROJECTS_API, 'POST', body);
    },

    // Update an existing project
    async updateProject(name, body) {
        return await this._mutate(`${CONFIG.API.PROJECTS_API}/${encodeURIComponent(name)}`, 'PUT', body);
    },

    // Delete a project
    async deleteProject(name) {
        return await this._mutate(`${CONFIG.API.PROJECTS_API}/${encodeURIComponent(name)}`, 'DELETE');
    },

    // Generate reports for a project (longer timeout for bot execution)
    async generateReports(name, options) {
        const url = `${CONFIG.API.PROJECTS_API}/${encodeURIComponent(name)}/reports`;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 120000); // 2 min timeout
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(options),
                signal: controller.signal
            });
            clearTimeout(timeout);
            const contentType = response.headers.get('Content-Type') || '';
            if (!contentType.includes('application/json')) {
                return { error: `Server error (HTTP ${response.status})`, status: response.status };
            }
            const data = await response.json();
            if (!response.ok) {
                return { error: data.error || `HTTP ${response.status}`, status: response.status };
            }
            return { data, status: response.status };
        } catch (error) {
            clearTimeout(timeout);
            if (error.name === 'AbortError') {
                return { error: 'Request timed out. The bots may still be running on the server.', status: 0 };
            }
            return { error: error.message, status: 0 };
        }
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
