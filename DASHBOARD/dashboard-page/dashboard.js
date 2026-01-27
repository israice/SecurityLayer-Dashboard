(() => {
const $ = id => document.getElementById(id);
const esc = t => Object.assign(document.createElement('div'), {textContent: t}).innerHTML;

// ==================== Session Check ====================

let currentUser = null;
try {
    currentUser = JSON.parse(sessionStorage.getItem('user'));
    if (!currentUser) {
        window.loadPage('landing-page');
    } else {
        $('org-name').textContent = currentUser.ORG_NAME || '';
    }
} catch(e) {
    sessionStorage.clear();
    window.loadPage('landing-page');
}

// ==================== Logout ====================

const logout = () => {
    stopSSE();
    sessionStorage.clear();
    window.loadPage('landing-page');
};

// ==================== Table Rendering ====================

let tableData = { headers: [], rows: [] }, sortCol = 0, sortAsc = false;

const render = () => {
    const rows = [...tableData.rows];
    if (sortCol >= 0) rows.sort((a, b) => {
        const [x, y] = [a[sortCol], b[sortCol]];
        const cmp = isNaN(x) || isNaN(y) ? x.localeCompare(y) : x - y;
        return sortAsc ? cmp : -cmp;
    });
    $('table-head').innerHTML = `<tr>${tableData.headers.map((h, i) =>
        `<th onclick="window._dashSort(${i})">${esc(h)} <span style="opacity:${sortCol === i ? 1 : 0}">${sortAsc ? '▲' : '▼'}</span></th>`
    ).join('')}</tr>`;
    $('table-body').innerHTML = rows.map(r =>
        `<tr>${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`
    ).join('');
};

window._dashSort = i => { sortAsc = sortCol === i ? !sortAsc : false; sortCol = i; render(); };

// ==================== SSE Connection ====================

let sseConnection = null;
let sseReconnectTimer = null;

const startSSE = () => {
    if (sseConnection) return;
    const es = new EventSource('/sse');
    sseConnection = es;
    es.onopen = () => {
        $('status').className = 'status connected';
        $('status').textContent = new Date().toLocaleTimeString('ru');
    };
    es.onmessage = e => {
        tableData = JSON.parse(e.data);
        const empty = !tableData.headers.length;
        $('data-table').style.display = empty ? 'none' : 'table';
        $('empty-message').style.display = empty ? 'block' : 'none';
        if (!empty) render();
        $('status').textContent = new Date().toLocaleTimeString('ru');
    };
    es.onerror = () => {
        $('status').className = 'status disconnected';
        $('status').textContent = 'Reconnecting...';
        es.close();
        sseConnection = null;
        sseReconnectTimer = setTimeout(startSSE, 3000);
    };
};

const stopSSE = () => {
    if (sseReconnectTimer) { clearTimeout(sseReconnectTimer); sseReconnectTimer = null; }
    if (sseConnection) { sseConnection.close(); sseConnection = null; }
};

// ==================== Init ====================

$('btn-logout').addEventListener('click', logout);
startSSE();
})();
