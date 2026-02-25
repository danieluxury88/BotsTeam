// Calendar page logic

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

let allEvents = [];
let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth(); // 0-indexed
let selectedDate = null;

// Filter state
let filterScope = '';
let filterProject = '';
let filterType = '';

async function initCalendar() {
    UI.initTheme();

    document.getElementById('refresh-btn').addEventListener('click', () => loadCalendar());
    document.getElementById('cal-prev').addEventListener('click', () => navigateMonth(-1));
    document.getElementById('cal-next').addEventListener('click', () => navigateMonth(1));
    document.getElementById('cal-scope').addEventListener('change', e => { filterScope = e.target.value; renderMonth(); });
    document.getElementById('cal-project').addEventListener('change', e => { filterProject = e.target.value; renderMonth(); });
    document.getElementById('cal-type').addEventListener('change', e => { filterType = e.target.value; renderMonth(); });
    document.getElementById('cal-detail-close').addEventListener('click', closeDetail);

    await loadCalendar();
}

async function loadCalendar() {
    const [calData, projectsData] = await Promise.all([
        API.getBots().then(() => API.getCalendar()),
        API.getProjects(),
    ]);

    allEvents = (calData && calData.events) ? calData.events : [];

    populateFilters(calData, projectsData);
    renderMonth();
}

function populateFilters(calData, projectsData) {
    // Project filter
    const projectSel = document.getElementById('cal-project');
    const projectIds = [...new Set(allEvents.map(e => e.project_id).filter(Boolean))];
    const projects = (projectsData && projectsData.projects) ? projectsData.projects : [];
    projectSel.innerHTML = '<option value="">All Projects</option>' +
        projectIds.map(id => {
            const proj = projects.find(p => p.id === id);
            const name = proj ? proj.name : id;
            return `<option value="${Utils.escapeHtml(id)}">${Utils.escapeHtml(name)}</option>`;
        }).join('');

    // Event type filter
    const typeSel = document.getElementById('cal-type');
    const types = (calData && calData.event_types) ? calData.event_types : [];
    typeSel.innerHTML = '<option value="">All Events</option>' +
        types.map(type => {
            const meta = (CONFIG.CALENDAR_EVENT_TYPES || {})[type] || { label: type, icon: '📋' };
            return `<option value="${Utils.escapeHtml(type)}">${meta.icon} ${Utils.escapeHtml(meta.label)}</option>`;
        }).join('');
}

function navigateMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 11) { currentMonth = 0; currentYear++; }
    if (currentMonth < 0)  { currentMonth = 11; currentYear--; }
    selectedDate = null;
    closeDetail();
    renderMonth();
}

function getFilteredEvents() {
    return allEvents.filter(e => {
        if (filterScope && e.scope !== filterScope) return false;
        if (filterProject && e.project_id !== filterProject) return false;
        if (filterType && e.type !== filterType) return false;
        return true;
    });
}

function renderMonth() {
    document.getElementById('cal-heading').textContent =
        `${MONTH_NAMES[currentMonth]} ${currentYear}`;

    const grid = document.getElementById('calendar-grid');
    const today = new Date();
    const todayStr = isoDate(today.getFullYear(), today.getMonth(), today.getDate());

    // First day of month (0=Sun … 6=Sat). Convert to Mon-first (0=Mon … 6=Sun).
    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    const leadingBlanks = (firstDay + 6) % 7; // Mon-first offset
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

    const filtered = getFilteredEvents();

    // Build event lookup: date → events[]
    const eventsByDate = {};
    for (const ev of filtered) {
        if (!eventsByDate[ev.date]) eventsByDate[ev.date] = [];
        eventsByDate[ev.date].push(ev);
    }

    let html = '';

    // Weekday headers
    for (const day of WEEKDAYS) {
        html += `<div class="calendar-weekday">${day}</div>`;
    }

    // Leading empty cells
    for (let i = 0; i < leadingBlanks; i++) {
        html += `<div class="calendar-day-empty"></div>`;
    }

    // Day cells
    for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = isoDate(currentYear, currentMonth, d);
        const events = eventsByDate[dateStr] || [];
        const isToday = dateStr === todayStr;
        const isSelected = dateStr === selectedDate;

        let classes = 'calendar-day';
        if (isToday) classes += ' calendar-day-today';
        if (isSelected) classes += ' calendar-day-selected';

        const maxBadges = 3;
        const badges = events.slice(0, maxBadges).map(e => renderEventBadge(e)).join('');
        const more = events.length > maxBadges
            ? `<span class="cal-event-more">+${events.length - maxBadges} more</span>`
            : '';

        html += `
            <div class="${classes}" data-date="${dateStr}" role="gridcell"
                 aria-label="${MONTH_NAMES[currentMonth]} ${d}${events.length ? `, ${events.length} events` : ''}"
                 onclick="openDayDetail('${dateStr}')">
                <span class="calendar-day-number">${d}</span>
                ${badges}
                ${more}
            </div>`;
    }

    grid.innerHTML = html;
}

function isoDate(year, month, day) {
    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function renderEventBadge(event) {
    const colorClass = `cal-color-${Utils.escapeHtml(event.color || event.type)}`;
    const title = Utils.escapeHtml(event.title || event.type);
    return `<span class="cal-event-badge ${colorClass}" title="${title}">${title}</span>`;
}

function openDayDetail(dateStr) {
    selectedDate = dateStr;
    renderMonth(); // refresh selected state

    const events = getFilteredEvents().filter(e => e.date === dateStr);
    const detail = document.getElementById('calendar-detail');
    const heading = document.getElementById('cal-detail-heading');
    const list = document.getElementById('cal-detail-list');

    // Parse date for display
    const [year, month, day] = dateStr.split('-').map(Number);
    heading.textContent = `${MONTH_NAMES[month - 1]} ${day}, ${year} — ${events.length} event${events.length !== 1 ? 's' : ''}`;

    if (events.length === 0) {
        list.innerHTML = '<p class="text-secondary">No events on this day.</p>';
    } else {
        list.innerHTML = events.map(e => renderDetailEvent(e)).join('');
    }

    detail.hidden = false;
    detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderDetailEvent(event) {
    if (event.type === 'report_run') {
        // Reuse the existing report item component where possible
        const report = {
            bot: event.meta.bot,
            project_name: event.project_id,
            project_id: event.project_id,
            timestamp: event.date,
            status: event.meta.status,
            summary: event.meta.summary,
            path: event.meta.path,
            scope: event.scope,
        };
        return Components.renderReportItem(report);
    }

    // Generic fallback for future event types
    const typeInfo = (CONFIG.CALENDAR_EVENT_TYPES || {})[event.type] || { icon: '📋', label: event.type };
    const colorClass = `cal-color-${Utils.escapeHtml(event.color || event.type)}`;
    return `
        <div class="report-item">
            <div class="report-status">
                <span class="cal-event-badge ${colorClass}">${typeInfo.icon}</span>
            </div>
            <div class="report-content">
                <div class="report-title">${Utils.escapeHtml(event.title)}</div>
                <div class="report-meta">
                    <span>${Utils.escapeHtml(event.project_id)}</span>
                    <span>${Utils.escapeHtml(typeInfo.label)}</span>
                </div>
            </div>
        </div>`;
}

function closeDetail() {
    document.getElementById('calendar-detail').hidden = true;
    selectedDate = null;
    renderMonth();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCalendar);
} else {
    initCalendar();
}
