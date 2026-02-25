// Configuration and constants
const CONFIG = {
    // API endpoints (relative to dashboard root)
    API: {
        DASHBOARD: 'data/dashboard.json',
        PROJECTS: 'data/projects.json',
        REPORTS_INDEX: 'data/index.json',
        BOTS: 'data/bots.json',
        PROJECTS_API: '/api/projects'
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
    
    // Bot configuration — loaded at runtime from data/bots.json (generated from shared/bot_registry.py).
    // Pages call API.getBots() at init and set CONFIG.BOTS = await API.getBots().
    BOTS: [],
    
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
