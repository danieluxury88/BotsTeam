// Configuration and constants
const CONFIG = {
    // API endpoints (relative to dashboard root)
    API: {
        DASHBOARD: 'data/dashboard.json',
        PROJECTS: 'data/projects.json',
        REPORTS_INDEX: 'data/index.json',
        BOTS: 'data/bots.json',
        CALENDAR: 'data/calendar.json',
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
    
    // Calendar event type metadata (extend as new sources are added)
    CALENDAR_EVENT_TYPES: {
        report_run:    { label: 'Bot Reports',  icon: '🤖' },
        issue_due:     { label: 'Issue Due',     icon: '📌' },
        issue_created: { label: 'Issue Created', icon: '🆕' },
        commit:        { label: 'Commits',       icon: '📝' },
        journal_entry: { label: 'Journal',       icon: '📓' },
        task:          { label: 'Task',          icon: '✅' },
    },

    // CSS color class suffixes for calendar event badges (matches .cal-color-{key})
    CALENDAR_COLORS: {
        gitbot:      '#3498db',
        qabot:       '#27ae60',
        pmbot:       '#9b59b6',
        journalbot:  '#f39c12',
        taskbot:     '#e67e22',
        habitbot:    '#e74c3c',
        orchestrator:'#95a5a6',
    },

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
