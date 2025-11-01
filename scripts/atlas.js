// scripts/atlas.js

// --- 1. CORE DATA STRUCTURES (Legend and Utility) ---

// LEGEND DATA (Defined client-side as it is static explanation of the model)
const legendData = [
  {
      status: 'RED',
      class: 'red',
      description: 'Risk Score ≥ 0.7. High probability of systemic stress. Adds **1.0 (Macro)** or **0.5 (Micro)** to Storm Trigger Bar.',
  },
  {
      status: 'AMBER',
      class: 'amber',
      description: 'Risk Score ≥ 0.4. Elevated risk level. Monitor carefully.',
  },
  {
      status: 'GREEN',
      class: 'green',
      description: 'Risk Score < 0.4. Normal/Low risk level. Stable conditions.',
  },
];


// --- 2. DATA FETCHING (AS PROVIDED BY USER) ---

// Initial data fetch and rendering
document.addEventListener('DOMContentLoaded', () => {
  // Assuming your JSON is in a 'data' folder now
  fetch("data/atlas-latest.json") 
      .then(res => {
          if (!res.ok) {
              // Handle 404 or other errors
              console.error("Failed to fetch atlas data:", res.statusText);
              return Promise.reject('Data fetch failed');
          }
          return res.json();
      })
      .then(data => {
          renderAtlas(data);
          setupEventHandlers(); // Setup events after the initial render
      })
      .catch(error => {
          console.error("Error during dashboard initialization:", error);
          // Optionally update the UI to show a loading error
          document.getElementById("lastUpdated").textContent = 'Data Load Error';
      });
});


// --- 3. MAIN RENDERING FUNCTION ---

function renderAtlas(d) {
  // 1. Update the date in the new location (lastUpdated) and footer (footerDate)
  const updateTime = d.overall.date + " AEST";
  document.getElementById("lastUpdated").textContent = 'Updated: ' + updateTime;
  document.getElementById("footerDate").textContent = updateTime;
  
  // 2. Populate the Banner Badge 
  const isRed = d.overall.status.includes('RED') || d.overall.status.includes('FULL-STORM');
  const badgeClass = isRed ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800';

  const badgeHtml = `
      <span class="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium ${badgeClass}">
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
  
  // Check if score is available, otherwise use status
  let summaryText = `Overall Status: <strong>${d.overall.status}</strong>`;
  if (d.overall.score !== undefined) {
      summaryText = `
          <span class="text-2xl font-bold ${isRed ? 'text-red-600' : 'text-amber-600'}">
              ${d.overall.score.toFixed(1)} / ${d.overall.max_score.toFixed(1)} points
          </span>
          <div class="text-lg font-semibold mt-1">${d.overall.status}</div>
      `;
  }
  triggerSummary.innerHTML = summaryText;

  // Use the official composite summary from the data
  triggerDetails.innerHTML = d.overall.composite_summary;
  
  // 6. Populate Immediate Actions List (Uses hardcoded recommendations)
  document.getElementById("actionList").innerHTML = renderActionCues();
  
  // 7. Populate Escalation Watch List
  document.getElementById("watchList").innerHTML = renderTriggers(d.escalation_triggers);

  // 8. Populate the Atlas Rating Legend
  renderLegend(); 
}


// --- 4. HELPER RENDERING FUNCTIONS ---

/**
* Renders only the table rows (<tbody> content).
* @param {Array} rows - Array of indicator objects.
* @returns {string} HTML string for table rows.
*/
function renderRows(rows) {
  return rows.map(r =>
      // Use index for alternating row color if needed, but for now stick to hover
      `<tr class="hover:bg-gray-100">
          <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">${r.name}</td>
          <td class="w-24 px-3 py-2 whitespace-nowrap text-sm font-semibold text-gray-800">
              <span class="status-dot ${r.status.toLowerCase().replace('→red', '')}"></span> 
              ${r.status.replace('Amber→Red', '🟠→🔴')}
          </td>
          <td class="px-3 py-2 text-sm text-gray-500">
              ${r.note}
              <div class="mt-1 text-xs italic text-gray-400">
                  ${r.action}
                  ${r.source_link ? `<a href="${r.source_link}" target="_blank" rel="noopener noreferrer" 
                  class="text-indigo-500 hover:text-indigo-600 underline **ml-2**">[Source]</a>` : ''}
              </div>
          </td>
      </tr>`).join("");
}

/**
* Renders the 'Immediate Recommended Actions' list items (<li> only).
* @returns {string} HTML string for action list items.
*/
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

/**
* Renders the 'Escalation Triggers' list items (<li> only).
* @param {Array} triggers - Array of escalation trigger objects.
* @returns {string} HTML string for trigger list items.
*/
function renderTriggers(triggers) {
  // Return only <li> elements
  return triggers.map(t => `<li><strong>${t.name}:</strong> ${t.note}</li>`).join("");
}

/**
* Renders the Legend panel based on static legendData.
*/
function renderLegend() {
  const legendDiv = document.getElementById('ratingLegend');
  if (!legendDiv) return;

  legendDiv.innerHTML = legendData.map(item => `
      <div class="flex items-start space-x-2">
          <span class="status-dot ${item.class} flex-shrink-0 mt-1"></span>
          <p class="text-xs text-gray-700 leading-snug">
              <span class="font-bold text-gray-900">${item.status}:</span> ${item.description}
          </p>
      </div>
  `).join('');
}


// --- 5. EVENT HANDLERS (Copy Share Link) ---

function setupEventHandlers() {
  const copyButton = document.getElementById('copyShareLink');
  if (copyButton) {
      copyButton.addEventListener('click', async () => {
          const url = window.location.href;
          try {
              await navigator.clipboard.writeText(url);
              
              // Temporary visual feedback
              const originalText = copyButton.innerHTML;
              copyButton.innerHTML = 'Link Copied! ✅';
              
              setTimeout(() => {
                  copyButton.innerHTML = originalText;
              }, 1500); // Revert after 1.5 seconds

          } catch (err) {
              console.error('Failed to copy text: ', err);
              alert('Could not automatically copy link. Please copy the URL from your browser address bar.');
          }
      });
  }
}