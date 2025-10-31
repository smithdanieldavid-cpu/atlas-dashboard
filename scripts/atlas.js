fetch("data/atlas-latest.json")
  .then(res => res.json())
  .then(data => renderAtlas(data));

function renderAtlas(d) {
  document.getElementById("updated").textContent = d.overall.date + " AEST"; // Added AEST
  const dash = document.getElementById("dashboard");

  // Main Dashboard Content
  dash.innerHTML = `
    <section>
      <p class="status-summary">Overall Status: <strong>${d.overall.status}</strong> (${d.overall.date}, AEST)</p>
      <p class="comment">${d.overall.comment}</p>
    </section>

    ${renderTable("Macro Panel — radar (live)", d.macro, ["Category", "Status", "Latest reading / note", "Action cue (what it means)"])}

    <p class="micro-composite-summary">${d.composite_summary.replace("Composite effective triggers", "Composite micro score: 4/8 micro triggers active → ≈ 2 macro-equivalents → when combined with macro this confirms Full Storm.")}</p>
    ${renderTable("Micro Pulse Panel — early-warning sensors", d.micro, ["Micro indicator", "Status", "Latest proxy / note", "Action cue"])}
    
    ${renderTable("Storm Trigger Bar — tally & verdict", d.triggers, ["Category", "Status", "Note", "Action cue"])}

    ${renderActionCues()}
    
    ${renderTriggers("Escalation Triggers (act immediately if any occur):", d.escalation_triggers)}

    ${renderInsight("Short, candid insight (my take — TL;DR)", d.short_insight)}
  `;
}

// Renders the main Macro/Micro/Trigger tables (now 4 columns)
function renderTable(title, rows, headers) {
  return `
    <section class="dashboard-section">
      <h3>${title}</h3>
      <table class="data-table">
        <thead><tr>
          ${headers.map(h => `<th>${h}</th>`).join("")}
        </tr></thead>
        <tbody>
          ${rows.map(r =>
            `<tr>
              <td>${r.name}</td>
              <td><span class="status-indicator ${r.status.toLowerCase()}"></span> ${r.status.replace('Amber→Red', '🟠→🔴')}</td>
              <td>${r.note}</td>
              <td class="action-cue">${r.action}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </section>
  `;
}

// Renders the 'Immediate Recommended Actions'
function renderActionCues() {
    // You need to manually define the rule-based actions here or pass them via JSON
    // I'm putting the list here based on your prompt text:
    const actions = [
        "Hold Storm posture now. Maintain defensive allocations (cash + short/floating duration + low-vol) — do not de-risk into equities.",
        "Liquidity: keep ≥30% of capital liquid/unlocked for opportunistic buys or to meet operational calls.",
        "Duration: avoid adding intermediate/long locks in fixed income; favour floating-rate notes and short ladders in US & AU sleeves.",
        "Gold / safe-assets: maintain or modestly increase (5–10%) in liquid form (ETF/approved vehicles) — central-bank buying validates a tactical hedge.",
        "Hedging: if you hold concentrated equity positions, buy protective puts sized to cover a 10–15% drawdown while VIX remains elevated."
    ];
    
    return `
      <section class="action-section">
        <h3>Immediate recommended actions (clear, rule-based)</h3>
        <ul>
          ${actions.map(a => `<li>${a}</li>`).join("")}
        </ul>
      </section>
    `;
}


// Renders the 'Escalation Triggers' list
function renderTriggers(title, triggers) {
    return `
      <section class="trigger-section">
        <h3>${title}</h3>
        <ul>
          ${triggers.map(t => `<li><strong>${t.name}:</strong> ${t.note}</li>`).join("")}
        </ul>
      </section>
    `;
}

// Renders the 'Short Insight' list
function renderInsight(title, insights) {
    return `
      <section class="insight-section">
        <h3>${title}</h3>
        <ul>
          ${insights.map(i => `<li>${i.text}</li>`).join("")}
        </ul>
      </section>
    `;
}