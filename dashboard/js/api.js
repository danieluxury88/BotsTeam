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
