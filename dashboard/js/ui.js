// UI utilities and helpers
const UI = {
    // Initialize theme
    initTheme() {
        const savedTheme = localStorage.getItem(CONFIG.STORAGE.THEME);
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = savedTheme || (prefersDark ? 'dark' : 'light');
        
        this.setTheme(theme);
        
        // Add theme toggle listener
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
    },
    
    // Set theme
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(CONFIG.STORAGE.THEME, theme);
        
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            const icon = themeToggle.querySelector('.icon');
            if (icon) {
                icon.textContent = theme === 'dark' ? '☀️' : '🌙';
            }
        }
    },
    
    // Toggle theme
    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    },
    
    // Show loading state
    showLoading(element) {
        if (element) {
            element.innerHTML = '<div class="loading">Loading...</div>';
        }
    },
    
    // Show empty state
    showEmpty(element, message = 'No data available') {
        if (element) {
            element.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <h3 class="empty-state-title">No Data</h3>
                    <p class="empty-state-description">${message}</p>
                </div>
            `;
        }
    },
    
    // Show error state
    showError(element, error = 'An error occurred') {
        if (element) {
            element.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⚠️</div>
                    <h3 class="empty-state-title">Error</h3>
                    <p class="empty-state-description">${error}</p>
                </div>
            `;
        }
    }
};

// Make UI globally available
window.UI = UI;
