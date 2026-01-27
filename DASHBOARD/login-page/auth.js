const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// Session check: redirect to dashboard if already authenticated
try {
    const user = JSON.parse(sessionStorage.getItem('user'));
    if (user) window.location.href = '/';
} catch(e) {}

// Tab switching
const show = id => {
    $$('.form').forEach(f => f.classList.remove('active'));
    const form = $(id);
    form.style.animation = 'none';
    form.offsetHeight;
    form.style.animation = '';
    form.classList.add('active');
    $$('.tab-btn').forEach(t => t.classList.remove('tab-btn--active'));
    const tab = document.querySelector(`.tab-btn[data-target="${id}"]`);
    if (tab) tab.classList.add('tab-btn--active');
    ['l-msg', 'r-msg'].forEach(m => { $(m).className = 'msg'; $(m).textContent = ''; });
};

// Real-time field validation
const checkField = async (inputId, fieldName) => {
    const input = $(inputId), value = input.value.trim();
    if (!value) { input.classList.remove('input-error'); return; }
    try {
        const res = await fetch('/api/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: fieldName, value })
        });
        const data = await res.json();
        input.classList.toggle('input-error', data.exists);
    } catch (e) { }
};

// Loading state
const setLoading = (btn, loading) => {
    btn.disabled = loading;
    if (loading) btn.classList.add('btn--loading');
    else btn.classList.remove('btn--loading');
};

// Messages
const showMsg = (el, type, text) => { el.className = `msg ${type}`; el.textContent = text; };

// Login
const login = async () => {
    const m = $('l-msg'), btn = document.querySelector('#login button[type="submit"]');
    showMsg(m, '', '');
    setLoading(btn, true);
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: $('l-email').value.trim(), password: $('l-pass').value })
        });
        const data = await res.json();
        if (data.ok) {
            showMsg(m, 'success', 'Success!');
            sessionStorage.setItem('user', JSON.stringify(data.user));
            window.location.href = '/';
        } else { showMsg(m, 'error', data.error); setLoading(btn, false); }
    } catch (e) { showMsg(m, 'error', 'Connection error'); setLoading(btn, false); }
};

// Register
const register = async () => {
    const m = $('r-msg'), btn = document.querySelector('#register button[type="submit"]');
    const org = $('r-org').value.trim(), name = $('r-name').value.trim();
    const email = $('r-email').value.trim(), pass = $('r-pass').value, pass2 = $('r-pass2').value;
    showMsg(m, '', '');

    if (org.length < 2) return showMsg(m, 'error', 'Organization must be at least 2 characters');
    if (name.length < 2) return showMsg(m, 'error', 'Name must be at least 2 characters');
    if (pass.length < 3) return showMsg(m, 'error', 'Password must be at least 3 characters');
    if (pass !== pass2) return showMsg(m, 'error', 'Passwords do not match');

    setLoading(btn, true);
    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ orgName: org, userName: name, email, password: pass })
        });
        const data = await res.json();
        if (data.ok) {
            showMsg(m, 'success', 'Registered!');
            sessionStorage.setItem('user', JSON.stringify(data.user));
            window.location.href = '/';
        } else { showMsg(m, 'error', data.error); setLoading(btn, false); }
    } catch (e) { showMsg(m, 'error', 'Connection error'); setLoading(btn, false); }
};

// Init events
document.addEventListener('DOMContentLoaded', () => {
    // Tabs
    $$('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => show(btn.dataset.target));
    });

    // Form submissions
    $('login').addEventListener('submit', e => { e.preventDefault(); login(); });
    $('register').addEventListener('submit', e => { e.preventDefault(); register(); });

    // Register field validation on blur
    $('r-org').addEventListener('blur', () => checkField('r-org', 'orgName'));
    $('r-name').addEventListener('blur', () => checkField('r-name', 'userName'));
    $('r-email').addEventListener('blur', () => checkField('r-email', 'email'));
});
