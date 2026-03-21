"""Web server for interactive model analysis dashboard.

Run with: python nlweb_router/scripts/analysis_server.py
Then open http://localhost:8050
"""

import json
from pathlib import Path
from datetime import datetime
import os

from flask import Flask, render_template_string, jsonify
import subprocess
import threading

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SCRIPTS_DIR = Path(__file__).resolve().parent

# Track running analysis
analysis_status = {"running": False, "output": "", "last_run": None}
ANALYSIS_PATH = DATA_DIR / "analysis_multi_ref.json"
RETRIEVAL_PATH = DATA_DIR / "retrieval_results.json"

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Model Comparison Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }
        h1 { color: #fff; margin-bottom: 5px; font-size: 28px; }
        .subtitle { color: #888; font-size: 14px; margin-bottom: 20px; }

        .controls {
            background: #16213e;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .control-row {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            align-items: center;
            margin-bottom: 10px;
        }
        .control-row:last-child { margin-bottom: 0; }
        .control-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .controls label {
            font-weight: 500;
            font-size: 13px;
            color: #aaa;
        }
        .controls select, .controls input[type="number"] {
            background: #0f3460;
            color: #fff;
            border: 1px solid #444;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 13px;
        }
        .controls input[type="range"] { width: 120px; }

        .metric-checkboxes {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .metric-checkbox {
            display: flex;
            align-items: center;
            gap: 5px;
            background: #0f3460;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .metric-checkbox input { cursor: pointer; }
        .metric-checkbox.disabled { opacity: 0.5; cursor: not-allowed; }

        .summary-cards {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }
        .summary-card {
            background: #16213e;
            padding: 15px 20px;
            border-radius: 8px;
            flex: 1;
            text-align: center;
        }
        .summary-card .value {
            font-size: 22px;
            font-weight: bold;
            color: #4cc9f0;
        }
        .summary-card .label {
            font-size: 11px;
            color: #888;
            margin-top: 5px;
        }
        .summary-card.highlight .value { color: #f72585; }
        .summary-card.good .value { color: #4ade80; }

        .chart-container {
            background: #16213e;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .chart-row {
            display: flex;
            gap: 20px;
        }
        .chart-row .chart-container {
            flex: 1;
            min-width: 0;
        }
        .chart-title {
            margin: 0 0 15px 0;
            color: #fff;
            font-size: 16px;
            font-weight: 600;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        .data-table th, .data-table td {
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        .data-table th {
            background: #0f3460;
            color: #aaa;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
        }
        .data-table th:hover { background: #1a4a7a; }
        .data-table th.sorted-asc::after { content: " ▲"; }
        .data-table th.sorted-desc::after { content: " ▼"; }
        .data-table tr:hover { background: #1f2f4f; }
        .data-table .model-name { color: #4cc9f0; font-weight: 500; }
        .data-table .model-name:hover { text-decoration: underline; color: #7dd3fc; }
        .data-table .good { color: #4ade80; }
        .data-table .bad { color: #f87171; }

        .metric-badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
        }
        .metric-badge.azure { background: #0078d4; color: white; }
        .metric-badge.openrouter { background: #7c3aed; color: white; }
        .highlight-row { background: #1f3a5f !important; }

        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            background: #16213e;
            border: none;
            color: #888;
            cursor: pointer;
            border-radius: 8px 8px 0 0;
            font-size: 14px;
            font-weight: 500;
        }
        .tab.active { background: #0f3460; color: #fff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .ref-model-btn {
            padding: 6px 12px;
            background: #0f3460;
            border: 2px solid transparent;
            color: #aaa;
            cursor: pointer;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .ref-model-btn:hover { background: #1a4a7a; }
        .ref-model-btn.active {
            border-color: #4cc9f0;
            color: #fff;
            background: #1a4a7a;
        }
    </style>
</head>
<body>
    <h1>🎯 Model Comparison Dashboard</h1>
    <p class="subtitle">Compare candidate models against different reference models</p>

    <div class="controls">
        <div class="control-row">
            <label style="min-width: 110px;">Reference Model:</label>
            <div id="ref-model-buttons" style="display: flex; gap: 6px; flex-wrap: wrap;"></div>
        </div>
        <div class="control-row">
            <label style="min-width: 110px;">Query Difficulty:</label>
            <div id="difficulty-buttons" style="display: flex; gap: 6px;">
                <button class="ref-model-btn active" onclick="selectDifficulty('all')">All</button>
                <button class="ref-model-btn" onclick="selectDifficulty('easy')">Easy</button>
                <button class="ref-model-btn" onclick="selectDifficulty('medium')">Medium</button>
                <button class="ref-model-btn" onclick="selectDifficulty('hard')">Hard</button>
                <button class="ref-model-btn" onclick="selectDifficulty('very_hard')">Very Hard</button>
            </div>
        </div>
        <div class="control-row">
            <div class="control-group">
                <label>Queries:</label>
                <input type="number" id="query-count" value="1000" min="100" max="100000" step="100" onchange="updateDisplay()">
            </div>
            <div class="control-group">
                <label>Min ρ:</label>
                <input type="range" id="threshold-slider" min="0" max="1" step="0.05" value="0.50" oninput="updateThreshold(this.value)">
                <span id="threshold-value">0.50</span>
            </div>
        </div>
    </div>

    <div class="summary-cards">
        <div class="summary-card">
            <div class="value" id="ref-model-display">-</div>
            <div class="label">Reference Model</div>
        </div>
        <div class="summary-card">
            <div class="value" id="difficulty-display">All</div>
            <div class="label">Query Difficulty</div>
        </div>
        <div class="summary-card">
            <div class="value" id="num-queries-display">-</div>
            <div class="label">Queries Analyzed</div>
        </div>
        <div class="summary-card good">
            <div class="value" id="qualified-count">-</div>
            <div class="label">ρ ≥ <span id="threshold-display">0.50</span></div>
        </div>
        <div class="summary-card highlight">
            <div class="value" id="best-model">-</div>
            <div class="label">Best Correlation</div>
        </div>
        <div class="summary-card">
            <div class="value" id="cheapest-qualified">-</div>
            <div class="label">Cheapest Qualified</div>
        </div>
    </div>

    <div class="tabs">
        <button class="tab active" onclick="showTab('charts')">Metric Charts</button>
        <button class="tab" onclick="showTab('scatter')">Scatter Plots</button>
        <button class="tab" onclick="showTab('table')">Data Table</button>
        <button class="tab" onclick="showTab('details')">Model Details</button>
        <button class="tab" onclick="showTab('glossary')">Glossary</button>
    </div>

    <div id="tab-charts" class="tab-content active">
        <div class="chart-row">
            <div class="chart-container">
                <h3 class="chart-title" id="chart0-title">-</h3>
                <div id="chart0"></div>
            </div>
            <div class="chart-container">
                <h3 class="chart-title" id="chart1-title">-</h3>
                <div id="chart1"></div>
            </div>
            <div class="chart-container">
                <h3 class="chart-title" id="chart2-title">-</h3>
                <div id="chart2"></div>
            </div>
        </div>
        <div class="chart-row">
            <div class="chart-container">
                <h3 class="chart-title" id="chart3-title">-</h3>
                <div id="chart3"></div>
            </div>
            <div class="chart-container">
                <h3 class="chart-title" id="chart4-title">-</h3>
                <div id="chart4"></div>
            </div>
            <div class="chart-container">
                <h3 class="chart-title" id="chart5-title">-</h3>
                <div id="chart5"></div>
            </div>
        </div>
        <div class="chart-row">
            <div class="chart-container">
                <h3 class="chart-title" id="chart6-title">-</h3>
                <div id="chart6"></div>
            </div>
            <div class="chart-container">
                <h3 class="chart-title" id="chart7-title">-</h3>
                <div id="chart7"></div>
            </div>
            <div class="chart-container">
                <h3 class="chart-title" id="chart8-title">-</h3>
                <div id="chart8"></div>
            </div>
        </div>
        <div class="chart-row">
            <div class="chart-container">
                <h3 class="chart-title" id="chart9-title">-</h3>
                <div id="chart9"></div>
            </div>
        </div>
    </div>

    <div id="tab-scatter" class="tab-content">
        <div class="controls" style="margin-bottom: 15px;">
            <div class="control-row">
                <label>Accuracy Metric:</label>
                <select id="scatter-metric" onchange="updateScatterPlots(getModelsForRef())" style="min-width: 200px;">
                    <option value="rank_correlation">Spearman ρ</option>
                    <option value="top5_overlap">Top-5 Overlap</option>
                    <option value="top10_overlap">Top-10 Overlap</option>
                    <option value="good5_70">Good@5 (≥70)</option>
                    <option value="good10_70">Good@10 (≥70)</option>
                    <option value="bad5_50">Bad@5 (&lt;50) ↓</option>
                    <option value="bad10_50">Bad@10 (&lt;50) ↓</option>
                    <option value="high_bad_75_50">HighBad (≥75→&lt;50) ↓</option>
                </select>
            </div>
        </div>
        <div class="chart-row">
            <div class="chart-container">
                <h3 class="chart-title" id="scatter-cost-title">Cost vs Accuracy</h3>
                <div id="scatter-corr-cost"></div>
            </div>
            <div class="chart-container">
                <h3 class="chart-title" id="scatter-latency-title">Latency vs Accuracy</h3>
                <div id="scatter-corr-latency"></div>
            </div>
        </div>
    </div>

    <div id="tab-table" class="tab-content">
        <div class="chart-container">
            <h3 class="chart-title">All Models - Click headers to sort, click model name for details</h3>
            <table class="data-table" id="data-table">
                <thead id="table-header"></thead>
                <tbody id="table-body"></tbody>
            </table>
        </div>
    </div>

    <div id="tab-details" class="tab-content">
        <div class="chart-container">
            <div class="control-row" style="margin-bottom: 20px;">
                <label style="min-width: 100px;">Select Model:</label>
                <select id="model-select" onchange="updateModelDetails()" style="min-width: 300px;"></select>
            </div>
            <div id="model-details-content">
                <p style="color: #888;">Select a model to view details</p>
            </div>
        </div>
    </div>

    <div id="tab-glossary" class="tab-content">
        <div class="chart-container">
            <h3 class="chart-title">Metric Definitions</h3>
            <div style="display: grid; gap: 20px; max-width: 900px;">
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Spearman ρ (Rank Correlation)</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Measures how well the candidate model's score rankings correlate with the reference model's rankings.
                        Ranges from -1 to 1, where 1 means perfect agreement in ranking order.
                        <br><span style="color: #4ade80;">Higher is better.</span>
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Top-5 Overlap</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        For each query, measures what fraction of the reference model's top 5 highest-scored items
                        also appear in the candidate model's top 5. Averaged across all queries.
                        <br><span style="color: #4ade80;">Higher is better.</span> Range: 0 to 1.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Top-10 Overlap</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Same as Top-5 Overlap but for the top 10 items instead of top 5.
                        <br><span style="color: #4ade80;">Higher is better.</span> Range: 0 to 1.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Good@5 (≥70)</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Among items where the <em>reference model</em> scored ≥70 (good items), what fraction did the
                        candidate model also rank in its top 5? Measures ability to surface quality results.
                        <br><span style="color: #4ade80;">Higher is better.</span> Range: 0 to 1.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Good@10 (≥70)</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Same as Good@5 but checks if reference's high-scoring items appear in candidate's top 10.
                        <br><span style="color: #4ade80;">Higher is better.</span> Range: 0 to 1.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #f87171; margin: 0 0 8px 0;">Bad@5 (&lt;50)</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Among items in the candidate model's top 5, what fraction did the <em>reference model</em>
                        score below 50 (poor items)? Measures how often the candidate surfaces low-quality results.
                        <br><span style="color: #f87171;">Lower is better.</span> Range: 0 to 1.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #f87171; margin: 0 0 8px 0;">Bad@10 (&lt;50)</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Same as Bad@5 but for the candidate's top 10 items.
                        <br><span style="color: #f87171;">Lower is better.</span> Range: 0 to 1.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #f87171; margin: 0 0 8px 0;">HighBad (≥75→&lt;50)</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Measures severe disagreement: how often the candidate scores an item ≥75 (highly relevant)
                        when the reference scored it &lt;50 (poor). These are the worst false positives.
                        <br><span style="color: #f87171;">Lower is better.</span> Range: 0 to 1.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Cost/1K ($)</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Estimated cost in USD to score 1,000 queries (adjustable via the "Queries" input).
                        Computed from per-pair cost × items per query × number of queries.
                        <br><span style="color: #f87171;">Lower is better.</span>
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Latency (ms)</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Average response time in milliseconds for a single scoring request.
                        Measured as time from API request to receiving the complete response.
                        <br><span style="color: #f87171;">Lower is better.</span>
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Pareto Frontier</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        In the scatter plots, the green line shows the Pareto frontier — models where you cannot
                        improve one metric (e.g., accuracy) without sacrificing another (e.g., cost).
                        Models on this frontier represent optimal trade-offs.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Best Correlation</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        The candidate model with the highest Spearman ρ against the selected reference model.
                        This model's rankings most closely match the reference model's rankings.
                    </p>
                </div>
                <div style="background: #0f3460; padding: 15px; border-radius: 8px;">
                    <h4 style="color: #4cc9f0; margin: 0 0 8px 0;">Cheapest Qualified</h4>
                    <p style="color: #ccc; margin: 0; line-height: 1.5;">
                        Among models that meet the minimum ρ threshold (set via the "Min ρ" slider),
                        this is the model with the lowest cost per query. Useful for finding budget-friendly
                        models that still achieve acceptable accuracy.
                    </p>
                </div>
            </div>
        </div>
    </div>

    <script>
        const rawData = {{ data | tojson }};

        const ALL_METRICS = [
            { key: 'rank_correlation', label: 'Spearman ρ', format: v => v.toFixed(4), higherBetter: true },
            { key: 'top5_overlap', label: 'Top-5 Overlap', format: v => v.toFixed(2), higherBetter: true },
            { key: 'top10_overlap', label: 'Top-10 Overlap', format: v => v.toFixed(2), higherBetter: true },
            { key: 'good5_70', label: 'Good@5 (≥70)', format: v => v.toFixed(2), higherBetter: true },
            { key: 'good10_70', label: 'Good@10 (≥70)', format: v => v.toFixed(2), higherBetter: true },
            { key: 'bad5_50', label: 'Bad@5 (<50)', format: v => v.toFixed(2), higherBetter: false },
            { key: 'bad10_50', label: 'Bad@10 (<50)', format: v => v.toFixed(2), higherBetter: false },
            { key: 'high_bad_75_50', label: 'HighBad (≥75→<50)', format: v => v.toFixed(2), higherBetter: false },
            { key: 'cost_1k', label: 'Cost/1K ($)', format: v => '$' + v.toFixed(2), higherBetter: false },
            { key: 'avg_first_result_ms', label: 'Latency (ms)', format: v => v.toFixed(0), higherBetter: false },
        ];

        let selectedRef = rawData.reference_models[0];
        let selectedDifficulty = 'all';  // 'all', 'easy', 'medium', 'hard', 'very_hard'
        let threshold = 0.50;
        let queryCount = 1000;
        let sortCol = 'rank_correlation';
        let sortAsc = false;

        function shortName(model) {
            const name = model.split('/').pop();
            return name.length > 22 ? name.substring(0, 19) + '...' : name;
        }

        function isAzure(model) {
            return model.startsWith('azure/');
        }

        function initControls() {
            const refContainer = document.getElementById('ref-model-buttons');
            refContainer.innerHTML = rawData.reference_models.map(ref =>
                `<button class="ref-model-btn ${ref === selectedRef ? 'active' : ''}"
                         onclick="selectRef('${ref}')">${shortName(ref)}</button>`
            ).join('');
        }

        function selectRef(ref) {
            selectedRef = ref;
            document.querySelectorAll('#ref-model-buttons .ref-model-btn').forEach(btn => {
                btn.classList.toggle('active', btn.textContent === shortName(ref));
            });
            updateDisplay();
        }

        function selectDifficulty(diff) {
            selectedDifficulty = diff;
            const labels = { 'all': 'All', 'easy': 'Easy', 'medium': 'Medium', 'hard': 'Hard', 'very_hard': 'Very Hard' };
            document.querySelectorAll('#difficulty-buttons .ref-model-btn').forEach(btn => {
                btn.classList.toggle('active', btn.textContent === labels[diff]);
            });
            updateDisplay();
        }

        function updateThreshold(val) {
            threshold = parseFloat(val);
            document.getElementById('threshold-value').textContent = threshold.toFixed(2);
            document.getElementById('threshold-display').textContent = threshold.toFixed(2);
            updateDisplay();
        }

        function getModelsForRef() {
            // Get data based on selected difficulty
            let refData;
            if (selectedDifficulty === 'all') {
                refData = rawData.metrics_by_reference[selectedRef] || [];
            } else {
                const diffData = rawData.metrics_by_difficulty || {};
                refData = (diffData[selectedDifficulty] && diffData[selectedDifficulty][selectedRef]) || [];
            }

            // When a non-gpt-4.1 reference is selected, exclude gpt-4.1 from comparisons
            // (since gpt-4.1 is typically the "gold standard", showing it as a candidate
            // when using a lesser reference is misleading)
            const isGpt41Ref = selectedRef === 'gpt-4.1';
            return refData
                .filter(m => {
                    // Always exclude the reference model itself (already done server-side)
                    // When not using gpt-4.1 as reference, also exclude azure/gpt-4.1
                    if (!isGpt41Ref && m.model === 'azure/gpt-4.1') return false;
                    return true;
                })
                .map(m => ({
                    ...m,
                    cost_1k: m.cost_per_pair_usd * 50 * queryCount,
                    is_azure: isAzure(m.model)
                }));
        }

        function updateDisplay() {
            queryCount = parseInt(document.getElementById('query-count').value);
            const models = getModelsForRef();
            const qualified = models.filter(m => m.rank_correlation >= threshold);

            document.getElementById('ref-model-display').textContent = shortName(selectedRef);
            const diffLabels = { 'all': 'All', 'easy': 'Easy', 'medium': 'Medium', 'hard': 'Hard', 'very_hard': 'Very Hard' };
            document.getElementById('difficulty-display').textContent = diffLabels[selectedDifficulty];
            document.getElementById('qualified-count').textContent = qualified.length;

            // Show number of queries being analyzed
            if (models.length > 0) {
                const numQueries = models[0].num_queries || '-';
                document.getElementById('num-queries-display').textContent = numQueries;
            } else {
                document.getElementById('num-queries-display').textContent = '-';
            }

            if (models.length > 0) {
                const best = models.reduce((a, b) => a.rank_correlation > b.rank_correlation ? a : b);
                document.getElementById('best-model').textContent = shortName(best.model);
            } else {
                document.getElementById('best-model').textContent = '-';
            }

            if (qualified.length > 0) {
                const cheapest = qualified.reduce((a, b) => a.cost_1k < b.cost_1k ? a : b);
                document.getElementById('cheapest-qualified').textContent = shortName(cheapest.model);
            } else {
                document.getElementById('cheapest-qualified').textContent = '-';
            }

            updateCharts(models);
            updateScatterPlots(models);
            updateTable(models);
        }

        function updateCharts(models) {
            // Show all 9 metrics in a 3x3 grid
            ALL_METRICS.forEach((metric, i) => {
                const chartId = `chart${i}`;
                const titleId = `chart${i}-title`;
                const metricKey = metric.key;

                document.getElementById(titleId).textContent = metric.label;

                const sorted = [...models].sort((a, b) =>
                    metric.higherBetter ? b[metricKey] - a[metricKey] : a[metricKey] - b[metricKey]
                );

                const colors = sorted.map(m =>
                    m.rank_correlation >= threshold ? (m.is_azure ? '#0078d4' : '#7c3aed') : '#555'
                );

                Plotly.newPlot(chartId, [{
                    x: sorted.map(m => shortName(m.model)),
                    y: sorted.map(m => m[metricKey]),
                    type: 'bar',
                    marker: { color: colors }
                }], {
                    xaxis: { tickangle: -45, color: '#888', gridcolor: '#333' },
                    yaxis: { title: metric.label, color: '#888', gridcolor: '#333' },
                    height: 250,
                    margin: { t: 10, b: 100 },
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: '#aaa', size: 9 }
                });
            });
        }

        function computeParetoFrontier(points, xKey, yKey, xLowerBetter = true) {
            // Sort by x (ascending if lower is better, descending otherwise)
            const sorted = [...points].sort((a, b) => xLowerBetter ? a[xKey] - b[xKey] : b[xKey] - a[xKey]);
            const frontier = [];
            let bestY = -Infinity;

            for (const p of sorted) {
                if (p[yKey] > bestY) {
                    frontier.push(p);
                    bestY = p[yKey];
                }
            }
            // Sort frontier by x for line drawing
            return frontier.sort((a, b) => a[xKey] - b[xKey]);
        }

        function computeParetoFrontierLowerBetter(points, xKey, yKey, xLowerBetter = true) {
            // For metrics where lower Y is better (bad metrics)
            // Sort by x (ascending if lower is better)
            const sorted = [...points].sort((a, b) => xLowerBetter ? a[xKey] - b[xKey] : b[xKey] - a[xKey]);
            const frontier = [];
            let bestY = Infinity;

            for (const p of sorted) {
                if (p[yKey] < bestY) {
                    frontier.push(p);
                    bestY = p[yKey];
                }
            }
            return frontier.sort((a, b) => a[xKey] - b[xKey]);
        }

        function updateScatterPlots(models) {
            // Get selected accuracy metric
            const metricSelect = document.getElementById('scatter-metric');
            const metricKey = metricSelect ? metricSelect.value : 'rank_correlation';
            const metricInfo = ALL_METRICS.find(m => m.key === metricKey) || ALL_METRICS[0];
            const higherBetter = metricInfo.higherBetter;

            // Update titles
            const suffix = higherBetter ? '' : ' (lower is better)';
            document.getElementById('scatter-cost-title').textContent = 'Cost vs ' + metricInfo.label + suffix;
            document.getElementById('scatter-latency-title').textContent = 'Latency vs ' + metricInfo.label + suffix;

            // Filter outliers: remove models with cost > 95th percentile or latency > 95th percentile
            const costs = models.map(m => m.cost_1k).sort((a, b) => a - b);
            const latencies = models.map(m => m.avg_first_result_ms).sort((a, b) => a - b);
            const costP95 = costs[Math.floor(costs.length * 0.95)] || costs[costs.length - 1];
            const latencyP95 = latencies[Math.floor(latencies.length * 0.95)] || latencies[latencies.length - 1];

            const costFiltered = models.filter(m => m.cost_1k <= costP95 * 1.1);
            const latencyFiltered = models.filter(m => m.avg_first_result_ms <= latencyP95 * 1.1);

            // Compute Pareto frontiers - use different function based on whether higher or lower is better
            let costPareto, latencyPareto;
            if (higherBetter) {
                costPareto = computeParetoFrontier(costFiltered, 'cost_1k', metricKey, true);
                latencyPareto = computeParetoFrontier(latencyFiltered, 'avg_first_result_ms', metricKey, true);
            } else {
                costPareto = computeParetoFrontierLowerBetter(costFiltered, 'cost_1k', metricKey, true);
                latencyPareto = computeParetoFrontierLowerBetter(latencyFiltered, 'avg_first_result_ms', metricKey, true);
            }

            // Highlight Pareto optimal points
            const costParetoSet = new Set(costPareto.map(m => m.model));
            const latencyParetoSet = new Set(latencyPareto.map(m => m.model));

            // Determine y-axis range based on metric
            const yRange = metricKey === 'rank_correlation' ? [0, 1] : [0, Math.max(...models.map(m => m[metricKey])) * 1.1];

            Plotly.newPlot('scatter-corr-cost', [{
                x: costFiltered.map(m => m.cost_1k),
                y: costFiltered.map(m => m[metricKey]),
                mode: 'markers+text',
                type: 'scatter',
                text: costFiltered.map(m => shortName(m.model)),
                textposition: 'top center',
                textfont: { size: 9, color: '#aaa' },
                marker: {
                    size: costFiltered.map(m => costParetoSet.has(m.model) ? 14 : 10),
                    color: costFiltered.map(m => costParetoSet.has(m.model) ? '#4ade80' : (m.is_azure ? '#0078d4' : '#7c3aed')),
                    line: { color: '#fff', width: costFiltered.map(m => costParetoSet.has(m.model) ? 2 : 1) }
                },
                hovertemplate: '<b>%{text}</b><br>' + metricInfo.label + ': %{y:.4f}<br>Cost: $%{x:.2f}/1K<extra></extra>',
                name: 'Models'
            }, {
                x: costPareto.map(m => m.cost_1k),
                y: costPareto.map(m => m[metricKey]),
                mode: 'lines',
                type: 'scatter',
                line: { color: '#4ade80', width: 2, shape: 'hv' },
                showlegend: false,
                hoverinfo: 'skip',
                name: 'Pareto Frontier'
            }], {
                xaxis: { title: 'Cost/' + queryCount + ' queries ($)', color: '#888', gridcolor: '#333' },
                yaxis: { title: metricInfo.label + ' vs ' + shortName(selectedRef), range: yRange, color: '#888', gridcolor: '#333' },
                height: 400,
                margin: { t: 20, b: 50 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#aaa' }
            });

            Plotly.newPlot('scatter-corr-latency', [{
                x: latencyFiltered.map(m => m.avg_first_result_ms),
                y: latencyFiltered.map(m => m[metricKey]),
                mode: 'markers+text',
                type: 'scatter',
                text: latencyFiltered.map(m => shortName(m.model)),
                textposition: 'top center',
                textfont: { size: 9, color: '#aaa' },
                marker: {
                    size: latencyFiltered.map(m => latencyParetoSet.has(m.model) ? 14 : 10),
                    color: latencyFiltered.map(m => latencyParetoSet.has(m.model) ? '#4ade80' : (m.is_azure ? '#0078d4' : '#7c3aed')),
                    line: { color: '#fff', width: latencyFiltered.map(m => latencyParetoSet.has(m.model) ? 2 : 1) }
                },
                hovertemplate: '<b>%{text}</b><br>' + metricInfo.label + ': %{y:.4f}<br>Latency: %{x:.0f}ms<extra></extra>',
                name: 'Models'
            }, {
                x: latencyPareto.map(m => m.avg_first_result_ms),
                y: latencyPareto.map(m => m[metricKey]),
                mode: 'lines',
                type: 'scatter',
                line: { color: '#4ade80', width: 2, shape: 'hv' },
                showlegend: false,
                hoverinfo: 'skip',
                name: 'Pareto Frontier'
            }], {
                xaxis: { title: 'Latency (ms)', color: '#888', gridcolor: '#333' },
                yaxis: { title: metricInfo.label + ' vs ' + shortName(selectedRef), range: yRange, color: '#888', gridcolor: '#333' },
                height: 400,
                margin: { t: 20, b: 50 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#aaa' }
            });
        }

        function updateTable(models) {
            // Show all metrics in the table
            const headerHtml = `<tr>
                <th data-col="model">Model</th>
                ${ALL_METRICS.map(m => `<th data-col="${m.key}" data-numeric="true">${m.label}</th>`).join('')}
            </tr>`;
            document.getElementById('table-header').innerHTML = headerHtml;

            const sorted = [...models].sort((a, b) => {
                if (sortCol === 'model') {
                    return sortAsc ? a.model.localeCompare(b.model) : b.model.localeCompare(a.model);
                }
                return sortAsc ? a[sortCol] - b[sortCol] : b[sortCol] - a[sortCol];
            });

            const bodyHtml = sorted.map(m => {
                const isQualified = m.rank_correlation >= threshold;
                const rowClass = isQualified ? 'highlight-row' : '';
                const badge = m.is_azure ? '<span class="metric-badge azure">Az</span>' : '<span class="metric-badge openrouter">OR</span>';

                return `<tr class="${rowClass}">
                    <td class="model-name" style="cursor: pointer;" onclick="showModelDetails('${m.model}')">${badge} ${shortName(m.model)}</td>
                    ${ALL_METRICS.map(metric => {
                        const val = m[metric.key];
                        const formatted = metric.format(val);
                        const cellClass = metric.key === 'rank_correlation' && isQualified ? 'good' :
                                          metric.key.startsWith('bad') && val > 0.3 ? 'bad' : '';
                        return `<td class="${cellClass}">${formatted}</td>`;
                    }).join('')}
                </tr>`;
            }).join('');
            document.getElementById('table-body').innerHTML = bodyHtml;

            document.querySelectorAll('#table-header th').forEach(th => {
                th.classList.remove('sorted-asc', 'sorted-desc');
                if (th.dataset.col === sortCol) {
                    th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
                }
            });

            document.querySelectorAll('#table-header th').forEach(th => {
                th.onclick = () => {
                    const col = th.dataset.col;
                    if (sortCol === col) {
                        sortAsc = !sortAsc;
                    } else {
                        sortCol = col;
                        sortAsc = th.dataset.numeric === 'true' ? false : true;
                    }
                    updateTable(models);
                };
            });
        }

        function showTab(tabId) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector(`.tab[onclick="showTab('${tabId}')"]`).classList.add('active');
            document.getElementById('tab-' + tabId).classList.add('active');
            if (tabId === 'details') {
                populateModelSelect();
            }
        }

        function populateModelSelect() {
            const select = document.getElementById('model-select');
            const models = [...new Set(rawData.candidate_models)].sort();
            select.innerHTML = '<option value="">-- Select a model --</option>' +
                models.map(m => `<option value="${m}">${m}</option>`).join('');
        }

        function showModelDetails(modelName) {
            showTab('details');
            document.getElementById('model-select').value = modelName;
            updateModelDetails();
        }

        function updateModelDetails() {
            const modelName = document.getElementById('model-select').value;
            const container = document.getElementById('model-details-content');

            if (!modelName) {
                container.innerHTML = '<p style="color: #888;">Select a model to view details</p>';
                return;
            }

            // Gather metrics across all reference models
            const metricsAcrossRefs = [];
            for (const refName of rawData.reference_models) {
                const refData = rawData.metrics_by_reference[refName] || [];
                const modelData = refData.find(m => m.model === modelName);
                if (modelData) {
                    metricsAcrossRefs.push({ ref: refName, ...modelData });
                }
            }

            if (metricsAcrossRefs.length === 0) {
                container.innerHTML = `<p style="color: #f87171;">No data found for ${modelName}</p>`;
                return;
            }

            const isAzureModel = modelName.startsWith('azure/');
            const badge = isAzureModel ? '<span class="metric-badge azure">Azure</span>' : '<span class="metric-badge openrouter">OpenRouter</span>';

            // Get cost info from first entry
            const costPerPair = metricsAcrossRefs[0].cost_per_pair_usd || 0;
            const cost1k = costPerPair * 50 * queryCount;
            const avgLatency = metricsAcrossRefs[0].avg_first_result_ms || 0;

            let html = `
                <h2 style="color: #4cc9f0; margin-bottom: 5px;">${badge} ${modelName}</h2>
                <div class="summary-cards" style="margin: 20px 0;">
                    <div class="summary-card">
                        <div class="value">$${cost1k.toFixed(2)}</div>
                        <div class="label">Cost per ${queryCount} queries</div>
                    </div>
                    <div class="summary-card">
                        <div class="value">${avgLatency.toFixed(0)}ms</div>
                        <div class="label">Avg First Result Latency</div>
                    </div>
                    <div class="summary-card">
                        <div class="value">$${(costPerPair * 1000000).toFixed(2)}</div>
                        <div class="label">Cost per 1M pairs</div>
                    </div>
                </div>

                <h3 class="chart-title">Performance vs Each Reference Model</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Reference Model</th>
                            <th>Spearman ρ</th>
                            <th>Top-5 Overlap</th>
                            <th>Top-10 Overlap</th>
                            <th>Good@5 (≥70)</th>
                            <th>Good@10 (≥70)</th>
                            <th>Bad@5 (<50)</th>
                            <th>Bad@10 (<50)</th>
                            <th>HighBad (≥75→<50)</th>
                            <th>Queries</th>
                            <th>Pairs</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            for (const m of metricsAcrossRefs) {
                const corrClass = m.rank_correlation >= 0.6 ? 'good' : m.rank_correlation < 0.4 ? 'bad' : '';
                const badClass5 = m.bad5_50 > 0.5 ? 'bad' : '';
                const badClass10 = m.bad10_50 > 0.5 ? 'bad' : '';
                const highBadClass = (m.high_bad_75_50 || 0) > 0.5 ? 'bad' : '';

                html += `
                    <tr>
                        <td class="model-name">${shortName(m.ref)}</td>
                        <td class="${corrClass}">${m.rank_correlation.toFixed(4)}</td>
                        <td>${m.top5_overlap.toFixed(2)}</td>
                        <td>${m.top10_overlap.toFixed(2)}</td>
                        <td>${m.good5_70.toFixed(2)}</td>
                        <td>${m.good10_70.toFixed(2)}</td>
                        <td class="${badClass5}">${m.bad5_50.toFixed(2)}</td>
                        <td class="${badClass10}">${m.bad10_50.toFixed(2)}</td>
                        <td class="${highBadClass}">${(m.high_bad_75_50 || 0).toFixed(2)}</td>
                        <td>${m.num_queries}</td>
                        <td>${m.num_pairs}</td>
                    </tr>
                `;
            }

            html += `</tbody></table>`;

            // Add a chart showing correlation across references
            html += `<div id="model-corr-chart" style="margin-top: 30px;"></div>`;

            container.innerHTML = html;

            // Draw correlation bar chart
            const refs = metricsAcrossRefs.map(m => shortName(m.ref));
            const corrs = metricsAcrossRefs.map(m => m.rank_correlation);
            const colors = corrs.map(c => c >= 0.6 ? '#4ade80' : c >= 0.4 ? '#fbbf24' : '#f87171');

            Plotly.newPlot('model-corr-chart', [{
                x: refs,
                y: corrs,
                type: 'bar',
                marker: { color: colors }
            }], {
                title: { text: 'Spearman ρ vs Each Reference', font: { color: '#fff', size: 14 } },
                xaxis: { tickangle: -30, color: '#888', gridcolor: '#333' },
                yaxis: { title: 'Spearman ρ', range: [0, 1], color: '#888', gridcolor: '#333' },
                height: 300,
                margin: { t: 50, b: 80 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#aaa' }
            });
        }

        initControls();
        updateDisplay();
        populateModelSelect();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    if not ANALYSIS_PATH.exists():
        return "Analysis data not found. Run analyze_multi_ref.py first.", 404

    with open(ANALYSIS_PATH) as f:
        data = json.load(f)

    return render_template_string(HTML_TEMPLATE, data=data)


STATUS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Crawl Status</title>
    <meta http-equiv="refresh" content="10">
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }
        h1 { color: #fff; margin-bottom: 5px; font-size: 28px; }
        .subtitle { color: #888; font-size: 14px; margin-bottom: 20px; }

        .summary-cards {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .summary-card {
            background: #16213e;
            padding: 15px 20px;
            border-radius: 8px;
            min-width: 150px;
            text-align: center;
        }
        .summary-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #4cc9f0;
        }
        .summary-card .label {
            font-size: 11px;
            color: #888;
            margin-top: 5px;
        }
        .summary-card.highlight .value { color: #f72585; }
        .summary-card.good .value { color: #4ade80; }
        .summary-card.warn .value { color: #fbbf24; }

        .section {
            background: #16213e;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .section h2 {
            margin: 0 0 15px 0;
            color: #fff;
            font-size: 18px;
        }

        .progress-bar {
            background: #0f3460;
            border-radius: 8px;
            height: 24px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4cc9f0, #7c3aed);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: bold;
            transition: width 0.3s ease;
        }

        .model-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
        }
        .model-card {
            background: #0f3460;
            padding: 15px;
            border-radius: 8px;
        }
        .model-card .name {
            color: #4cc9f0;
            font-weight: 600;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .model-card .stats {
            display: flex;
            gap: 15px;
            font-size: 12px;
            color: #aaa;
        }
        .model-card .stat-value { color: #fff; font-weight: 600; }
        .model-card .progress-bar { height: 8px; margin-bottom: 5px; }

        .file-info {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }
        .file-item {
            background: #0f3460;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 12px;
        }
        .file-item .name { color: #4cc9f0; font-weight: 500; }
        .file-item .size { color: #888; }
        .file-item .time { color: #aaa; font-size: 11px; }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            margin-left: 8px;
        }
        .badge.azure { background: #0078d4; color: white; }
        .badge.openrouter { background: #7c3aed; color: white; }
        .badge.complete { background: #4ade80; color: #000; }
        .badge.running { background: #fbbf24; color: #000; }

        .nav {
            margin-bottom: 20px;
        }
        .nav a {
            color: #4cc9f0;
            text-decoration: none;
            margin-right: 20px;
        }
        .nav a:hover { text-decoration: underline; }

        .refresh-note {
            color: #666;
            font-size: 11px;
            margin-top: 10px;
        }

        .action-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .action-btn.primary {
            background: linear-gradient(135deg, #4cc9f0, #7c3aed);
            color: white;
        }
        .action-btn.primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.4);
        }
        .action-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .action-bar {
            display: flex;
            gap: 15px;
            align-items: center;
            margin-bottom: 20px;
        }
        .status-text {
            font-size: 13px;
            color: #888;
        }
        .status-text.running { color: #fbbf24; }
        .status-text.success { color: #4ade80; }
        .status-text.error { color: #f87171; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">← Dashboard</a>
        <a href="/status">Crawl Status</a>
    </div>

    <h1>📊 Crawl Status</h1>
    <p class="subtitle">Scoring progress across all models (auto-refreshes every 10s)</p>

    <div class="action-bar">
        <button class="action-btn primary" id="run-analysis-btn" onclick="runAnalysis()">
            ▶ Run Analysis
        </button>
        <span class="status-text" id="analysis-status">
            {% if analysis_running %}
            <span class="running">⏳ Analysis running...</span>
            {% elif analysis_last_run %}
            <span class="success">✓ Last run: {{ analysis_last_run }}</span>
            {% endif %}
        </span>
    </div>

    <script>
        function runAnalysis() {
            const btn = document.getElementById('run-analysis-btn');
            const status = document.getElementById('analysis-status');

            btn.disabled = true;
            btn.textContent = '⏳ Running...';
            status.innerHTML = '<span class="running">⏳ Analysis running...</span>';

            fetch('/run-analysis', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        status.innerHTML = '<span class="success">✓ ' + data.message + '</span>';
                        // Redirect to dashboard after success
                        setTimeout(() => { window.location.href = '/'; }, 1500);
                    } else {
                        status.innerHTML = '<span class="error">✗ ' + data.message + '</span>';
                    }
                    btn.disabled = false;
                    btn.textContent = '▶ Run Analysis';
                })
                .catch(err => {
                    status.innerHTML = '<span class="error">✗ Error: ' + err + '</span>';
                    btn.disabled = false;
                    btn.textContent = '▶ Run Analysis';
                });
        }
    </script>

    <div class="summary-cards">
        <div class="summary-card">
            <div class="value">{{ total_queries }}</div>
            <div class="label">Total Queries</div>
        </div>
        <div class="summary-card">
            <div class="value">{{ total_pairs }}</div>
            <div class="label">Total Query-Item Pairs</div>
        </div>
        <div class="summary-card good">
            <div class="value">{{ azure_models_complete }}/{{ azure_models_total }}</div>
            <div class="label">Azure Models Done</div>
        </div>
        <div class="summary-card" style="background: #7c3aed22;">
            <div class="value">{{ openrouter_models_complete }}/{{ openrouter_models_total }}</div>
            <div class="label">OpenRouter Models Done</div>
        </div>
    </div>

    <div class="section">
        <h2>Azure OpenAI Models</h2>
        <div class="model-grid">
            {% for model in azure_models %}
            <div class="model-card">
                <div class="name">
                    {{ model.name }}
                    {% if model.complete %}
                    <span class="badge complete">Complete</span>
                    {% elif model.scored > 0 %}
                    <span class="badge running">Running</span>
                    {% endif %}
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {{ model.pct }}%">{{ model.pct }}%</div>
                </div>
                <div class="stats">
                    <div>Pairs: <span class="stat-value">{{ model.scored }}</span></div>
                    {% if model.latency_ms %}
                    <div>Latency: <span class="stat-value">{{ model.latency_ms|int }}ms</span></div>
                    {% endif %}
                    {% if model.cost %}
                    <div>Cost: <span class="stat-value">${{ "%.2f"|format(model.cost) }}</span></div>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="section">
        <h2>OpenRouter Models ({{ openrouter_models|length }} models)</h2>
        <div class="model-grid">
            {% for model in openrouter_models %}
            <div class="model-card">
                <div class="name">
                    {{ model.name }}
                    {% if model.complete %}
                    <span class="badge complete">Complete</span>
                    {% endif %}
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {{ model.pct }}%">{{ model.pct }}%</div>
                </div>
                <div class="stats">
                    <div>Pairs: <span class="stat-value">{{ model.scored }}</span></div>
                    {% if model.latency_ms %}
                    <div>Latency: <span class="stat-value">{{ model.latency_ms|int }}ms</span></div>
                    {% endif %}
                    {% if model.cost %}
                    <div>Cost: <span class="stat-value">${{ "%.4f"|format(model.cost) }}</span></div>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="section">
        <h2>Data Files</h2>
        <div class="file-info">
            {% for f in files %}
            <div class="file-item">
                <div class="name">{{ f.name }}</div>
                <div class="size">{{ f.size }}</div>
                <div class="time">{{ f.modified }}</div>
            </div>
            {% endfor %}
        </div>
    </div>

    <p class="refresh-note">Last updated: {{ last_updated }}</p>
</body>
</html>
"""


def safe_load_json(path):
    """Load JSON file, returning None if file is being written or corrupted."""
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_crawl_status():
    """Compute crawl status from data files."""
    status = {
        "total_queries": 0,
        "total_pairs": 0,
        "azure_models": [],
        "openrouter_models": [],
        "azure_models_complete": 0,
        "azure_models_total": 3,
        "openrouter_models_complete": 0,
        "openrouter_models_total": 0,
        "files": [],
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Load retrieval results to get total counts
    if RETRIEVAL_PATH.exists():
        retrieval = safe_load_json(RETRIEVAL_PATH)
        if retrieval:
            status["total_queries"] = len(retrieval)
            status["total_pairs"] = sum(r.get("num_results", 0) for r in retrieval)

    # Check Azure models
    azure_models = ["gpt-4.1", "gpt-4.1-mini", "gpt-4o-mini"]
    for model in azure_models:
        score_path = DATA_DIR / f"scores_azure_oai_{model}.json"
        cost_path = DATA_DIR / f"cost_azure_oai_{model}.json"

        model_info = {
            "name": model,
            "scored": 0,
            "queries": 0,
            "pct": 0,
            "complete": False,
            "cost": None,
        }

        if score_path.exists():
            scores = safe_load_json(score_path)
            if scores:
                model_info["queries"] = len(scores)
                model_info["scored"] = sum(len(q.get("items", [])) for q in scores)
                if status["total_pairs"] > 0:
                    model_info["pct"] = round(100 * model_info["scored"] / status["total_pairs"], 1)
                model_info["complete"] = model_info["pct"] >= 99
                if model_info["complete"]:
                    status["azure_models_complete"] += 1

        if cost_path.exists():
            cost = safe_load_json(cost_path)
            if cost:
                model_info["cost"] = cost.get("total_cost_usd", 0)
                model_info["latency_ms"] = cost.get("avg_response_time_ms", 0)

        status["azure_models"].append(model_info)

    # Check OpenRouter models
    openrouter_score_path = DATA_DIR / "scores_openrouter.json"
    openrouter_cost_path = DATA_DIR / "cost_openrouter.json"

    if openrouter_score_path.exists():
        or_scores = safe_load_json(openrouter_score_path)
        if not or_scores:
            or_scores = []

        # Get model list from first query that has items
        model_set = set()
        model_counts = {}  # pairs per model
        model_queries = {}  # queries per model (unique)

        for qi, query_data in enumerate(or_scores):
            models_in_query = set()
            for item in query_data.get("items", []):
                for ms in item.get("model_scores", []):
                    model = ms.get("model", "")
                    if model:
                        model_set.add(model)
                        model_counts[model] = model_counts.get(model, 0) + 1
                        models_in_query.add(model)
            # Count unique queries per model
            for model in models_in_query:
                model_queries[model] = model_queries.get(model, 0) + 1

        # Load costs and latency from cost file
        model_costs = {}
        model_latency = {}
        if openrouter_cost_path.exists():
            cost_data = safe_load_json(openrouter_cost_path)
            if cost_data:
                for entry in cost_data:
                    model_costs[entry.get("model", "")] = entry.get("total_cost_usd", 0)
                    model_latency[entry.get("model", "")] = entry.get("avg_response_time_ms", 0)

        status["openrouter_models_total"] = len(model_set)

        for model in sorted(model_set):
            count = model_counts.get(model, 0)
            pct = round(100 * count / status["total_pairs"], 1) if status["total_pairs"] > 0 else 0
            complete = pct >= 99
            if complete:
                status["openrouter_models_complete"] += 1

            status["openrouter_models"].append({
                "name": model.split("/")[-1] if "/" in model else model,
                "full_name": model,
                "queries": model_queries.get(model, 0),
                "scored": count,
                "pct": pct,
                "complete": complete,
                "cost": model_costs.get(model),
                "latency_ms": model_latency.get(model),
            })

    # List data files
    if DATA_DIR.exists():
        for f in sorted(DATA_DIR.glob("*.json")):
            stat = f.stat()
            size_kb = stat.st_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            status["files"].append({
                "name": f.name,
                "size": size_str,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })

    return status


@app.route("/status")
def crawl_status():
    status = get_crawl_status()
    status["analysis_running"] = analysis_status["running"]
    status["analysis_last_run"] = analysis_status["last_run"]
    return render_template_string(STATUS_TEMPLATE, **status)


def run_analysis_script():
    """Run the analysis script in background."""
    global analysis_status
    analysis_status["running"] = True
    analysis_status["output"] = ""

    try:
        result = subprocess.run(
            ["python", str(SCRIPTS_DIR / "analyze_multi_ref.py")],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS_DIR.parent.parent),
            timeout=300,
        )
        analysis_status["output"] = result.stdout + result.stderr
        analysis_status["last_run"] = datetime.now().strftime("%H:%M:%S")
    except Exception as e:
        analysis_status["output"] = f"Error: {e}"
    finally:
        analysis_status["running"] = False


@app.route("/run-analysis", methods=["POST"])
def run_analysis():
    """Trigger analysis script run."""
    if analysis_status["running"]:
        return jsonify({"success": False, "message": "Analysis already running"})

    # Run in background thread
    thread = threading.Thread(target=run_analysis_script)
    thread.start()

    # Wait briefly to see if it starts successfully
    thread.join(timeout=2)

    if analysis_status["running"]:
        return jsonify({"success": True, "message": "Analysis started..."})

    # If it finished quickly, return the result
    if analysis_status["last_run"]:
        return jsonify({"success": True, "message": f"Analysis completed at {analysis_status['last_run']}"})

    return jsonify({"success": False, "message": "Failed to start analysis"})


if __name__ == "__main__":
    print("Starting analysis server...")
    print("Open http://localhost:8050 in your browser")
    print("Crawl status at http://localhost:8050/status")
    # Only enable debug mode if explicitly set via environment variable
    import os
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host="0.0.0.0", port=8050, debug=debug_mode)
