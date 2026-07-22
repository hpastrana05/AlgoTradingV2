
// ==========================================================================
// TELEGRAM ALERTS PANEL
// ==========================================================================
function initAlertsPanel() {
    const telegramForm = document.getElementById('telegram-form');
    const alertForm = document.getElementById('alert-create-form');
    if (!telegramForm || !alertForm) return;

    telegramForm.addEventListener('submit', saveTelegramConfig);
    document.getElementById('btn-telegram-test').addEventListener('click', testTelegram);
    document.getElementById('btn-alerts-start').addEventListener('click', startAlertsMonitor);
    document.getElementById('btn-alerts-stop').addEventListener('click', stopAlertsMonitor);
    document.getElementById('btn-alerts-refresh').addEventListener('click', async () => {
        await refreshTelegramStatus();
        await refreshAlertsList();
        await refreshAlertsMonitor();
        await refreshAlertsLogs();
    });
    alertForm.addEventListener('submit', createAlert);
    document.getElementById('alert-type').addEventListener('change', onAlertTypeChange);
    onAlertTypeChange();
    refreshTelegramStatus();
}

function onAlertTypeChange() {
    const type = document.getElementById('alert-type').value;
    document.getElementById('alert-strategy-fields').classList.toggle('hidden', type !== 'strategy');
    document.getElementById('alert-price-fields').classList.toggle('hidden', type !== 'price');
}

function startAlertsPolling() {
    stopAlertsPolling();
    state.alertsPollTimer = setInterval(async () => {
        await refreshAlertsMonitor();
        await refreshAlertsLogs();
        await refreshAlertsList();
    }, 5000);
}

function stopAlertsPolling() {
    if (state.alertsPollTimer) {
        clearInterval(state.alertsPollTimer);
        state.alertsPollTimer = null;
    }
}

async function refreshTelegramStatus() {
    try {
        const response = await fetch('/api/telegram/status');
        if (!response.ok) throw new Error('Failed to load Telegram status');
        const status = await response.json();
        const badge = document.getElementById('telegram-status-badge');
        const chatInput = document.getElementById('telegram-chat-id');
        const hint = document.getElementById('telegram-hint');

        badge.textContent = status.configured ? 'READY' : 'NOT SET';
        badge.className = `mode-badge ${status.configured ? 'mode-demo' : 'mode-live'}`;
        if (status.chat_id && !chatInput.value) {
            chatInput.value = status.chat_id;
        }
        hint.textContent = status.configured
            ? `Configured (${status.source}). Token: ${status.token_masked || '—'}.`
            : 'Create a bot with @BotFather, then get your chat id (e.g. @userinfobot). You can also set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.';
    } catch (e) {
        showToast('Telegram', e.message, 'error');
    }
}

async function saveTelegramConfig(event) {
    event.preventDefault();
    const botToken = document.getElementById('telegram-bot-token').value.trim();
    const chatId = document.getElementById('telegram-chat-id').value.trim();
    const body = {};
    if (botToken) body.bot_token = botToken;
    if (chatId) body.chat_id = chatId;

    if (!botToken && !chatId) {
        showToast('Telegram', 'Enter a bot token and/or chat id.', 'error');
        return;
    }

    toggleLoading(true);
    try {
        const response = await fetch('/api/telegram/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Save failed');
        document.getElementById('telegram-bot-token').value = '';
        showToast('Telegram', 'Bot settings saved.', 'success');
        await refreshTelegramStatus();
    } catch (e) {
        showToast('Telegram', e.message, 'error');
    } finally {
        toggleLoading(false);
    }
}

async function testTelegram() {
    toggleLoading(true);
    try {
        const response = await fetch('/api/telegram/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: 'AlgoTrading V2: Telegram connected.' })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Test failed');
        showToast('Telegram', 'Test message sent.', 'success');
    } catch (e) {
        showToast('Telegram', e.message, 'error');
    } finally {
        toggleLoading(false);
    }
}

async function refreshAlertsList() {
    try {
        const response = await fetch('/api/alerts');
        if (!response.ok) throw new Error('Failed to load alerts');
        const data = await response.json();
        state.alerts = data.alerts || [];
        renderAlertsList();
    } catch (e) {
        showToast('Alerts', e.message, 'error');
    }
}

function renderAlertsList() {
    const container = document.getElementById('alerts-list');
    if (!container) return;

    if (!state.alerts.length) {
        container.innerHTML = '<div class="loading-state"><p>No alerts yet. Create one above.</p></div>';
        return;
    }

    container.innerHTML = state.alerts.map(alert => {
        const enabledBadge = alert.enabled
            ? '<span class="alert-badge on">On</span>'
            : '<span class="alert-badge off">Off</span>';
        const typeBadge = `<span class="alert-badge ${alert.type}">${alert.type}</span>`;
        let detail = '';
        if (alert.type === 'strategy') {
            const notify = (alert.notify_on || []).join(', ') || 'entry, exit';
            const tickers = (alert.tickers && alert.tickers.length)
                ? alert.tickers.join(', ')
                : 'default ticker';
            detail = `Strategy: ${alert.strategy_file} · Tickers: ${tickers} · Notify: ${notify}`;
        } else {
            const tickers = (alert.tickers && alert.tickers.length)
                ? alert.tickers.join(', ')
                : (alert.ticker || '—');
            detail = `${tickers} ${alert.condition} ${alert.price} · ${alert.interval}` +
                (alert.once ? ' · once' : ' · repeat');
        }
        const last = alert.last_triggered_at
            ? `Last trigger: ${alert.last_triggered_at}`
            : 'Not triggered yet';
        const err = alert.last_error ? `<br><span class="engine-error">${escapeHtml(alert.last_error)}</span>` : '';

        return `
            <div class="alert-card" data-id="${alert.id}">
                <div>
                    <div class="alert-card-title">${typeBadge}${enabledBadge}${escapeHtml(alert.name)}</div>
                    <div class="alert-card-meta">${escapeHtml(detail)}<br>${escapeHtml(last)}${err}</div>
                </div>
                <div class="alert-card-actions">
                    <button type="button" class="btn btn-secondary btn-sm" data-action="toggle">
                        ${alert.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button type="button" class="btn btn-secondary btn-sm" data-action="delete">
                        Delete
                    </button>
                </div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('.alert-card').forEach(card => {
        const id = card.getAttribute('data-id');
        card.querySelector('[data-action="toggle"]').addEventListener('click', () => toggleAlert(id));
        card.querySelector('[data-action="delete"]').addEventListener('click', () => deleteAlert(id));
    });
}

function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

async function createAlert(event) {
    event.preventDefault();
    const name = document.getElementById('alert-name').value.trim();
    const type = document.getElementById('alert-type').value;
    const payload = { name, type, enabled: true };

    if (type === 'strategy') {
        const strategyFile = document.getElementById('alert-strategy-select').value;
        if (!strategyFile) {
            showToast('Alerts', 'Select a strategy.', 'error');
            return;
        }
        const notifyOn = [];
        if (document.getElementById('alert-notify-entry').checked) notifyOn.push('entry');
        if (document.getElementById('alert-notify-exit').checked) notifyOn.push('exit');
        if (!notifyOn.length) {
            showToast('Alerts', 'Select at least Entry or Exit.', 'error');
            return;
        }
        payload.strategy_file = strategyFile;
        payload.notify_on = notifyOn;
        const rawTickers = document.getElementById('alert-strategy-tickers').value.trim();
        if (rawTickers) {
            payload.tickers = rawTickers.split(/[,;\s]+/).map(t => t.trim()).filter(Boolean);
        }
    } else {
        const rawTickers = document.getElementById('alert-ticker').value.trim();
        const tickers = rawTickers.split(/[,;\s]+/).map(t => t.trim()).filter(Boolean);
        const price = parseFloat(document.getElementById('alert-price').value);
        if (!tickers.length || Number.isNaN(price)) {
            showToast('Alerts', 'At least one ticker and a price are required.', 'error');
            return;
        }
        payload.tickers = tickers;
        payload.ticker = tickers[0];
        payload.condition = document.getElementById('alert-condition').value;
        payload.price = price;
        payload.interval = document.getElementById('alert-interval').value;
        payload.once = document.getElementById('alert-once').checked;
    }

    toggleLoading(true);
    try {
        const response = await fetch('/api/alerts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Create failed');
        document.getElementById('alert-name').value = '';
        showToast('Alerts', `Created "${data.name}".`, 'success');
        await refreshAlertsList();
        await refreshAlertsMonitor();
    } catch (e) {
        showToast('Alerts', e.message, 'error');
    } finally {
        toggleLoading(false);
        lucide.createIcons();
    }
}

async function toggleAlert(id) {
    const alert = state.alerts.find(a => a.id === id);
    if (!alert) return;
    try {
        const response = await fetch(`/api/alerts/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: !alert.enabled })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Update failed');
        await refreshAlertsList();
        await refreshAlertsMonitor();
    } catch (e) {
        showToast('Alerts', e.message, 'error');
    }
}

async function deleteAlert(id) {
    if (!window.confirm('Delete this alert?')) return;
    try {
        const response = await fetch(`/api/alerts/${id}`, { method: 'DELETE' });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Delete failed');
        await refreshAlertsList();
        await refreshAlertsMonitor();
    } catch (e) {
        showToast('Alerts', e.message, 'error');
    }
}

function renderAlertsMonitor(status) {
    const running = !!status.running;
    const engineEl = document.getElementById('alerts-engine-state');
    const sinceEl = document.getElementById('alerts-engine-since');
    const badge = document.getElementById('alerts-monitor-badge');
    const startBtn = document.getElementById('btn-alerts-start');
    const stopBtn = document.getElementById('btn-alerts-stop');

    engineEl.textContent = running ? 'Running' : 'Stopped';
    engineEl.className = `metric-value ${running ? 'engine-running' : 'engine-stopped'}`;
    sinceEl.textContent = running
        ? `Since ${status.started_at || '—'}`
        : (status.stopped_at ? `Stopped ${status.stopped_at}` : 'Not running');

    badge.textContent = running ? 'RUNNING' : 'STOPPED';
    badge.className = `mode-badge ${running ? 'mode-demo' : 'mode-live'}`;

    document.getElementById('alerts-enabled-count').textContent = status.enabled_alerts ?? 0;
    document.getElementById('alerts-total-count').textContent = `${status.total_alerts ?? 0} total`;
    document.getElementById('alerts-messages-sent').textContent = status.messages_sent ?? 0;
    document.getElementById('alerts-last-tick').textContent = `Last tick: ${status.last_tick_at || '—'}`;
    document.getElementById('alerts-poll-seconds').textContent = `${status.poll_seconds || 60}s`;

    const errEl = document.getElementById('alerts-last-error');
    if (status.last_error) {
        errEl.textContent = status.last_error;
        errEl.className = 'metric-subtext engine-error';
    } else {
        errEl.textContent = 'No errors';
        errEl.className = 'metric-subtext';
    }

    startBtn.disabled = running;
    stopBtn.disabled = !running;
}

async function refreshAlertsMonitor() {
    try {
        const response = await fetch('/api/alerts/monitor/status');
        if (!response.ok) throw new Error('Failed to fetch monitor status');
        const status = await response.json();
        renderAlertsMonitor(status);
        return status;
    } catch (e) {
        console.error(e);
    }
}

async function refreshAlertsLogs() {
    try {
        const response = await fetch('/api/alerts/monitor/logs?limit=120');
        if (!response.ok) return;
        const data = await response.json();
        const view = document.getElementById('alerts-log-view');
        const lines = (data.logs || []).map(l => l.line || l.message).join('\n');
        view.textContent = lines || 'Waiting for monitor activity…';
        view.scrollTop = view.scrollHeight;
    } catch (e) {
        console.error(e);
    }
}

async function startAlertsMonitor() {
    toggleLoading(true);
    try {
        const response = await fetch('/api/alerts/monitor/start', { method: 'POST' });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Failed to start monitor');
        renderAlertsMonitor(data);
        showToast('Alerts', 'Monitor started. Watching enabled alerts.', 'success');
        startAlertsPolling();
        await refreshAlertsLogs();
    } catch (e) {
        showToast('Alerts', e.message, 'error');
    } finally {
        toggleLoading(false);
        lucide.createIcons();
    }
}

async function stopAlertsMonitor() {
    toggleLoading(true);
    try {
        const response = await fetch('/api/alerts/monitor/stop', { method: 'POST' });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Failed to stop monitor');
        renderAlertsMonitor(data);
        showToast('Alerts', 'Monitor stopped.', 'info');
        await refreshAlertsLogs();
    } catch (e) {
        showToast('Alerts', e.message, 'error');
    } finally {
        toggleLoading(false);
        lucide.createIcons();
    }
}
