document.addEventListener('DOMContentLoaded', () => {
    const selector = document.getElementById('id_application');
    if (!selector || !selector.dataset.previewUrl) return;
    let pending;
    selector.addEventListener('change', async () => {
        if (pending) pending.abort();
        for (const name of ['full_name', 'primary_email', 'role_title', 'engagement_type']) {
            document.getElementById(`id_${name}`).value = '';
        }
        if (!selector.value) return;
        pending = new AbortController();
        const selected = selector.value;
        try {
            const url = new URL(selector.dataset.previewUrl, window.location.origin);
            url.searchParams.set('application', selected);
            const response = await fetch(url, {signal: pending.signal, cache: 'no-store'});
            if (!response.ok) throw new Error('Application unavailable');
            const fields = await response.json();
            if (selector.value !== selected) return;
            for (const [name, value] of Object.entries(fields)) {
                document.getElementById(`id_${name}`).value = value;
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                window.alert('Could not load this application. Select it again before saving.');
            }
        }
    });
});
