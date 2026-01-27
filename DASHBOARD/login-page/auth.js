(() => {
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

const showMsg = (el, type, text) => { el.className = `msg ${type}`; el.textContent = text; };

const setLoading = (btn, loading) => {
    btn.disabled = loading;
    btn.classList.toggle('btn--loading', loading);
};

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
    $$('.msg').forEach(m => { m.className = 'msg'; m.textContent = ''; });
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

// Common auth submit: fetch → handle ok/error → loading state
const submitAuth = async (formId, url, body, successText) => {
    const msg = document.querySelector(`#${formId} .msg`);
    const btn = document.querySelector(`#${formId} button[type="submit"]`);
    showMsg(msg, '', '');
    setLoading(btn, true);
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (data.ok) {
            showMsg(msg, 'success', successText);
            sessionStorage.setItem('user', JSON.stringify(data.user));
            window.loadPage('dashboard-page');
        } else { showMsg(msg, 'error', data.error); setLoading(btn, false); }
    } catch (e) { showMsg(msg, 'error', 'Connection error'); setLoading(btn, false); }
};

const validateRegister = (org, name, pass, pass2) => {
    if (org.length < 2) return 'Organization must be at least 2 characters';
    if (name.length < 2) return 'Name must be at least 2 characters';
    if (pass.length < 3) return 'Password must be at least 3 characters';
    if (pass !== pass2) return 'Passwords do not match';
    return null;
};

// Login
const login = () => submitAuth('login', '/api/login', {
    email: $('l-email').value.trim(),
    password: $('l-pass').value
}, 'Success!');

// Register
const register = () => {
    const org = $('r-org').value.trim(), name = $('r-name').value.trim();
    const email = $('r-email').value.trim(), pass = $('r-pass').value, pass2 = $('r-pass2').value;
    const error = validateRegister(org, name, pass, pass2);
    if (error) return showMsg($('r-msg'), 'error', error);
    submitAuth('register', '/api/register', { orgName: org, userName: name, email, password: pass }, 'Registered!');
};

// Events
$$('.tab-btn').forEach(btn => btn.addEventListener('click', () => show(btn.dataset.target)));
$('login').addEventListener('submit', e => { e.preventDefault(); login(); });
$('register').addEventListener('submit', e => { e.preventDefault(); register(); });
$('r-org').addEventListener('blur', () => checkField('r-org', 'orgName'));
$('r-name').addEventListener('blur', () => checkField('r-name', 'userName'));
$('r-email').addEventListener('blur', () => checkField('r-email', 'email'));
})();
