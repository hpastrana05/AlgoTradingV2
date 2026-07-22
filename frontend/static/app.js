// Global State Manager
const state = {
    signals: [],      // Dynamic signal definitions from API
    strategies: [],   // List of existing strategies
    chart: null,      // Chart.js instance
    editingFile: null, // Filename being edited, or null when creating
    lastResult: null,  // Latest backtest result
    comparisonRuns: [], // Pinned runs for ticker comparison
    livePollTimer: null,
    alertsPollTimer: null,
    alerts: []
};

const COMPARISON_COLORS = [
    '#6366f1', '#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6', '#22c55e', '#06b6d4', '#f97316'
];


// ==========================================================================
// TOAST NOTIFICATIONS HELPER
// ==========================================================================
function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    if (type === 'error') iconName = 'alert-triangle';
    
    toast.innerHTML = `
        <i data-lucide="${iconName}" class="toast-icon ${type}"></i>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-msg">${message}</div>
        </div>
    `;
    
    container.appendChild(toast);
    lucide.createIcons();
    
    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Show/Hide Spinner
function toggleLoading(show) {
    const spinner = document.getElementById('loading-spinner');
    if (show) {
        spinner.classList.remove('hidden');
    } else {
        spinner.classList.add('hidden');
    }
}

// ==========================================================================
// INITIALIZATION
// ==========================================================================
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize Lucide Icons
    lucide.createIcons();
    
    // Tab switching
    initTabs();
    
    // Load metadata and strategies
    await loadSignals();
    await loadStrategies();
    
    // Set up Creator dynamic behaviors
    initCreator();
    
    // Set up Backtest form execution
    document.getElementById('backtest-form').addEventListener('submit', runBacktest);
    document.getElementById('strategy-select').addEventListener('change', onStrategySelectChange);
    document.getElementById('btn-clear-comparison').addEventListener('click', clearComparison);
    document.getElementById('chart-compare-mode').addEventListener('change', () => {
        if (state.lastResult) {
            renderChart(state.lastResult);
        }
    });

    // Live trading panel
    initLivePanel();
    // Telegram alerts panel
    initAlertsPanel();
});

// Tab navigation handler
function initTabs() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    const tabInfo = {
        'backtest': {
            title: 'Backtest Panel',
            desc: 'Run historical simulations and analyze strategy performance.'
        },
        'live': {
            title: 'Live Trading',
            desc: 'Run a strategy 24/7 against Trading212 in Demo or Live mode.'
        },
        'alerts': {
            title: 'Telegram Alerts',
            desc: 'Watch strategies or price levels and get notified on Telegram.'
        },
        'creator': {
            title: 'Strategy Creator',
            desc: 'Configure entry/exit signal logic. Each signal computes its own indicators from OHLCV data.'
        },
        'strategies': {
            title: 'Saved Strategies',
            desc: 'Browse existing strategies config files in the workspace.'
        }
    };
    
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            // Toggle sidebar buttons active state
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Toggle tab content panes active state
            tabPanes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === `tab-${targetTab}`) {
                    pane.classList.add('active');
                }
            });
            
            // Update page header info
            if (tabInfo[targetTab]) {
                document.getElementById('current-tab-title').textContent = tabInfo[targetTab].title;
                document.getElementById('current-tab-desc').textContent = tabInfo[targetTab].desc;
            }
            
            // Refresh strategy list when opening Strategies tab
            if (targetTab === 'strategies') {
                renderStrategiesList();
            }
            if (targetTab === 'live') {
                refreshLiveStatus();
                refreshLiveLogs();
                startLivePolling();
            } else {
                stopLivePolling();
            }
            if (targetTab === 'alerts') {
                refreshTelegramStatus();
                refreshAlertsList();
                refreshAlertsMonitor();
                refreshAlertsLogs();
                startAlertsPolling();
            } else {
                stopAlertsPolling();
            }
        });
    });
}

// Fetch Signals Metadata from FastAPI
async function loadSignals() {
    try {
        const response = await fetch('/api/signals');
        if (!response.ok) throw new Error("Failed to fetch signals metadata");
        state.signals = await response.json();
    } catch (e) {
        showToast("Error loading signals", e.message, "error");
    }
}

// Fetch existing strategies list
async function loadStrategies() {
    try {
        const response = await fetch('/api/strategies');
        if (!response.ok) throw new Error("Failed to fetch strategies list");
        state.strategies = await response.json();
        populateStrategiesDropdown();
    } catch (e) {
        showToast("Error loading strategies", e.message, "error");
    }
}

// Populate backtest selection dropdown
function populateStrategiesDropdown() {
    const select = document.getElementById('strategy-select');
    select.innerHTML = '<option value="" disabled selected>Choose a strategy...</option>';

    const liveSelect = document.getElementById('live-strategy-select');
    if (liveSelect) {
        liveSelect.innerHTML = '<option value="" disabled selected>Choose a strategy...</option>';
    }

    const alertSelect = document.getElementById('alert-strategy-select');
    if (alertSelect) {
        alertSelect.innerHTML = '<option value="" disabled selected>Choose a strategy...</option>';
    }
    
    state.strategies.forEach(strat => {
        const option = document.createElement('option');
        option.value = strat.file_name;
        option.textContent = `${strat.config.name} (${strat.config.ticker_data})`;
        option.dataset.ticker = strat.config.ticker_data || '';
        select.appendChild(option);

        if (liveSelect) {
            const liveOpt = option.cloneNode(true);
            liveSelect.appendChild(liveOpt);
        }
        if (alertSelect) {
            const alertOpt = option.cloneNode(true);
            alertSelect.appendChild(alertOpt);
        }
    });
}

function onStrategySelectChange() {
    const select = document.getElementById('strategy-select');
    const option = select.options[select.selectedIndex];
    const tickerInput = document.getElementById('backtest-ticker');
    // Prefill override with strategy ticker only if user left it empty
    if (option && option.dataset.ticker && !tickerInput.value.trim()) {
        tickerInput.placeholder = `Default: ${option.dataset.ticker}`;
    }
}

// ==========================================================================
// BACKTEST ENGINE SIMULATION EXECUTION
// ==========================================================================
async function runBacktest(event) {
    event.preventDefault();
    toggleLoading(true);
    
    const strategyFile = document.getElementById('strategy-select').value;
    const capital = parseFloat(document.getElementById('backtest-capital').value);
    // convert percentage back to decimal rate (e.g. 0.1% -> 0.001)
    const commission = parseFloat(document.getElementById('backtest-commission').value) / 100;
    const riskPct = parseFloat(document.getElementById('backtest-risk').value);
    const period = document.getElementById('backtest-period').value;
    const interval = document.getElementById('backtest-interval').value;
    const ticker = document.getElementById('backtest-ticker').value.trim();
    
    if (!strategyFile) {
        showToast("Configuration Error", "Please select a strategy to backtest.", "error");
        toggleLoading(false);
        return;
    }
    
    try {
        const response = await fetch('/api/backtest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                strategy_file: strategyFile,
                capital: capital,
                commission: commission,
                risk_pct: riskPct,
                period: period || null,
                interval: interval || null,
                ticker: ticker || null
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const detail = errorData.detail;
            const message = Array.isArray(detail)
                ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
                : (detail || "Backtest execution failed");
            throw new Error(message);
        }
        
        const results = await response.json();
        if (!results.ticker) {
            throw new Error(
                "Server response missing ticker — restart the frontend API " +
                "(uvicorn frontend.main:app --reload) and hard-refresh the browser."
            );
        }
        state.lastResult = results;
        pinComparisonRun(results);

        showToast(
            "Backtest Completed",
            `${results.strategy_name} on ${results.ticker} [${results.interval}] (${results.period || 'default'}) finished.`,
            "success"
        );
        
        updateMetricCards(results);
        renderChart(results);
        renderTradeLog(results.trade_pairs);
        
    } catch (e) {
        showToast("Simulation Failed", e.message, "error");
    } finally {
        toggleLoading(false);
    }
}

function comparisonKey(run) {
    return `${run.ticker}|${run.interval}|${run.period}|${run.strategy_name || ''}`;
}

function pinComparisonRun(results) {
    const run = {
        id: Date.now(),
        strategy_name: results.strategy_name || '—',
        ticker: results.ticker || 'unknown',
        interval: results.interval || 'default',
        period: results.period || 'default',
        total_return_pct: results.total_return_pct,
        win_rate: results.win_rate,
        total_trades: results.total_trades,
        winning_trades: results.winning_trades,
        losing_trades: results.losing_trades,
        max_drawdown_pct: results.max_drawdown_pct,
        final_value: results.final_value,
        portfolio_history: results.portfolio_history || []
    };

    // Replace existing run for same ticker+interval+period+strategy, keep max 8
    const key = comparisonKey(run);
    state.comparisonRuns = state.comparisonRuns.filter(r => comparisonKey(r) !== key);
    state.comparisonRuns.push(run);
    if (state.comparisonRuns.length > 8) {
        state.comparisonRuns = state.comparisonRuns.slice(-8);
    }

    // Auto-enable overlay once we have multiple pinned runs
    const overlay = document.getElementById('chart-compare-mode');
    if (overlay && state.comparisonRuns.length > 1) {
        overlay.checked = true;
    }

    renderComparisonTable();
}

function clearComparison() {
    state.comparisonRuns = [];
    renderComparisonTable();
    if (state.lastResult) {
        renderChart(state.lastResult);
    }
    showToast("Comparison Cleared", "Pinned runs removed.", "info");
}

function renderComparisonTable() {
    const tbody = document.querySelector('#comparison-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (state.comparisonRuns.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state-row">
                <td colspan="10">
                    Run a backtest, change ticker/interval override, run again — rows pin here automatically.
                </td>
            </tr>
        `;
        return;
    }

    state.comparisonRuns.forEach((run, idx) => {
        const row = document.createElement('tr');
        const ret = run.total_return_pct;
        const color = COMPARISON_COLORS[idx % COMPARISON_COLORS.length];
        row.innerHTML = `
            <td>
                <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:6px;"></span>
                #${idx + 1}
            </td>
            <td><strong>${run.ticker}</strong></td>
            <td>${run.interval}</td>
            <td>${run.period}</td>
            <td>${run.strategy_name}</td>
            <td class="pnl-cell ${ret >= 0 ? 'positive' : 'negative'}">${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%</td>
            <td>${run.win_rate.toFixed(1)}%</td>
            <td>${run.total_trades} (${run.winning_trades}W/${run.losing_trades}L)</td>
            <td>${run.max_drawdown_pct.toFixed(2)}%</td>
            <td>$${run.final_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
        `;
        tbody.appendChild(row);
    });
}

// Updates UI metrics text content and colors
function updateMetricCards(results) {
    const pnl = results.total_pnl;
    const returnPct = results.total_return_pct;
    
    const pnlElem = document.getElementById('metric-pnl');
    const pnlPctElem = document.getElementById('metric-pnl-pct');
    
    pnlElem.textContent = `${pnl >= 0 ? '+' : ''}$${pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    pnlPctElem.textContent = `${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(2)}%`;
    
    // color trends based on profitability
    if (pnl >= 0) {
        pnlElem.className = "metric-value text-success";
        pnlPctElem.className = "metric-trend positive";
    } else {
        pnlElem.className = "metric-value text-danger";
        pnlPctElem.className = "metric-trend negative";
    }
    
    document.getElementById('metric-win-rate').textContent = `${results.win_rate.toFixed(2)}%`;
    document.getElementById('metric-trades-count').textContent = `${results.total_trades} trades (${results.winning_trades}W / ${results.losing_trades}L)`;
    
    document.getElementById('metric-drawdown').textContent = `${results.max_drawdown_pct.toFixed(2)}%`;
    document.getElementById('metric-final-val').textContent = `$${results.final_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    const tickerHint = document.getElementById('metric-ticker-used');
    if (tickerHint) {
        if (results.ticker) {
            const parts = [`Ticker: ${results.ticker}`];
            if (results.interval) parts.push(results.interval);
            if (results.period) parts.push(results.period);
            tickerHint.textContent = parts.join(' · ');
        } else {
            tickerHint.textContent = 'Cash + holdings value';
        }
    }
}

// Populates execution log table
function renderTradeLog(tradePairs) {
    const tbody = document.querySelector('#trade-log-table tbody');
    tbody.innerHTML = '';
    
    if (tradePairs.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state-row">
                <td colspan="8">No trades executed during the backtest period. Try adjusting entry/exit rules or selecting a different data period.</td>
            </tr>
        `;
        return;
    }
    
    tradePairs.forEach((tp, idx) => {
        const row = document.createElement('tr');
        const pnl = tp.pnl;
        const returnPct = tp.return_pct;
        const isLong = (tp.side || 'LONG') === 'LONG';
        const sideBadge = isLong
            ? '<span class="badge-side-buy">LONG</span>'
            : '<span class="badge-side-sell">SHORT</span>';
        const exitType = tp.exit_type || '';
        let exitBadge;
        if (exitType.startsWith('FORCE_') || exitType.startsWith('EOD_')) {
            exitBadge = '<span class="badge-exit-force">EOD / FORCE</span>';
        } else if (exitType.startsWith('SL_')) {
            exitBadge = '<span class="badge-exit-force">SL</span>';
        } else if (exitType.startsWith('TP_')) {
            exitBadge = '<span class="badge-exit-cover">TP</span>';
        } else if (isLong) {
            exitBadge = '<span class="badge-exit-sell">SELL</span>';
        } else {
            exitBadge = '<span class="badge-exit-cover">COVER</span>';
        }        
        row.innerHTML = `
            <td class="trade-pair-cell">#${idx + 1}</td>
            <td>${sideBadge}</td>
            <td>${formatTime(tp.buy_time)}</td>
            <td>$${tp.buy_price.toFixed(2)}</td>
            <td>${formatTime(tp.sell_time)} ${exitBadge}</td>
            <td>$${tp.sell_price.toFixed(2)}</td>
            <td class="pnl-cell ${pnl >= 0 ? 'positive' : 'negative'}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</td>
            <td class="pnl-cell ${returnPct >= 0 ? 'positive' : 'negative'}">${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(2)}%</td>
        `;
        tbody.appendChild(row);
    });
}

function formatTime(timeStr) {
    if (!timeStr) return '-';
    // Trim timezone offsets and milliseconds if present for shorter dates in table
    return timeStr.replace(/[-+]\d{2}:\d{2}$/, '').split('.')[0];
}

// Render chart using Chart.js — linear lines, no point markers
function renderChart(resultsOrHistory) {
    const canvas = document.getElementById('portfolioChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const overlayToggle = document.getElementById('chart-compare-mode');
    const compareMode = !!(overlayToggle && overlayToggle.checked && state.comparisonRuns.length > 1);

    if (state.chart) {
        state.chart.destroy();
    }

    const titleEl = document.getElementById('chart-title');
    let datasets = [];
    let labels = [];
    let tooltipHistory = null;

    if (compareMode) {
        titleEl.textContent = 'Comparison — Portfolio Returns';
        // Align all runs to normalized index (0..100%) of their own length
        const maxLen = Math.max(...state.comparisonRuns.map(r => r.portfolio_history.length));
        labels = Array.from({ length: maxLen }, (_, i) => {
            const pct = maxLen <= 1 ? 0 : (i / (maxLen - 1)) * 100;
            return `${pct.toFixed(0)}%`;
        });

        state.comparisonRuns.forEach((run, idx) => {
            const history = run.portfolio_history;
            if (!history.length) return;
            const initial = history[0].portfolio_value;
            const series = history.map(h => ((h.portfolio_value / initial) * 100) - 100);
            // Stretch shorter series to maxLen by last-value pad for chart alignment
            while (series.length < maxLen) {
                series.push(series[series.length - 1]);
            }
            datasets.push({
                label: `${run.ticker} · ${run.interval} · ${run.period} (${run.total_return_pct >= 0 ? '+' : ''}${run.total_return_pct.toFixed(1)}%)`,
                data: series,
                borderColor: COMPARISON_COLORS[idx % COMPARISON_COLORS.length],
                borderWidth: 2,
                backgroundColor: 'transparent',
                fill: false,
                tension: 0,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHitRadius: 8
            });
        });
    } else {
        const history = resultsOrHistory.portfolio_history || resultsOrHistory;
        tooltipHistory = history;
        if (resultsOrHistory.ticker) {
            const bits = [resultsOrHistory.ticker];
            if (resultsOrHistory.interval) bits.push(resultsOrHistory.interval);
            titleEl.textContent = `Portfolio Growth — ${bits.join(' · ')}`;
        } else {
            titleEl.textContent = 'Portfolio Growth Chart';
        }

        labels = history.map(h => formatTime(h.timestamp));
        const initialPortfolio = history[0].portfolio_value;
        const initialAsset = history[0].close_price;
        const normalizedPortfolio = history.map(h => ((h.portfolio_value / initialPortfolio) * 100) - 100);
        const normalizedAsset = history.map(h => ((h.close_price / initialAsset) * 100) - 100);

        datasets = [
            {
                label: 'Portfolio Return (%)',
                data: normalizedPortfolio,
                borderColor: '#6366f1',
                borderWidth: 2,
                backgroundColor: 'rgba(99, 102, 241, 0.06)',
                fill: true,
                tension: 0,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHitRadius: 8
            },
            {
                label: 'Buy & Hold (%)',
                data: normalizedAsset,
                borderColor: '#14b8a6',
                borderWidth: 1.5,
                borderDash: [5, 4],
                backgroundColor: 'transparent',
                fill: false,
                tension: 0,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHitRadius: 8
            }
        ];
    }

    state.chart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            elements: {
                point: { radius: 0 },
                line: { tension: 0 }
            },
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#f3f4f6',
                        font: { family: 'Plus Jakarta Sans', weight: '500' }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.95)',
                    titleColor: '#f3f4f6',
                    bodyColor: '#d1d5db',
                    borderColor: '#1f2937',
                    borderWidth: 1,
                    titleFont: { family: 'Outfit', weight: '600' },
                    bodyFont: { family: 'Plus Jakarta Sans' },
                    callbacks: {
                        label: function(context) {
                            if (compareMode || !tooltipHistory) {
                                return `${context.dataset.label}: ${context.parsed.y >= 0 ? '+' : ''}${context.parsed.y.toFixed(2)}%`;
                            }
                            const item = tooltipHistory[context.dataIndex];
                            const label = context.dataset.label;
                            if (label.includes('Portfolio')) {
                                return `Portfolio: $${item.portfolio_value.toFixed(2)} (${context.parsed.y >= 0 ? '+' : ''}${context.parsed.y.toFixed(2)}%)`;
                            }
                            return `Asset: $${item.close_price.toFixed(2)} (${context.parsed.y >= 0 ? '+' : ''}${context.parsed.y.toFixed(2)}%)`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(31, 41, 55, 0.4)' },
                    ticks: { color: '#9ca3af', font: { size: 10 }, maxTicksLimit: 12 },
                    title: compareMode ? {
                        display: true,
                        text: 'Progress through backtest',
                        color: '#9ca3af'
                    } : undefined
                },
                y: {
                    type: 'linear',
                    display: true,
                    title: {
                        display: true,
                        text: 'Cumulative Return (%)',
                        color: '#9ca3af',
                        font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' }
                    },
                    grid: { color: 'rgba(31, 41, 55, 0.6)' },
                    ticks: {
                        color: '#f3f4f6',
                        callback: function(value) { return value.toFixed(1) + '%'; }
                    }
                }
            }
        }
    });
}

// ==========================================================================
// STRATEGY CREATOR LOGIC (nested AND/OR support)
// ==========================================================================
function initCreator() {
    document.querySelectorAll('.rule-op-select').forEach(select => {
        select.addEventListener('change', (e) => {
            const ruleType = e.target.getAttribute('data-rule-type');
            onRuleOperatorChange(ruleType);
        });
    });

    document.getElementById('strategy-creator-form').addEventListener('submit', saveStrategy);
    document.getElementById('btn-cancel-edit').addEventListener('click', () => {
        resetCreatorForm();
        showToast("Edit Cancelled", "Switched back to creating a new strategy.", "info");
    });

    renderRuleBuilder('entry', null);
    renderRuleBuilder('exit', null);
    updateCreatorModeUI();
}

function updateCreatorModeUI() {
    const badge = document.getElementById('creator-mode-badge');
    const hint = document.getElementById('creator-edit-hint');
    const cancelBtn = document.getElementById('btn-cancel-edit');
    const saveLabel = document.getElementById('btn-save-strategy-label');

    if (state.editingFile) {
        badge.classList.remove('hidden');
        hint.classList.remove('hidden');
        cancelBtn.classList.remove('hidden');
        saveLabel.textContent = "Update Strategy";
    } else {
        badge.classList.add('hidden');
        hint.classList.add('hidden');
        cancelBtn.classList.add('hidden');
        saveLabel.textContent = "Save Strategy Config";
    }
    lucide.createIcons();
}

function resetCreatorForm() {
    state.editingFile = null;
    document.getElementById('strategy-creator-form').reset();
    document.getElementById('entry-rule-op').value = "SINGLE";
    document.getElementById('exit-rule-op').value = "SINGLE";
    renderRuleBuilder('entry', null);
    renderRuleBuilder('exit', null);
    updateCreatorModeUI();
}

function onRuleOperatorChange(ruleType) {
    const newOp = document.getElementById(`${ruleType}-rule-op`).value;
    const current = compileRuleConfig(ruleType);

    if (newOp === 'SINGLE') {
        let single = null;
        if (current) {
            if (current.type === 'AND' || current.type === 'OR') {
                single = current.signals[0] || null;
            } else {
                single = current;
            }
        }
        renderRuleBuilder(ruleType, single);
        return;
    }

    let preset = null;
    if (current) {
        if (current.type === 'AND' || current.type === 'OR') {
            preset = { type: newOp, signals: current.signals };
        } else {
            preset = { type: newOp, signals: [current] };
        }
    } else {
        preset = { type: newOp, signals: [null] };
    }
    renderRuleBuilder(ruleType, preset);
}

function renderRuleBuilder(ruleType, preset = null) {
    const opSelect = document.getElementById(`${ruleType}-rule-op`);
    const container = document.getElementById(`${ruleType}-signals-container`);
    container.innerHTML = '';

    let op = 'SINGLE';
    let children = [null];

    if (preset) {
        if (preset.type === 'AND' || preset.type === 'OR') {
            op = preset.type;
            children = preset.signals && preset.signals.length ? preset.signals : [null];
        } else {
            op = 'SINGLE';
            children = [preset];
        }
    }

    opSelect.value = op;

    if (op === 'SINGLE') {
        container.appendChild(createSignalNode(children[0], false));
        return;
    }

    const childrenList = document.createElement('div');
    childrenList.className = 'rule-children-list';
    container.appendChild(createRuleToolbar(childrenList));
    container.appendChild(childrenList);

    children.forEach(child => {
        childrenList.appendChild(createRuleNode(child, true));
    });

    lucide.createIcons();
}

function createRuleToolbar(childrenList) {
    const toolbar = document.createElement('div');
    toolbar.className = 'rule-toolbar';

    const addSignalBtn = document.createElement('button');
    addSignalBtn.type = 'button';
    addSignalBtn.className = 'btn btn-secondary btn-sm';
    addSignalBtn.innerHTML = '<i data-lucide="plus"></i> Add Signal';
    addSignalBtn.addEventListener('click', () => {
        childrenList.appendChild(createSignalNode(null, true));
        lucide.createIcons();
    });

    const addGroupBtn = document.createElement('button');
    addGroupBtn.type = 'button';
    addGroupBtn.className = 'btn btn-secondary btn-sm';
    addGroupBtn.innerHTML = '<i data-lucide="git-branch"></i> Add Group';
    addGroupBtn.addEventListener('click', () => {
        childrenList.appendChild(createGroupNode(null, true));
        lucide.createIcons();
    });

    toolbar.appendChild(addSignalBtn);
    toolbar.appendChild(addGroupBtn);
    return toolbar;
}

function createRuleNode(preset, removable = true) {
    if (preset && (preset.type === 'AND' || preset.type === 'OR')) {
        return createGroupNode(preset, removable);
    }
    return createSignalNode(preset, removable);
}

function createGroupNode(preset = null, removable = true) {
    const group = document.createElement('div');
    group.className = 'rule-node rule-group-node';

    const op = preset && (preset.type === 'AND' || preset.type === 'OR') ? preset.type : 'AND';
    const children = preset && preset.signals && preset.signals.length ? preset.signals : [null];
    group.dataset.op = op;

    const header = document.createElement('div');
    header.className = 'rule-node-header';
    header.innerHTML = `
        <div class="flex-align" style="gap: 10px;">
            <span class="rule-node-label">Group</span>
            <select class="rule-group-op" required>
                <option value="AND" ${op === 'AND' ? 'selected' : ''}>AND</option>
                <option value="OR" ${op === 'OR' ? 'selected' : ''}>OR</option>
            </select>
        </div>
        ${removable ? `
            <button type="button" class="icon-btn-danger btn-remove-rule-node" title="Remove group">
                <i data-lucide="x-circle"></i>
            </button>
        ` : ''}
    `;

    const childrenList = document.createElement('div');
    childrenList.className = 'rule-children-list';

    const toolbar = createRuleToolbar(childrenList);

    group.appendChild(header);
    group.appendChild(toolbar);
    group.appendChild(childrenList);

    children.forEach(child => {
        childrenList.appendChild(createRuleNode(child, true));
    });

    const opSelect = header.querySelector('.rule-group-op');
    opSelect.addEventListener('change', () => {
        group.dataset.op = opSelect.value;
    });

    if (removable) {
        header.querySelector('.btn-remove-rule-node').addEventListener('click', () => {
            group.remove();
        });
    }

    return group;
}

function fillSignalParams(paramsGrid, signalMeta, preset = null) {
    paramsGrid.innerHTML = '';

    const visibleParams = (signalMeta?.parameters || []).filter(
        (p) => p.name !== 'session_tz'
    );

    if (visibleParams.length > 0) {
        visibleParams.forEach(p => {
            const field = document.createElement('div');
            field.className = 'signal-param-field';

            let value = p.default !== null && p.default !== undefined ? p.default : '';
            if (preset && preset[p.name] !== undefined && preset[p.name] !== null) {
                value = Array.isArray(preset[p.name])
                    ? preset[p.name].join(',')
                    : preset[p.name];
            }

            const requiredAttr = p.required === false ? '' : 'required';

            field.innerHTML = `
                <label>${p.name}</label>
                <input type="text"
                       data-param-name="${p.name}"
                       data-param-type="${p.type}"
                       placeholder="${p.description}"
                       value="${value}"
                       ${requiredAttr}>
            `;
            paramsGrid.appendChild(field);
        });
    } else if (signalMeta) {
        paramsGrid.innerHTML = '<span class="input-hint">No configuration parameters required for this signal.</span>';
    }
}

function createSignalNode(preset = null, removable = false) {
    const row = document.createElement('div');
    row.className = 'rule-node rule-signal-node';

    const dropdownOptions = state.signals.map(s => {
        const selected = preset && preset.type === s.name ? 'selected' : '';
        return `<option value="${s.name}" ${selected}>${s.name}</option>`;
    }).join('');

    row.innerHTML = `
        <div class="rule-node-header">
            <div class="flex-align" style="gap: 10px; flex: 1;">
                <span class="rule-node-label">Signal</span>
                <select class="signal-type-select" required style="flex: 1; max-width: 280px;">
                    <option value="" disabled ${!(preset && preset.type) ? 'selected' : ''}>Select signal logic...</option>
                    ${dropdownOptions}
                </select>
            </div>
            ${removable ? `
                <button type="button" class="icon-btn-danger btn-remove-rule-node" title="Remove signal">
                    <i data-lucide="x-circle"></i>
                </button>
            ` : ''}
        </div>
        <div class="signal-params-grid"></div>
    `;

    const select = row.querySelector('.signal-type-select');
    const paramsGrid = row.querySelector('.signal-params-grid');

    select.addEventListener('change', () => {
        const signalMeta = state.signals.find(s => s.name === select.value);
        fillSignalParams(paramsGrid, signalMeta, null);
    });

    if (preset && preset.type) {
        const signalMeta = state.signals.find(s => s.name === preset.type);
        fillSignalParams(paramsGrid, signalMeta, preset);
    }

    if (removable) {
        row.querySelector('.btn-remove-rule-node').addEventListener('click', () => {
            row.remove();
        });
    }

    return row;
}

function populateRuleFromConfig(ruleType, rule) {
    renderRuleBuilder(ruleType, rule || null);
}

function loadStrategyIntoCreator(strat) {
    state.editingFile = strat.file_name;
    const cfg = strat.config;

    document.getElementById('strat-name').value = cfg.name || '';
    document.getElementById('strat-ticker-api').value = cfg.ticker_API || '';
    document.getElementById('strat-ticker-data').value = cfg.ticker_data || '';
    document.getElementById('strat-interval').value = cfg.interval || '1d';
    document.getElementById('strat-period').value = (cfg.period || '1y').toLowerCase();
    document.getElementById('strat-action').value = cfg.action || 'BUY';

    populateRuleFromConfig('entry', cfg.entry_rule);
    populateRuleFromConfig('exit', cfg.exit_rule);
    updateCreatorModeUI();

    document.querySelector('.nav-btn[data-tab="creator"]').click();
    showToast("Editing Strategy", `Loaded ${cfg.name} into the creator.`, "info");
}

async function saveStrategy(event) {
    event.preventDefault();
    toggleLoading(true);

    try {
        const entryRule = compileRuleConfig('entry');
        const exitRule = compileRuleConfig('exit');

        if (!entryRule || !exitRule) {
            throw new Error("Invalid signals configured in Entry or Exit rules.");
        }

        const payload = {
            name: document.getElementById('strat-name').value,
            ticker_API: document.getElementById('strat-ticker-api').value,
            ticker_data: document.getElementById('strat-ticker-data').value,
            interval: document.getElementById('strat-interval').value,
            period: document.getElementById('strat-period').value,
            action: document.getElementById('strat-action').value,
            entry_rule: entryRule,
            exit_rule: exitRule
        };

        const isEdit = Boolean(state.editingFile);
        const url = isEdit
            ? `/api/strategies/${encodeURIComponent(state.editingFile)}`
            : '/api/strategies';
        const method = isEdit ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to save strategy");
        }

        const result = await response.json();
        showToast(
            isEdit ? "Strategy Updated" : "Strategy Saved",
            `Strategy saved as ${result.file_name} successfully!`,
            "success"
        );

        resetCreatorForm();
        await loadStrategies();

    } catch (e) {
        showToast("Saving Failed", e.message, "error");
    } finally {
        toggleLoading(false);
    }
}

function compileRuleConfig(ruleType) {
    const op = document.getElementById(`${ruleType}-rule-op`).value;
    const container = document.getElementById(`${ruleType}-signals-container`);

    if (op === 'SINGLE') {
        const signalNode = container.querySelector(':scope > .rule-signal-node');
        return signalNode ? compileSignalNode(signalNode) : null;
    }

    const childrenList = container.querySelector(':scope > .rule-children-list');
    if (!childrenList) return null;

    const signals = [];
    let isValid = true;

    childrenList.querySelectorAll(':scope > .rule-node').forEach(node => {
        const compiled = compileRuleNode(node);
        if (!compiled) isValid = false;
        else signals.push(compiled);
    });

    if (!isValid || signals.length === 0) return null;
    return { type: op, signals };
}

function compileRuleNode(nodeEl) {
    if (nodeEl.classList.contains('rule-signal-node')) {
        return compileSignalNode(nodeEl);
    }

    if (nodeEl.classList.contains('rule-group-node')) {
        const op = nodeEl.querySelector('.rule-group-op').value;
        const childrenList = nodeEl.querySelector(':scope > .rule-children-list');
        const signals = [];
        let isValid = true;

        childrenList.querySelectorAll(':scope > .rule-node').forEach(child => {
            const compiled = compileRuleNode(child);
            if (!compiled) isValid = false;
            else signals.push(compiled);
        });

        if (!isValid || signals.length === 0) return null;
        return { type: op, signals };
    }

    return null;
}

function compileSignalNode(signalNode) {
    const typeSelect = signalNode.querySelector('.signal-type-select');
    if (!typeSelect || !typeSelect.value) return null;

    const signalObj = { type: typeSelect.value };

    signalNode.querySelectorAll('.signal-params-grid input').forEach(input => {
        const name = input.getAttribute('data-param-name');
        if (name === 'session_tz') return;
        const type = input.getAttribute('data-param-type');
        const rawVal = input.value.trim();
        if (!rawVal) return;

        if (type === 'array') {
            signalObj[name] = rawVal.split(',').map(v => Number(v.trim()));
        } else {
            signalObj[name] = rawVal.includes('.') ? parseFloat(rawVal) : parseInt(rawVal, 10);
        }
    });

    return signalObj;
}

// ==========================================================================
// SAVED STRATEGIES VIEW
// ==========================================================================
function renderStrategiesList() {
    const grid = document.getElementById('strategies-cards-grid');
    grid.innerHTML = '';

    if (state.strategies.length === 0) {
        grid.innerHTML = `
            <div class="loading-state">
                <i data-lucide="folder-x" style="width:48px;height:48px;color:var(--text-muted)"></i>
                <p>No strategies found in the workspace directory strategies/.</p>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    state.strategies.forEach(strat => {
        const card = document.createElement('div');
        card.className = 'card strat-list-card';

        const entryText = formatRulePreview(strat.config.entry_rule);
        const exitText = formatRulePreview(strat.config.exit_rule);

        card.innerHTML = `
            <div class="card-header justify-between">
                <div class="flex-align">
                    <i data-lucide="file-text"></i>
                    <h3>${strat.config.name}</h3>
                </div>
                <span class="badge-exit-sell" style="text-transform:uppercase">${strat.config.action}</span>
            </div>

            <div class="strat-card-meta">
                <div class="meta-item">
                    <span>Ticker</span>
                    <p>${strat.config.ticker_data}</p>
                </div>
                <div class="meta-item">
                    <span>Interval</span>
                    <p>${strat.config.interval}</p>
                </div>
                <div class="meta-item">
                    <span>Period</span>
                    <p>${strat.config.period || '—'}</p>
                </div>
            </div>

            <div class="strat-card-rules">
                <div class="rule-preview">
                    <i data-lucide="log-in" class="text-success"></i>
                    <span style="font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">Entry: ${entryText}</span>
                </div>
                <div class="rule-preview">
                    <i data-lucide="log-out" class="text-danger"></i>
                    <span style="font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">Exit: ${exitText}</span>
                </div>
            </div>

            <div class="strat-card-footer">
                <button type="button" class="btn btn-secondary btn-block btn-edit-strat" data-file="${strat.file_name}">
                    <i data-lucide="pencil"></i> Edit
                </button>
                <button type="button" class="btn btn-primary btn-block btn-load-strat" data-file="${strat.file_name}">
                    <i data-lucide="play-circle"></i> Backtest
                </button>
            </div>
        `;

        grid.appendChild(card);

        card.querySelector('.btn-edit-strat').addEventListener('click', () => {
            loadStrategyIntoCreator(strat);
        });

        card.querySelector('.btn-load-strat').addEventListener('click', () => {
            const dropdown = document.getElementById('strategy-select');
            dropdown.value = strat.file_name;
            onStrategySelectChange();
            document.querySelector('.nav-btn[data-tab="backtest"]').click();
            showToast("Strategy Loaded", `Loaded ${strat.config.name} into configuration panel.`, "success");
        });
    });

    lucide.createIcons();
}

function formatRulePreview(rule) {
    if (!rule) return 'None';
    if (rule.type === 'AND' || rule.type === 'OR') {
        const subList = (rule.signals || []).map(s => formatRulePreview(s)).join(', ');
        return `${rule.type}(${subList})`;
    }
    return rule.type;
}

// ==========================================================================
// LIVE TRADING PANEL
// ==========================================================================
function initLivePanel() {
    const form = document.getElementById('live-form');
    if (!form) return;

    form.addEventListener('submit', startLiveEngine);
    document.getElementById('btn-live-stop').addEventListener('click', stopLiveEngine);
    document.getElementById('btn-live-refresh').addEventListener('click', async () => {
        await refreshLiveStatus();
        await refreshLiveLogs();
    });
    document.getElementById('live-mode-select').addEventListener('change', onLiveModeChange);
    onLiveModeChange();
    refreshLiveStatus();
}

function onLiveModeChange() {
    const mode = document.getElementById('live-mode-select').value;
    const badge = document.getElementById('live-mode-badge');
    const warning = document.getElementById('live-warning');
    const isLive = mode === 'live';

    badge.textContent = isLive ? 'LIVE' : 'DEMO';
    badge.className = `mode-badge ${isLive ? 'mode-live' : 'mode-demo'}`;
    warning.classList.toggle('is-live', isLive);
    warning.textContent = isLive
        ? 'LIVE mode uses real money. Orders will be sent to Trading212 live.'
        : 'Demo uses paper trading credentials. Live places real orders on Trading212.';
}

function startLivePolling() {
    stopLivePolling();
    state.livePollTimer = setInterval(async () => {
        await refreshLiveStatus();
        await refreshLiveLogs();
    }, 4000);
}

function stopLivePolling() {
    if (state.livePollTimer) {
        clearInterval(state.livePollTimer);
        state.livePollTimer = null;
    }
}

function renderLiveStatus(status) {
    const running = !!status.running;
    const engineEl = document.getElementById('live-engine-state');
    const sinceEl = document.getElementById('live-engine-since');
    const nameEl = document.getElementById('live-strategy-name');
    const metaEl = document.getElementById('live-strategy-meta');
    const modeEl = document.getElementById('live-mode-label');
    const credsEl = document.getElementById('live-creds-label');
    const tickEl = document.getElementById('live-last-tick');
    const errEl = document.getElementById('live-last-error');
    const startBtn = document.getElementById('btn-live-start');
    const stopBtn = document.getElementById('btn-live-stop');
    const modeSelect = document.getElementById('live-mode-select');
    const stratSelect = document.getElementById('live-strategy-select');

    engineEl.textContent = running ? 'Running' : 'Stopped';
    engineEl.className = `metric-value ${running ? 'engine-running' : 'engine-stopped'}`;
    sinceEl.textContent = running
        ? `Since ${status.started_at || '—'}`
        : (status.stopped_at ? `Stopped ${status.stopped_at}` : 'Not running');

    nameEl.textContent = status.strategy_name || '—';
    if (status.ticker) {
        const apiPart = status.ticker_api
            ? `API ${status.ticker_api}`
            : 'API unset (no orders)';
        metaEl.textContent = `${status.ticker} · ${apiPart} · ${status.interval || '—'}`;
    } else {
        metaEl.textContent = 'Select a strategy to run';
    }

    modeEl.textContent = (status.mode || 'demo').toUpperCase();
    credsEl.textContent = status.has_credentials
        ? 'Credentials loaded'
        : 'Missing .env credentials';

    tickEl.textContent = status.last_tick_at || '—';
    if (status.last_error) {
        errEl.textContent = status.last_error;
        errEl.className = 'metric-subtext engine-error';
    } else {
        errEl.textContent = 'No errors';
        errEl.className = 'metric-subtext';
    }

    startBtn.disabled = running;
    stopBtn.disabled = !running;
    modeSelect.disabled = running;
    stratSelect.disabled = running;

    // Only sync the mode dropdown from the server while a run is active.
    // When idle, leave the user's Demo/Live choice alone.
    if (running && status.mode) {
        modeSelect.value = status.mode;
        onLiveModeChange();
    }
}

async function refreshLiveStatus() {
    try {
        const response = await fetch('/api/live/status');
        if (!response.ok) throw new Error('Failed to fetch live status');
        const status = await response.json();
        renderLiveStatus(status);
        return status;
    } catch (e) {
        console.error(e);
        return null;
    }
}

async function refreshLiveLogs() {
    const view = document.getElementById('live-log-view');
    if (!view) return;
    try {
        const response = await fetch('/api/live/logs?limit=150');
        if (!response.ok) throw new Error('Failed to fetch logs');
        const data = await response.json();
        const logs = data.logs || [];
        if (!logs.length) {
            view.textContent = 'Waiting for engine activity…';
            return;
        }
        view.textContent = logs.map(l => l.line || `${l.time} ${l.message}`).join('\n');
        view.scrollTop = view.scrollHeight;
    } catch (e) {
        console.error(e);
    }
}

async function startLiveEngine(event) {
    event.preventDefault();
    const strategyFile = document.getElementById('live-strategy-select').value;
    const mode = document.getElementById('live-mode-select').value;
    const isDemo = mode !== 'live';

    if (!strategyFile) {
        showToast('Configuration Error', 'Please select a strategy to run.', 'error');
        return;
    }

    if (!isDemo) {
        const ok = window.confirm(
            'Start in LIVE mode?\n\nThis can place real orders with real money on Trading212.'
        );
        if (!ok) return;
    }

    toggleLoading(true);
    try {
        const response = await fetch('/api/live/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                strategy_file: strategyFile,
                is_demo: isDemo
            })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to start engine');
        }
        renderLiveStatus(data);
        showToast(
            'Engine Started',
            `${data.strategy_name} running in ${data.mode.toUpperCase()} mode.`,
            'success'
        );
        startLivePolling();
        await refreshLiveLogs();
    } catch (e) {
        showToast('Start Failed', e.message, 'error');
    } finally {
        toggleLoading(false);
        lucide.createIcons();
    }
}

async function stopLiveEngine() {
    toggleLoading(true);
    try {
        const response = await fetch('/api/live/stop', { method: 'POST' });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to stop engine');
        }
        renderLiveStatus(data);
        showToast('Engine Stopped', 'Live trading loop has been stopped.', 'info');
        await refreshLiveLogs();
    } catch (e) {
        showToast('Stop Failed', e.message, 'error');
    } finally {
        toggleLoading(false);
        lucide.createIcons();
    }
}

// Alerts panel lives in alerts_panel.js (loaded after this file).

