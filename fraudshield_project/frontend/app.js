const API = "http://localhost:5000/api";

const COLORS = { low: "#22c55e", med: "#f59e0b", high: "#ef4444", blue: "#3b82f6", purple: "#a855f7", cyan: "#06b6d4" };
const CHANNEL_COLORS = { Web: "#a855f7", Mobile: "#3b82f6", API: "#22c55e", POS: "#06b6d4" };

let charts = {};

// ---------------------------------------------------------------- NAV ----
document.querySelectorAll(".nav-item, [data-view]").forEach(el => {
  el.addEventListener("click", () => switchView(el.dataset.view));
});

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach(n => n.classList.toggle("active", n.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.getElementById("view-" + view).classList.add("active");

  const titles = {
    dashboard: "Fraud Risk Command Center", live: "Transaction Detail",
    transactions: "Transactions", alerts: "Alerts", cases: "Case Management",
    score: "Score a New Transaction", models: "Models & Performance",
  };
  document.getElementById("pageTitle").textContent = titles[view] || "FraudShield";

  if (view === "transactions") loadTransactions();
  if (view === "alerts") loadAlerts();
  if (view === "cases") loadCases();
  if (view === "models") loadModelsView();
  if (view === "live") loadQuickPicks();
}

// ------------------------------------------------------------ HELPERS ----
async function getJSON(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error("Request failed: " + path);
  return res.json();
}
function fmtMoney(n) { return "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function fmtTime(iso) { const d = new Date(iso); return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
function riskClass(score) { return score >= 70 ? "high" : score >= 30 ? "med" : "low"; }
function statusChipClass(status) {
  if (status === "Flagged") return "flagged";
  if (status === "Review") return "review";
  return "cleared";
}

// ============================================================ DASHBOARD
async function loadDashboard() {
  const [summary, dist, trend, factors, alertsOv, byChannel, perf, feed] = await Promise.all([
    getJSON("/summary"), getJSON("/risk-distribution"), getJSON("/fraud-trend"),
    getJSON("/top-risk-factors"), getJSON("/alerts-overview"), getJSON("/alerts-by-channel"),
    getJSON("/model-performance"), getJSON("/live-feed"),
  ]);

  renderKPIs(summary);
  renderRiskDonut(dist);
  renderFraudTrend(trend);
  renderRiskFactorBars(factors);
  renderLiveFeed(feed);
  renderAlertsOverview(alertsOv);
  renderChannelDonut(byChannel);
  renderModelPerf(perf);

  document.getElementById("alertBadge").textContent = alertsOv.high_risk_alerts;
}

function renderKPIs(s) {
  const cards = [
    { label: "Total Transactions", value: s.total_transactions.toLocaleString(), delta: "▲ 12.5% vs last hour", cls: "up", icon: "🔷" },
    { label: "Risky Transactions", value: s.risky_transactions.toLocaleString(), delta: "▲ 18.7% vs last hour", cls: "up", icon: "🟣" },
    { label: "High Risk (≥ 70)", value: s.high_risk.toLocaleString(), delta: "▲ 22.1% vs last hour", cls: "up", icon: "🔺" },
    { label: "Fraud Confirmed", value: s.fraud_confirmed.toLocaleString(), delta: "▲ 8.9% vs last hour", cls: "up", icon: "🛡️" },
    { label: "Avg Risk Score", value: s.avg_risk_score, delta: "▼ 3.4% vs last hour", cls: "down", icon: "📈" },
    { label: "Blocked Amount", value: fmtMoney(s.blocked_amount), delta: "▲ 15.3% vs last hour", cls: "up", icon: "💰" },
  ];
  document.getElementById("kpiGrid").innerHTML = cards.map(c => `
    <div class="kpi-card">
      <div class="kpi-top"><span class="kpi-label">${c.label}</span><span class="kpi-icon">${c.icon}</span></div>
      <div class="kpi-value">${c.value}</div>
      <div class="kpi-delta ${c.cls}">${c.delta}</div>
    </div>`).join("");
}

function renderRiskDonut(dist) {
  const ctx = document.getElementById("riskDonut");
  if (charts.riskDonut) charts.riskDonut.destroy();
  charts.riskDonut = new Chart(ctx, {
    type: "doughnut",
    data: { labels: dist.labels, datasets: [{ data: dist.counts, backgroundColor: [COLORS.low, COLORS.med, COLORS.high], borderWidth: 0 }] },
    options: { cutout: "70%", plugins: { legend: { display: false } } },
  });
  document.getElementById("riskDonutLegend").innerHTML = dist.labels.map((l, i) => `
    <div class="legend-row"><span class="legend-dot" style="background:${[COLORS.low, COLORS.med, COLORS.high][i]}"></span>
      ${l} <span class="legend-val">${dist.counts[i]} (${dist.percentages[i]}%)</span></div>`).join("");
}

function renderFraudTrend(trend) {
  const ctx = document.getElementById("fraudTrendChart");
  if (charts.trend) charts.trend.destroy();
  charts.trend = new Chart(ctx, {
    type: "line",
    data: {
      labels: trend.labels,
      datasets: [
        { label: "Risky Transactions", data: trend.risky, borderColor: COLORS.purple, tension: 0.35, pointRadius: 0 },
        { label: "Fraud Confirmed", data: trend.fraud, borderColor: COLORS.high, tension: 0.35, pointRadius: 0 },
      ],
    },
    options: {
      plugins: { legend: { labels: { color: "#8892a4", boxWidth: 10, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: "#5c667a", font: { size: 10 } }, grid: { color: "#1b2333" } },
        y: { ticks: { color: "#5c667a", font: { size: 10 } }, grid: { color: "#1b2333" }, beginAtZero: true },
      },
    },
  });
}

function renderRiskFactorBars(factors) {
  const colors = [COLORS.high, COLORS.med, COLORS.purple, COLORS.blue, COLORS.cyan];
  document.getElementById("riskFactorsBars").innerHTML = factors.map((f, i) => `
    <div class="risk-factor-row">
      <div class="rf-label-row"><span>${f.factor}</span><span>${f.percentage}%</span></div>
      <div class="rf-bar-bg"><div class="rf-bar-fill" style="width:${f.percentage}%;background:${colors[i % colors.length]}"></div></div>
    </div>`).join("");
}

function renderLiveFeed(feed) {
  document.getElementById("liveFeedList").innerHTML = feed.map(t => `
    <div class="feed-row">
      <span class="feed-time">${fmtTime(t.created_at)}</span>
      <span class="feed-id">${t.txn_id} <span class="feed-user">· ${t.user_id}</span></span>
      <span>${fmtMoney(t.amount)}</span>
      <span class="chip ${statusChipClass(t.status)}">${t.status === "Flagged" ? fmtMoney(t.amount) : "Risk: " + t.risk_score}</span>
    </div>`).join("");
}

function renderAlertsOverview(ov) {
  document.getElementById("alertsOverview").innerHTML = `
    <div class="ao-item"><div class="ao-value" style="color:${COLORS.high}">${ov.high_risk_alerts}</div><div class="ao-label">High Risk Alerts</div></div>
    <div class="ao-item"><div class="ao-value" style="color:${COLORS.med}">${ov.medium_risk_alerts}</div><div class="ao-label">Medium Risk Alerts</div></div>
    <div class="ao-item"><div class="ao-value" style="color:${COLORS.low}">${ov.low_risk_alerts}</div><div class="ao-label">Low Risk Alerts</div></div>`;
}

function renderChannelDonut(byChannel) {
  const ctx = document.getElementById("channelDonut");
  if (charts.channel) charts.channel.destroy();
  const labels = byChannel.map(c => c.channel);
  const data = byChannel.map(c => c.percentage);
  const colors = labels.map(l => CHANNEL_COLORS[l] || COLORS.blue);
  charts.channel = new Chart(ctx, {
    type: "doughnut",
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
    options: { cutout: "65%", plugins: { legend: { display: false } } },
  });
  document.getElementById("channelDonutLegend").innerHTML = labels.map((l, i) => `
    <div class="legend-row"><span class="legend-dot" style="background:${colors[i]}"></span>${l} <span class="legend-val">${data[i]}%</span></div>`).join("");
}

function renderModelPerf(perf) {
  const items = [
    { label: "Precision", value: perf.precision },
    { label: "Recall", value: perf.recall },
    { label: "F1 Score", value: perf.f1_score },
    { label: "AUC-ROC", value: perf.auc_roc },
  ];
  document.getElementById("modelPerf").innerHTML = items.map(i => `
    <div class="mp-item"><div class="mp-value">${i.value}</div><div class="mp-label">${i.label}</div></div>`).join("");
}

// ============================================================ TRANSACTIONS
async function loadTransactions() {
  const rows = await getJSON("/transactions?limit=100");
  const tbody = document.querySelector("#txnTable tbody");
  tbody.innerHTML = rows.map(t => `
    <tr data-txn="${t.txn_id}">
      <td>${t.txn_id}</td><td>${t.user_id}</td><td>${fmtMoney(t.amount)}</td>
      <td>${t.channel}</td><td>${t.location}</td>
      <td class="risk-cell ${riskClass(t.risk_score)}">${t.risk_score}</td>
      <td><span class="chip ${statusChipClass(t.status)}">${t.status}</span></td>
      <td>${fmtTime(t.created_at)}</td>
    </tr>`).join("");
  tbody.querySelectorAll("tr").forEach(tr => {
    tr.addEventListener("click", () => openTransactionDetail(tr.dataset.txn));
  });
}
document.getElementById("refreshTxns")?.addEventListener("click", loadTransactions);

// ============================================================ TRANSACTION DETAIL
async function loadQuickPicks() {
  const rows = await getJSON("/transactions?limit=100");
  const picks = [...rows].sort((a, b) => b.risk_score - a.risk_score).slice(0, 5);
  document.getElementById("quickTxnPicks").innerHTML = picks.map(t => `
    <button class="btn-mini" data-txn="${t.txn_id}">${t.txn_id} (risk ${t.risk_score})</button>`).join("");
  document.querySelectorAll("#quickTxnPicks .btn-mini").forEach(b => {
    b.addEventListener("click", () => openTransactionDetail(b.dataset.txn));
  });
}

async function openTransactionDetail(txnId) {
  switchView("live");
  const data = await getJSON("/transactions/" + txnId);
  document.getElementById("detailHint").classList.add("hidden");
  document.getElementById("detailContent").classList.remove("hidden");
  renderTransactionDetail(data);
}

function renderTransactionDetail(data) {
  const t = data.transaction;
  document.getElementById("txnInfo").innerHTML = [
    ["Transaction ID", t.txn_id], ["User ID", t.user_id], ["Amount", fmtMoney(t.amount)],
    ["Status", t.status], ["Time", new Date(t.created_at).toLocaleString()],
    ["Channel", t.channel], ["Location", t.location], ["Device", t.device], ["IP Address", t.ip_address],
  ].map(([k, v]) => `<div class="kv-row"><span class="kv-key">${k}</span><span class="kv-val">${v}</span></div>`).join("");

  const rc = riskClass(t.risk_score);
  document.getElementById("riskScoreNum").textContent = t.risk_score;
  document.getElementById("riskScoreNum").style.color = COLORS[rc === "high" ? "high" : rc === "med" ? "med" : "low"];
  const labelEl = document.getElementById("riskLabelText");
  labelEl.textContent = data.risk_label;
  labelEl.className = "risk-label " + rc;
  drawGauge(t.risk_score, rc);

  const topReasons = data.breakdown.filter(b => b.score_contribution > 0).slice(0, 5);
  document.getElementById("whyFlagged").innerHTML = topReasons.map(r => `
    <div class="why-row"><span class="why-text">${r.reason}</span><span class="why-badge ${r.impact.toLowerCase()}">${r.impact}</span></div>`).join("")
    || `<div class="why-text">No significant risk indicators found.</div>`;

  document.querySelector("#scoreBreakdownTable tbody").innerHTML = data.breakdown.map(r => `
    <tr><td>${r.factor}</td><td>${r.impact}</td><td>${r.reason}</td><td>${r.weight}</td>
    <td style="color:${r.score_contribution >= 0 ? COLORS.high : COLORS.low}">${r.score_contribution >= 0 ? "+" : ""}${r.score_contribution}</td></tr>`).join("");

  drawShapChart(data.breakdown);
}

function drawGauge(score, rc) {
  const ctx = document.getElementById("riskGauge");
  if (charts.gauge) charts.gauge.destroy();
  const color = rc === "high" ? COLORS.high : rc === "med" ? COLORS.med : COLORS.low;
  charts.gauge = new Chart(ctx, {
    type: "doughnut",
    data: { datasets: [{ data: [score, 100 - score], backgroundColor: [color, "#1b2333"], borderWidth: 0 }] },
    options: { cutout: "78%", rotation: -90, circumference: 360, plugins: { legend: { display: false }, tooltip: { enabled: false } } },
  });
}

function drawShapChart(breakdown) {
  const ctx = document.getElementById("shapChart");
  if (charts.shap) charts.shap.destroy();
  const sorted = [...breakdown].sort((a, b) => a.score_contribution - b.score_contribution);
  charts.shap = new Chart(ctx, {
    type: "bar",
    data: {
      labels: sorted.map(r => r.factor),
      datasets: [{ data: sorted.map(r => r.score_contribution),
        backgroundColor: sorted.map(r => r.score_contribution >= 0 ? COLORS.high : COLORS.low) }],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#5c667a" }, grid: { color: "#1b2333" } },
        y: { ticks: { color: "#8892a4", font: { size: 11 } }, grid: { display: false } },
      },
    },
  });
}

// ============================================================ ALERTS
async function loadAlerts() {
  const [ov, rows] = await Promise.all([getJSON("/alerts-overview"), getJSON("/transactions?limit=200")]);
  document.getElementById("alertHigh").textContent = ov.high_risk_alerts;
  document.getElementById("alertMed").textContent = ov.medium_risk_alerts;
  document.getElementById("alertLow").textContent = ov.low_risk_alerts;

  const flagged = rows.filter(t => t.risk_score >= 30).sort((a, b) => b.risk_score - a.risk_score);
  document.querySelector("#alertsTable tbody").innerHTML = flagged.map(t => `
    <tr><td>${t.txn_id}</td><td>${t.user_id}</td><td>${fmtMoney(t.amount)}</td>
    <td class="risk-cell ${riskClass(t.risk_score)}">${t.risk_score}</td>
    <td><span class="chip ${statusChipClass(t.status)}">${t.status}</span></td>
    <td>${fmtTime(t.created_at)}</td></tr>`).join("") || `<tr><td colspan="6" class="muted">No active alerts.</td></tr>`;
}

// ============================================================ CASES
async function loadCases(statusFilter) {
  const filter = statusFilter || document.getElementById("caseStatusFilter").value;
  const [summary, cases] = await Promise.all([getJSON("/cases/summary"), getJSON("/cases?status=" + encodeURIComponent(filter))]);

  document.getElementById("caseSummaryRow").innerHTML = [
    ["Open Cases", summary.open], ["In Review", summary.in_review],
    ["Escalated", summary.escalated], ["Closed Today", summary.closed_today],
  ].map(([label, val]) => `<div class="case-summary-card"><div class="case-summary-label">${label}</div><div class="case-summary-value">${val}</div></div>`).join("");

  document.querySelector("#casesTable tbody").innerHTML = cases.map(c => `
    <tr>
      <td>${c.case_id}</td>
      <td><span class="priority-badge ${c.priority}">${c.priority}</span></td>
      <td>
        <select class="status-select" data-case="${c.case_id}">
          ${["Open", "In Review", "Escalated", "Closed"].map(s => `<option ${s === c.status ? "selected" : ""}>${s}</option>`).join("")}
        </select>
      </td>
      <td>${c.user_id}</td><td>${fmtMoney(c.amount)}</td>
      <td class="risk-cell ${riskClass(c.risk_score)}">${c.risk_score}</td>
      <td>${c.assigned_to}</td>
      <td><button class="btn-mini" data-view-txn="${c.txn_id}">View Txn</button></td>
    </tr>`).join("") || `<tr><td colspan="8" class="muted">No cases found.</td></tr>`;

  document.querySelectorAll("#casesTable .status-select").forEach(sel => {
    sel.addEventListener("change", async () => {
      await fetch(API + "/cases/" + sel.dataset.case, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: sel.value }),
      });
      loadCases();
    });
  });
  document.querySelectorAll("#casesTable [data-view-txn]").forEach(btn => {
    btn.addEventListener("click", () => openTransactionDetail(btn.dataset.viewTxn));
  });
}
document.getElementById("caseStatusFilter")?.addEventListener("change", () => loadCases());

// ============================================================ SCORE FORM
document.getElementById("scoreForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = {
    amount: parseFloat(fd.get("amount")),
    distance_km: parseFloat(fd.get("distance_km")),
    velocity_5min: parseInt(fd.get("velocity_5min")),
    account_age_days: parseFloat(fd.get("account_age_days")),
    hour: parseInt(fd.get("hour")),
    new_device: fd.get("new_device") ? 1 : 0,
    new_payee: fd.get("new_payee") ? 1 : 0,
    channel: fd.get("channel"),
    location: fd.get("location"),
  };
  const resultEl = document.getElementById("scoreResult");
  resultEl.innerHTML = `<div class="muted">Scoring...</div>`;
  try {
    const res = await fetch(API + "/score", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const data = await res.json();
    const rc = riskClass(data.risk_score);
    const color = COLORS[rc];
    const topReasons = data.breakdown.filter(b => b.score_contribution > 0).slice(0, 4);
    resultEl.innerHTML = `
      <div style="text-align:center;margin-bottom:16px;">
        <div style="font-size:42px;font-weight:700;color:${color}">${data.risk_score}</div>
        <div class="muted">/100 · <span class="chip ${statusChipClass(data.status)}">${data.status}</span></div>
        <div class="muted" style="margin-top:6px;">Saved as ${data.txn_id}</div>
      </div>
      <div class="why-list">${topReasons.map(r => `
        <div class="why-row"><span class="why-text">${r.reason}</span><span class="why-badge ${r.impact.toLowerCase()}">${r.impact}</span></div>`).join("") || "<div class='muted'>No major risk indicators.</div>"}
      </div>
      <button class="btn-secondary" style="margin-top:14px;" onclick="openTransactionDetail('${data.txn_id}')">View Full Breakdown</button>
    `;
  } catch (err) {
    resultEl.innerHTML = `<div class="muted">Error scoring transaction. Is the backend running on localhost:5000?</div>`;
  }
});

// ============================================================ MODELS VIEW
async function loadModelsView() {
  const perf = await getJSON("/model-performance");
  document.getElementById("modelPerfLarge").innerHTML = [
    ["Precision", perf.precision], ["Recall", perf.recall],
    ["F1 Score", perf.f1_score], ["AUC-ROC", perf.auc_roc],
  ].map(([label, val]) => `<div class="mp-item"><div class="mp-value">${val}</div><div class="mp-label">${label}</div></div>`).join("");

  const factors = await getJSON("/top-risk-factors");
  const ctx = document.getElementById("importanceChart");
  if (charts.importance) charts.importance.destroy();
  charts.importance = new Chart(ctx, {
    type: "bar",
    data: { labels: factors.map(f => f.factor), datasets: [{ data: factors.map(f => f.percentage), backgroundColor: COLORS.blue }] },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8892a4", font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: "#5c667a" }, grid: { color: "#1b2333" } },
      },
    },
  });
}

document.getElementById("resetDemoBtn")?.addEventListener("click", async () => {
  const statusEl = document.getElementById("resetStatus");
  statusEl.textContent = " Resetting...";
  await fetch(API + "/reset-demo", { method: "POST" });
  statusEl.textContent = " ✓ Demo data reset.";
  loadDashboard();
});

// ---------------------------------------------------------------- INIT ----
loadDashboard();
setInterval(loadDashboard, 15000); // auto-refresh every 15s to feel "live"
