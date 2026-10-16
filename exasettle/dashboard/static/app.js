let activeRunId = null;
let currentRunResults = [];
let currentSimEvents = [];
let activeTableFilter = "ALL";
let activeSimRole = "ALL";

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  setupSSE();
});

// Setup Server-Sent Events for real-time live run updates
function setupSSE() {
  const eventSource = new EventSource("/api/events");
  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      handleLiveEvent(payload);
    } catch (e) {
      console.error("SSE parse error", e);
    }
  };
  eventSource.onerror = (err) => {
    console.warn("SSE connection error; falling back to direct response handling.");
  };
}

function handleLiveEvent(evt) {
  const type = evt.event_type;
  const data = evt.data;
  const msgEl = document.getElementById("timelineStatusMessage");

  if (type === "STATUS_TRANSITION") {
    if (msgEl) msgEl.innerText = data.message;
    updateStepper(data.stage);
  }
}

function updateStepper(stage) {
  const stages = [
    "SCENARIO_CREATED",
    "SOURCE_RECORDS_GENERATED",
    "RECORDS_LOADING",
    "RECONCILIATION_RUNNING",
    "RECONCILIATION_COMPLETED",
    "AGENT_SIMULATION_RUNNING",
    "RESULTS_AVAILABLE"
  ];
  const idx = stages.indexOf(stage);
  for (let i = 0; i <= 5; i++) {
    const el = document.getElementById(`step-${i}`);
    if (!el) continue;
    if (i < idx) {
      el.className = "step-item completed";
    } else if (i === idx) {
      el.className = "step-item active";
    } else {
      el.className = "step-item";
    }
  }
}

// Preflight Health Check
async function checkHealth() {
  const container = document.getElementById("healthBadges");
  const tsEl = document.getElementById("healthTimestamp");
  if (!container) return;

  try {
    const resp = await fetch("/api/health");
    const summary = await resp.json();
    if (tsEl) tsEl.innerText = `Checked: ${new Date(summary.timestamp_utc).toLocaleTimeString()}`;

    container.innerHTML = "";
    summary.services.forEach(svc => {
      const badge = document.createElement("div");
      const statusClass = svc.status.toLowerCase().replace("_", "-");
      badge.className = `health-badge ${statusClass}`;
      badge.innerHTML = `
        <span>●</span>
        <div>
          <strong>${svc.service_name}</strong>: 
          <span>${svc.status}</span>
          ${svc.latency_ms ? `<small>(${svc.latency_ms}ms)</small>` : ""}
          <div style="font-size: 0.72rem; color: #94a3b8;">${svc.details}</div>
        </div>
      `;
      container.appendChild(badge);
    });
  } catch (err) {
    if (container) container.innerHTML = `<div class="health-badge offline">API Unreachable: ${err.message}</div>`;
  }
}

// Trigger Reconciliation Run
async function triggerRun() {
  const runBtn = document.getElementById("runBtn");
  if (runBtn) {
    runBtn.disabled = true;
    runBtn.innerText = "⏳ Running...";
  }

  const scenario = document.getElementById("scenarioSelect").value;
  const seed = parseInt(document.getElementById("seedInput").value) || 42;
  const threshold = parseFloat(document.getElementById("thresholdInput").value) || 24;
  const enginePref = document.getElementById("engineSelect").value;
  const simMode = document.getElementById("simModeSelect").value;

  const extraCount = scenario === "SCN_EXPANDED_20" ? 12 : 0;

  try {
    const resp = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario_id: scenario,
        seed: seed,
        extra_matched_count: extraCount,
        settlement_delay_threshold_hours: threshold,
        engine_preference: enginePref,
        simulation_mode: simMode
      })
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Run failed");
    }

    const data = await resp.json();
    activeRunId = data.report_metadata.run_id;
    currentRunResults = data.results;
    currentSimEvents = data.simulation_events;

    // Render all dashboard sections
    renderKPIs(data);
    renderTable();
    renderSimulationPanel();
    renderCharts(data);

    // Update active engine badge
    const engBadge = document.getElementById("activeEngineDisplay");
    if (engBadge) {
      engBadge.innerText = `Engine: ${data.engine_execution.engine} (${data.engine_execution.engine_mode})`;
      engBadge.className = data.engine_execution.is_fallback ? "engine-badge-tag fallback" : "engine-badge-tag exasol";
    }

    const msgEl = document.getElementById("timelineStatusMessage");
    if (msgEl) {
      msgEl.innerText = `Completed Run ${activeRunId}. Dataset Hash: ${data.report_metadata.dataset_hash.substring(0, 16)}... Reconciled in ${data.engine_execution.timings_ms.total_time_ms}ms.`;
    }
  } catch (err) {
    alert("Reconciliation Run Error: " + err.message);
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerText = "▶️ Start Reconciliation Run";
    }
  }
}

// Render KPIs
function renderKPIs(data) {
  const summary = data.reconciliation_summary;
  document.getElementById("kpiTotal").innerText = summary.total_transactions;
  document.getElementById("kpiMatched").innerText = summary.clean_matches;
  document.getElementById("kpiExceptions").innerText = summary.total_exceptions;
  document.getElementById("kpiAmountAtIssue").innerText = summary.total_amount_at_issue;
  document.getElementById("kpiAccuracy").innerText = `${summary.ground_truth_accuracy.accuracy_percent}%`;
  document.getElementById("kpiAccuracySub").innerText = `${summary.ground_truth_accuracy.correctly_classified}/${summary.ground_truth_accuracy.evaluated_known_cases} cases verified`;
}

// Filter results table
function setFilter(filterType) {
  activeTableFilter = filterType;
  document.querySelectorAll(".table-filters .filter-btn").forEach(btn => btn.classList.remove("active"));
  event.target.classList.add("active");
  renderTable();
}

function renderTable() {
  const tbody = document.getElementById("resultsTableBody");
  if (!tbody) return;

  let filtered = currentRunResults;
  if (activeTableFilter === "MATCHED") {
    filtered = currentRunResults.filter(r => r.classification === "MATCHED");
  } else if (activeTableFilter === "EXCEPTIONS") {
    filtered = currentRunResults.filter(r => r.classification !== "MATCHED");
  } else if (activeTableFilter === "HIGH_PRIORITY") {
    filtered = currentRunResults.filter(r => r.priority_score >= 40);
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center py-4">No transactions matching selected filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(r => {
    const gwAmt = r.gateway_amount_paise !== null ? `₹${(r.gateway_amount_paise / 100).toFixed(2)}` : "<span class='text-muted'>[MISSING]</span>";
    const bkAmt = r.bank_amount_paise !== null ? `₹${(r.bank_amount_paise / 100).toFixed(2)}` : "<span class='text-muted'>[MISSING]</span>";
    const diff = `₹${(r.difference_paise / 100).toFixed(2)}`;

    let pColor = "#10b981";
    if (r.priority_score >= 70) pColor = "#ef4444";
    else if (r.priority_score >= 40) pColor = "#f59e0b";
    else if (r.priority_score > 0) pColor = "#3b82f6";

    return `
      <tr>
        <td><strong>${r.transaction_id}</strong></td>
        <td><span class="badge badge-${r.classification}">${r.classification}</span></td>
        <td>
          <span class="priority-pill" style="background: ${pColor}20; color: ${pColor}; border: 1px solid ${pColor};">
            ${r.priority_score} / 100
          </span>
        </td>
        <td>${gwAmt}</td>
        <td>${bkAmt}</td>
        <td>${diff}</td>
        <td style="max-width: 280px; font-size: 0.8rem;">${r.applied_rule}</td>
        <td>
          <span class="badge badge-MATCHED">✓ ${r.ground_truth_label || "MATCHED"}</span>
        </td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="viewEvidence('${r.transaction_id}')">Evidence</button>
        </td>
      </tr>
    `;
  }).join("");
}

// View Evidence Drawer / Modal
async function viewEvidence(txnId) {
  if (!activeRunId) return;
  const body = document.getElementById("evidenceBody");
  document.getElementById("drilldownTxnId").innerText = txnId;
  body.innerHTML = `<div class="py-4 text-center">Loading evidence...</div>`;
  openModal("evidenceModal");

  try {
    const resp = await fetch(`/api/evidence/${activeRunId}/${txnId}`);
    const data = await resp.json();
    const res = data.reconciliation_result;
    const ev = res.evidence_json;

    body.innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;">
        <div style="background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155;">
          <h4 style="color: #38bdf8; margin-bottom: 8px;">🌐 Gateway Capture Feed</h4>
          <p><strong>Record ID:</strong> ${res.gateway_record_id || "[MISSING]"}</p>
          <p><strong>Amount:</strong> ${res.gateway_amount_paise !== null ? `₹${(res.gateway_amount_paise/100).toFixed(2)}` : "N/A"}</p>
          <p><strong>Status:</strong> ${ev.state.gateway_status || "N/A"}</p>
          <p><strong>Timestamp:</strong> ${ev.timing.gateway_timestamp || "N/A"}</p>
        </div>
        <div style="background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155;">
          <h4 style="color: #34d399; margin-bottom: 8px;">🏦 Bank Settlement Feed</h4>
          <p><strong>Record ID:</strong> ${res.bank_record_id || "[MISSING]"}</p>
          <p><strong>Amount:</strong> ${res.bank_amount_paise !== null ? `₹${(res.bank_amount_paise/100).toFixed(2)}` : "N/A"}</p>
          <p><strong>Status:</strong> ${ev.state.bank_status || "N/A"}</p>
          <p><strong>Timestamp:</strong> ${ev.timing.bank_timestamp || "N/A"}</p>
        </div>
      </div>

      <div style="background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 16px;">
        <h4 style="margin-bottom: 6px;">📐 Deterministic SQL Rule Applied</h4>
        <p style="font-family: monospace; font-size: 0.85rem; color: #fde047;">${res.applied_rule}</p>
        <p style="font-size: 0.82rem; color: #94a3b8; margin-top: 6px;">
          Settlement elapsed time: ${ev.timing.elapsed_settlement_hours}h (scenario threshold: ${ev.timing.threshold_hours}h)
        </p>
      </div>

      <div style="background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 16px;">
        <h4 style="margin-bottom: 6px;">⚖️ Operational Triage Priority Breakdown</h4>
        <p><strong>Score:</strong> ${res.priority_score} / 100</p>
        <p style="font-size: 0.85rem; color: #cbd5e1;">${res.priority_explanation}</p>
      </div>

      <div style="background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155;">
        <h4 style="margin-bottom: 6px;">🎯 Independent Ground Truth Check</h4>
        <p><strong>Planted Reason:</strong> ${data.ground_truth ? data.ground_truth.planted_reason : "N/A"}</p>
        <p><strong>Validation:</strong> <span class="badge badge-MATCHED">${res.validation_status}</span></p>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div class="text-danger">Failed to load evidence: ${err.message}</div>`;
  }
}

// Render Simulation Panel
function setSimRole(role) {
  activeSimRole = role;
  document.querySelectorAll(".sim-role-tabs .sim-tab-btn").forEach(btn => btn.classList.remove("active"));
  event.target.classList.add("active");
  renderSimulationPanel();
}

function renderSimulationPanel() {
  const container = document.getElementById("simEventsList");
  if (!container) return;

  let filtered = currentSimEvents;
  if (activeSimRole !== "ALL") {
    filtered = currentSimEvents.filter(e => e.agent_role === activeSimRole);
  }

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state">No simulated events matching selected role.</div>`;
    return;
  }

  container.innerHTML = filtered.map(ev => `
    <div class="sim-card-item role-${ev.agent_role}">
      <div class="sim-card-header">
        <span><strong>${ev.persona_name}</strong> (${ev.agent_role}) • Txn: <code>${ev.transaction_id}</code></span>
        <span class="badge badge-sim-notice">${ev.status} • SIMULATED</span>
      </div>
      <div class="sim-observation">"${ev.observation}"</div>
      <div class="sim-feedback">💬 Query/Action: ${ev.question_or_feedback}</div>
    </div>
  `).join("");
}

// Render Charts
function renderCharts(data) {
  const classCounts = data.reconciliation_summary.classification_breakdown;
  const chartEl = document.getElementById("classificationChart");
  if (!chartEl) return;

  const total = data.reconciliation_summary.total_transactions;
  chartEl.innerHTML = Object.entries(classCounts).map(([cls, cnt]) => {
    const pct = ((cnt / total) * 100).toFixed(0);
    return `
      <div class="chart-bar-row">
        <span class="chart-bar-label">${cls}</span>
        <div class="chart-bar-track">
          <div class="chart-bar-fill" style="width: ${pct}%;"></div>
        </div>
        <span style="width: 45px; text-align: right;">${cnt} (${pct}%)</span>
      </div>
    `;
  }).join("");

  // Priority Score Chart
  const prioEl = document.getElementById("priorityChart");
  if (!prioEl) return;

  let p0 = 0, pLow = 0, pMed = 0, pHigh = 0;
  data.results.forEach(r => {
    if (r.priority_score === 0) p0++;
    else if (r.priority_score < 40) pLow++;
    else if (r.priority_score < 70) pMed++;
    else pHigh++;
  });

  const pBuckets = [
    { label: "Clean (0)", count: p0, color: "#10b981" },
    { label: "Low (1-39)", count: pLow, color: "#3b82f6" },
    { label: "Medium (40-69)", count: pMed, color: "#f59e0b" },
    { label: "High (70-100)", count: pHigh, color: "#ef4444" }
  ];

  prioEl.innerHTML = pBuckets.map(b => {
    const pct = ((b.count / total) * 100).toFixed(0);
    return `
      <div class="chart-bar-row">
        <span class="chart-bar-label">${b.label}</span>
        <div class="chart-bar-track">
          <div class="chart-bar-fill" style="width: ${pct}%; background: ${b.color};"></div>
        </div>
        <span style="width: 45px; text-align: right;">${b.count} (${pct}%)</span>
      </div>
    `;
  }).join("");
}

// Export functions
function exportData(type) {
  if (!activeRunId) {
    alert("Please execute a reconciliation run before exporting.");
    return;
  }
  window.open(`/api/export/${type}/${activeRunId}`, "_blank");
}

// Modal open/close
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("open");
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("open");
}
