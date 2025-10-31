fetch("data/atlas-latest.json") // Assuming your JSON is in a 'data' folder now
  .then(res => res.json())
  .then(data => renderAtlas(data));

function renderAtlas(d) {
  // 1. FIX: Update the date in the new location (lastUpdated) and footer (footerDate)
  document.getElementById("lastUpdated").textContent = 'Updated: ' + d.overall.date + " AEST";
  document.getElementById("footerDate").textContent = d.overall.date + " AEST";
  
  // 2. Populate the Banner Badge 
  const badgeHtml = `
    <span class="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium 
    ${d.overall.status === 'FULL-STORM' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}">
      ${d.overall.status} — ${d.overall.comment.split('—')[0].trim()}
    </span>
  `;
  document.getElementById("bannerBadge").innerHTML = badgeHtml;


  // 3. Populate Macro Table (Table Body)
  document.getElementById("macroTable").innerHTML = renderRows(d.macro);
  
  // 4. Populate Micro Table (Table Body)
  document.getElementById("microTable").innerHTML = renderRows(d.micro);

  // 5. Populate Side Column (Storm Triggers)
  const triggerSummary = document.getElementById("triggerSummary");
  const triggerDetails = document.getElementById("triggerDetails");
  
  triggerSummary.innerHTML = `Overall Status: <strong>${d.overall.status}</strong>`;
  
  // Custom message for the details section
  const microCompositeSummary = d.overall.composite_summary.replace(
      "Composite effective triggers", 
      "Micro pulse score: 4/8 active. Composite total triggers"
  );
  triggerDetails.innerHTML = microCompositeSummary;
  
  // 6. Populate Immediate Actions List
  document.getElementById("actionList").innerHTML = renderActionCues();
  
  // 7. Populate Escalation Watch List
  document.getElementById("watchList").innerHTML = renderTriggers(d.escalation_triggers);
}


// Renders only the table rows (<tbody> content)
function renderRows(rows) {
  return rows.map(r =>
    `<tr class="hover:bg-gray-50">
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

// Renders the 'Immediate Recommended Actions' list items (<li> only)
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


// Renders the 'Escalation Triggers' list items (<li> only)
function renderTriggers(triggers) {
    // Return only <li> elements
    return triggers.map(t => `<li><strong>${t.name}:</strong> ${t.note}</li>`).join("");
}