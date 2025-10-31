fetch("/data/atlas-latest.json")
  .then(res => res.json())
  .then(data => renderAtlas(data));

function renderAtlas(d) {
  // 1. FIX: Update the date in the new location (lastUpdated) and footer (footerDate)
  document.getElementById("lastUpdated").textContent = 'Updated: ' + d.overall.date + " AEST";
  document.getElementById("footerDate").textContent = d.overall.date + " AEST";
  
  // 2. Populate the Banner Badge (Optional - based on the old content)
  const badgeHtml = `
    <span class="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium 
    ${d.overall.status === 'FULL-STORM' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}">
      ${d.overall.status} — ${d.overall.comment.split('—')[0].trim()}
    </span>
  `;
  document.getElementById("bannerBadge").innerHTML = badgeHtml;


  // 3. Populate Macro Table
  // NOTE: Only rendering the table body (tbody) now. The old renderTable needs to be adapted.
  document.getElementById("macroTable").innerHTML = renderRows(d.macro);
  
  // 4. Populate Micro Panel and Summary
  const microSummaryText = d.overall.composite_summary.replace(
      "Composite effective triggers", 
      "Composite micro score: 4/8 micro triggers active → ≈ 2 macro-equivalents → when combined with macro this confirms Full Storm."
  );
  // Using a temporary div for the summary text for now, or just placing it above the micro table.
  // We'll use the aside for the triggers.

  document.getElementById("microTable").innerHTML = renderRows(d.micro);

  // 5. Populate Side Column (Storm Triggers, Actions, Escalation Watch)
  
  // Storm Trigger Bar
  const triggerSummary = document.getElementById("triggerSummary");
  const triggerDetails = document.getElementById("triggerDetails");
  
  triggerSummary.innerHTML = `Overall Status: <strong>${d.overall.status}</strong>`;
  triggerDetails.innerHTML = d.overall.composite_summary;

  // Immediate Actions
  document.getElementById("actionList").innerHTML = renderActionCues();
  
  // Escalation Watch
  document.getElementById("watchList").innerHTML = renderTriggers(d.escalation_triggers);
  
  // Insight is not used in the new HTML, but you could add a section for it if desired.
}


// RE-FACTORED: Now renders only the table rows (<tbody> content)
function renderRows(rows) {
  return rows.map(r =>
    `<tr>
      <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">${r.name}</td>
      <td class="w-24 px-3 py-2 whitespace-nowrap text-sm">
        <span class="status-dot ${r.status.toLowerCase()}"></span> 
        ${r.status.replace('Amber→Red', '🟠→🔴')}
      </td>
      <td class="px-3 py-2 text-sm text-gray-500">
          ${r.note}
          <div class="mt-1 text-xs italic text-gray-400">${r.action}</div>
      </td>
    </tr>`).join("");
}

// RE-FACTORED: Renders the 'Immediate Recommended Actions' list items (<li> only)
function renderActionCues() {
    const actions = [
        "Hold Storm posture now. Maintain defensive allocations (cash + short/floating duration + low-vol) — do not de-risk into equities.",
        "Liquidity: keep ≥30% of capital liquid/unlocked for opportunistic buys or to meet operational calls.",
        "Duration: avoid adding intermediate/long locks in fixed income; favour floating-rate notes and short ladders in US & AU sleeves.",
        "Gold / safe-assets: maintain or modestly increase (5–10%) in liquid form (ETF/approved vehicles) — central-bank buying validates a tactical hedge.",
        "Hedging: if you hold concentrated equity positions, buy protective puts sized to cover a 10–15% drawdown while VIX remains elevated."
    ];
    
    // Return only <li> elements
    return actions.map(a => `<li>${a}</li>`).join("");
}


// RE-FACTORED: Renders the 'Escalation Triggers' list items (<li> only)
function renderTriggers(triggers) {
    // Return only <li> elements
    return triggers.map(t => `<li><strong>${t.name}:</strong> ${t.note}</li>`).join("");
}

// The renderInsight function is no longer needed unless you add a specific <ul> for it.
// The data from the old 'triggers' section is now used to populate triggerSummary/triggerDetails.

// You will also need to update your CSS to define the status-dot colors (Red, Amber, Green).