(async () => {
    try {
        const res = await fetch('/version.md');
        if (!res.ok) return;
        const text = (await res.text()).trimEnd();
        const lastLine = text.split('\n').pop().trim();
        const match = lastLine.match(/^(v[\d.]+)/);
        if (!match) return;
        const remote = match[1];
        const el = document.querySelector('.version');
        if (el && el.textContent.trim() !== remote) {
            el.textContent = remote;
        }
    } catch (_) {}
})();
