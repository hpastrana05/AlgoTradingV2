// Global State Manager
const state = {
    signals: [],      // Dynamic signal definitions from API
    strategies: [],   // List of existing strategies
    chart: null,      // Chart.js instance
    editingFile: null // Filename being edited, or null when creating
};

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
        'creator': {
            title: 'Strategy Creator',
            desc: 'Configure entry/exit signal logic. Indicators are derived automatically from your rules.'
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
    
    state.strategies.forEach(strat => {
        const option = document.createElement('option');
        option.value = strat.file_name;
        option.textContent = `${strat.config.name} (${strat.config.ticker_data})`;
        select.appendChild(option);
    });
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
    const period = document.getElementById('backtest-period').value;
    
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
                period: period || null
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Backtest execution failed");
        }
        
        const results = await response.json();
        showToast("Backtest Completed", `Simulation completed successfully for ${results.strategy_name}!`, "success");
        
        // Update metric UI cards
        updateMetricCards(results);
        
        // Render portfolio performance graph
        renderChart(results.portfolio_history);
        
        // Populate execution log table
        renderTradeLog(results.trade_pairs);
        
    } catch (e) {
        showToast("Simulation Failed", e.message, "error");
    } finally {
        toggleLoading(false);
    }
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
}

// Populates execution log table
function renderTradeLog(tradePairs) {
    const tbody = document.querySelector('#trade-log-table tbody');
    tbody.innerHTML = '';
    
    if (tradePairs.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state-row">
                <td colspan="7">No trades executed during the backtest period. Try adjusting entry/exit rules or selecting a different data period.</td>
            </tr>
        `;
        return;
    }
    
    tradePairs.forEach((tp, idx) => {
        const row = document.createElement('tr');
        const pnl = tp.pnl;
        const returnPct = tp.return_pct;
        const exitBadge = tp.exit_type === 'FORCE_SELL' ? '<span class="badge-exit-force">FORCE CLOSE</span>' : '<span class="badge-exit-sell">SELL</span>';
        
        row.innerHTML = `
            <td class="trade-pair-cell">#${idx + 1}</td>
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

// Render chart using Chart.js
function renderChart(history) {
    const ctx = document.getElementById('portfolioChart').getContext('2d');
    
    // Destroy previous chart if it exists
    if (state.chart) {
        state.chart.destroy();
    }
    
    const labels = history.map(h => formatTime(h.timestamp));
    
    // Normalize to base 100 (percentage change from the start of simulation)
    const initialPortfolio = history[0].portfolio_value;
    const initialAsset = history[0].close_price;
    
    const normalizedPortfolio = history.map(h => ((h.portfolio_value / initialPortfolio) * 100) - 100);
    const normalizedAsset = history.map(h => ((h.close_price / initialAsset) * 100) - 100);
    
    // Create new unified-axis line chart comparing returns
    state.chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Portfolio Return (%)',
                    data: normalizedPortfolio,
                    borderColor: '#6366f1',
                    borderWidth: 2.5,
                    backgroundColor: 'rgba(99, 102, 241, 0.05)',
                    fill: true,
                    tension: 0.15
                },
                {
                    label: 'Asset Return (%)',
                    data: normalizedAsset,
                    borderColor: '#14b8a6',
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                    backgroundColor: 'transparent',
                    fill: false,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
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
                            const index = context.dataIndex;
                            const item = history[index];
                            const label = context.dataset.label;
                            if (label.includes('Portfolio')) {
                                return `Portfolio Value: $${item.portfolio_value.toFixed(2)} (${context.parsed.y >= 0 ? '+' : ''}${context.parsed.y.toFixed(2)}%)`;
                            } else {
                                return `Asset Close Price: $${item.close_price.toFixed(2)} (${context.parsed.y >= 0 ? '+' : ''}${context.parsed.y.toFixed(2)}%)`;
                            }
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(31, 41, 55, 0.4)' },
                    ticks: { color: '#9ca3af', font: { size: 10 }, maxTicksLimit: 12 }
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
// STRATEGY CREATOR LOGIC
// ==========================================================================
function initCreator() {
    document.querySelectorAll('.rule-op-select').forEach(select => {
        select.addEventListener('change', (e) => {
            const ruleType = e.target.getAttribute('data-rule-type');
            const op = e.target.value;
            renderRuleSignals(ruleType, op);
        });
    });

    document.getElementById('strategy-creator-form').addEventListener('submit', saveStrategy);
    document.getElementById('btn-cancel-edit').addEventListener('click', () => {
        resetCreatorForm();
        showToast("Edit Cancelled", "Switched back to creating a new strategy.", "info");
    });

    renderRuleSignals("entry", "SINGLE");
    renderRuleSignals("exit", "SINGLE");
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
    renderRuleSignals("entry", "SINGLE");
    renderRuleSignals("exit", "SINGLE");
    updateCreatorModeUI();
}

// Renders the signals elements inside rule containers based on operator selection
function renderRuleSignals(ruleType, operator, presetSignals = null) {
    const container = document.getElementById(`${ruleType}-signals-container`);
    container.innerHTML = '';

    if (operator !== 'SINGLE') {
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'btn btn-secondary btn-sm mb-3';
        addBtn.innerHTML = '<i data-lucide="plus"></i> Add Sub-Signal';
        container.appendChild(addBtn);
        lucide.createIcons();

        addBtn.addEventListener('click', () => {
            addSignalRowItem(container, ruleType, true);
        });
    }

    const signals = presetSignals && presetSignals.length
        ? presetSignals
        : [null];

    signals.forEach((preset) => {
        addSignalRowItem(container, ruleType, operator !== 'SINGLE', preset);
    });
}

function fillSignalParams(paramsGrid, signalMeta, preset = null) {
    paramsGrid.innerHTML = '';

    if (signalMeta && signalMeta.parameters.length > 0) {
        signalMeta.parameters.forEach(p => {
            const field = document.createElement('div');
            field.className = 'signal-param-field';

            let value = p.default !== null && p.default !== undefined ? p.default : '';
            if (preset && preset[p.name] !== undefined && preset[p.name] !== null) {
                value = Array.isArray(preset[p.name])
                    ? preset[p.name].join(',')
                    : preset[p.name];
            }

            field.innerHTML = `
                <label>${p.name}</label>
                <input type="text"
                       data-param-name="${p.name}"
                       data-param-type="${p.type}"
                       placeholder="${p.description}"
                       value="${value}"
                       required>
            `;
            paramsGrid.appendChild(field);
        });
    } else if (signalMeta) {
        paramsGrid.innerHTML = '<span class="input-hint">No configuration parameters required for this signal.</span>';
    }
}

// Adds one signal row builder. Optional preset fills type + params (edit mode).
function addSignalRowItem(container, ruleType, isRemoveable = false, preset = null) {
    const row = document.createElement('div');
    row.className = 'signal-row-item';

    const dropdownOptions = state.signals.map(s => {
        const selected = preset && preset.type === s.name ? 'selected' : '';
        return `<option value="${s.name}" ${selected}>${s.name}</option>`;
    }).join('');

    row.innerHTML = `
        <div class="signal-row-header">
            <select class="signal-type-select" required>
                <option value="" disabled ${!(preset && preset.type) ? 'selected' : ''}>Select signal logic...</option>
                ${dropdownOptions}
            </select>
            ${isRemoveable ? `
                <button type="button" class="icon-btn-danger btn-remove-signal-row">
                    <i data-lucide="x-circle"></i>
                </button>
            ` : ''}
        </div>
        <div class="signal-params-grid">
            <!-- Dynamic parameters populated on selection -->
        </div>
    `;

    container.appendChild(row);
    lucide.createIcons();

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

    if (isRemoveable) {
        row.querySelector('.btn-remove-signal-row').addEventListener('click', () => {
            row.remove();
        });
    }
}

function populateRuleFromConfig(ruleType, rule) {
    let op = 'SINGLE';
    let signals = [];

    if (!rule) {
        document.getElementById(`${ruleType}-rule-op`).value = 'SINGLE';
        renderRuleSignals(ruleType, 'SINGLE');
        return;
    }

    if (rule.type === 'AND' || rule.type === 'OR') {
        op = rule.type;
        signals = rule.signals || [];
    } else {
        signals = [rule];
    }

    document.getElementById(`${ruleType}-rule-op`).value = op;
    renderRuleSignals(ruleType, op, signals);
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

// Form submit event to compile config and post/put save request
async function saveStrategy(event) {
    event.preventDefault();
    toggleLoading(true);

    try {
        const entryOp = document.getElementById('entry-rule-op').value;
        const entryRule = compileRuleConfig('entry', entryOp);
        const exitOp = document.getElementById('exit-rule-op').value;
        const exitRule = compileRuleConfig('exit', exitOp);

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

// Compile signals layout inside containers into nested JSON objects
function compileRuleConfig(ruleType, op) {
    const container = document.getElementById(`${ruleType}-signals-container`);
    const rows = container.querySelectorAll('.signal-row-item');

    if (rows.length === 0) return null;

    const signalsList = [];
    let isValid = true;

    rows.forEach(row => {
        const typeSelect = row.querySelector('.signal-type-select').value;
        if (!typeSelect) {
            isValid = false;
            return;
        }

        const signalObj = { type: typeSelect };

        const inputs = row.querySelectorAll('.signal-params-grid input');
        inputs.forEach(input => {
            const name = input.getAttribute('data-param-name');
            const type = input.getAttribute('data-param-type');
            const rawVal = input.value.trim();

            if (type === 'array') {
                signalObj[name] = rawVal.split(',').map(Number);
            } else {
                signalObj[name] = rawVal.includes('.') ? parseFloat(rawVal) : parseInt(rawVal, 10);
            }
        });

        signalsList.push(signalObj);
    });

    if (!isValid) return null;

    if (op === 'SINGLE') {
        return signalsList[0];
    }
    return {
        type: op,
        signals: signalsList
    };
}

// ==========================================================================
// SAVED STRATEGIES VIEW
// ==========================================================================
function formatIndicatorsPreview(indicators) {
    if (!indicators || Object.keys(indicators).length === 0) return 'None (from rules)';
    return Object.entries(indicators)
        .map(([k, v]) => `${k}: [${v.map(x => Array.isArray(x) ? `(${x.join(',')})` : x).join(', ')}]`)
        .join(' | ');
}

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

        const indicatorList = formatIndicatorsPreview(
            strat.derived_indicators || strat.config.indicators
        );
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
                <div class="meta-item" style="grid-column: span 2">
                    <span>Indicators (auto)</span>
                    <p style="font-size:12px;color:var(--text-secondary);">${indicatorList}</p>
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
            document.querySelector('.nav-btn[data-tab="backtest"]').click();
            showToast("Strategy Loaded", `Loaded ${strat.config.name} into configuration panel.`, "success");
        });
    });

    lucide.createIcons();
}

function formatRulePreview(rule) {
    if (!rule) return 'None';
    if (rule.type === 'AND' || rule.type === 'OR') {
        const subList = rule.signals.map(s => s.type).join(`, ${rule.type} `);
        return `${rule.type}(${subList})`;
    }
    return rule.type;
}
