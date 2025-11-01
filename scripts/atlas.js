// scripts/atlas.js

// 1. --- STATUS AND COLOR MAPPING UTILITY ---
/**
 * Maps the risk status string from the back-end JSON to a colour and icon, 
 * using Tailwind CSS classes for styling.
 */
const getStatusDetails = (status) => {
  // Normalize status to uppercase for consistent matching
  const s = status.toUpperCase();

  switch (s) {
      // --- 4-Tier Overall Statuses ---
      case 'FULL-STORM':
          // Extreme Risk
          return { 
              color: 'bg-red-800 text-white border-red-900', 
              icon: '⛈️', 
              badge: 'bg-red-100 text-red-800' 
          };
      case 'SEVERE RISK':
          // High Risk
          return { 
              color: 'bg-red-600 text-white border-red-700', 
              icon: '🔴', 
              badge: 'bg-red-100 text-red-800' 
          };
      case 'ELEVATED RISK':
          // Moderate Risk
          return { 
              color: 'bg-amber-500 text-black border-amber-600', 
              icon: '🟡', 
              badge: 'bg-amber-100 text-amber-800' 
          };
      case 'MONITOR (GREEN)':
          // Low Risk
          return { 
              color: 'bg-green-600 text-white border-green-700', 
              icon: '🟢', 
              badge: 'bg-green-100 text-green-800' 
          };

      // --- 3-Tier Individual Indicator Statuses ---
      case 'RED':
          // Individual Indicator Red
          return { 
              color: 'border-red-600', 
              icon: '🟥', 
              badge: 'bg-red-100 text-red-800' 
          };
      case 'AMBER':
          // Individual Indicator Amber
          return { 
              color: 'border-amber-600', 
              icon: '🟠', 
              badge: 'bg-amber-100 text-amber-800' 
          }; 
      case 'GREEN':
          // Individual Indicator Green
          return { 
              color: 'border-green-600', 
              icon: '✅', 
              badge: 'bg-green-100 text-green-800' 
          };
          
      default:
          // Default/Unknown Status
          return { 
              color: 'bg-gray-400 text-white border-gray-500', 
              icon: '⚪', 
              badge: 'bg-gray-100 text-gray-800' 
          };
  }
};


// 2. --- DATA FETCHING ---
const ATLAS_DATA_PATH = 'data/atlas-latest.json'; 

async function fetchAtlasData() {
  try {
      // Fetch the JSON file relative to index.html
      const response = await fetch(ATLAS_DATA_PATH);
      if (!response.ok) {
          // Throw a specific error if the file isn't found (HTTP 404)
          if (response.status === 404) {
              console.error(`Atlas data file not found at: ${ATLAS_DATA_PATH}`);
              return null;
          }
          throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return await response.json();
  } catch (error) {
      console.error("Failed to fetch Atlas data:", error);
      // Display a simple error message on the page if fetch fails
      document.getElementById('overallStatusCard').innerHTML = `
          <div class="text-center text-red-600 font-bold">
              ERROR: Could not load risk data. Check console for details (F12).
          </div>
      `;
      return null;
  }
}


// 3. --- RENDERING FUNCTIONS ---

/**
* Updates the overall status card with the score, status, and summary.
* @param {object} overall - The overall status object from the JSON.
*/
function renderOverallStatus(overall) {
  const card = document.getElementById('overallStatusCard');
  const details = getStatusDetails(overall.status);

  // Apply main color and structural classes to the card container
  card.className = `p-6 mb-8 rounded-xl shadow-2xl border-4 transform transition duration-500 hover:scale-[1.01] hover:shadow-2xl ${details.color}`;
  
  // INJECT THE FINAL, SMALLER CONTENT (text-base, text-2xl, text-sm, text-xs)
  card.innerHTML = `
      <div class="flex justify-between items-center mb-2">
          <h2 class="text-base font-semibold uppercase">
              ${details.icon} ${overall.status}
          </h2>
          <span class="text-2xl font-mono font-bold">
              ${overall.score.toFixed(1)} <span class="text-sm font-normal opacity-70">/${overall.max_score.toFixed(1)}</span>
          </span>
      </div>
      <p class="text-xs font-medium opacity-90">${overall.comment}</p>
      <p class="mt-4 text-xs font-light italic">${overall.composite_summary}</p>
  `;
  
  // Update the other side-bar elements
  document.getElementById('triggerSummary').textContent = `${overall.status} (Score: ${overall.score.toFixed(1)} / ${overall.max_score.toFixed(1)})`;
  document.getElementById('triggerDetails').textContent = overall.comment;
  
  // Update the last updated time in the header/footer
  document.getElementById('lastUpdated').textContent = `Last Update: ${overall.date}`;
  document.getElementById('footerDate').textContent = overall.date;
}

/**
* Creates and inserts rows into the specified table (Macro or Micro).
* @param {string} tableId - 'macroTable' or 'microTable'.
* @param {Array<object>} indicators - List of indicator objects.
*/
function renderIndicatorTable(tableId, indicators) {
  const tableBody = document.getElementById(tableId);
  if (!tableBody) return;
  tableBody.innerHTML = ''; // Clear existing rows

  indicators.forEach(indicator => {
      const details = getStatusDetails(indicator.status);
      
      const row = document.createElement('tr');
      row.className = 'hover:bg-gray-50';
      
      row.innerHTML = `
          <td class="w-1/3 px-3 py-3 text-sm font-medium text-gray-900">
              <span class="mr-2">${details.icon}</span>${indicator.name}
          </td>
          <td class="w-24 px-3 py-3">
              <span class="px-2 py-0.5 text-xs font-bold rounded-full uppercase ${details.badge}">
                  ${indicator.status}
              </span>
          </td>
          <td class="px-3 py-3 text-sm text-gray-700">
              <span class="font-semibold">${indicator.note}</span>. Action: ${indicator.action}
          </td>
      `;
      tableBody.appendChild(row);
  });
}

/**
* Renders simple bulleted lists for actions, watch list, and insights.
* @param {string} listId - The ID of the UL element.
* @param {Array<string> | Array<object>} items - List of strings or objects (for insights/escalations).
* @param {string} type - 'action', 'watch', or 'insight' to choose the list style.
*/
function renderList(listId, items, type) {
  const list = document.getElementById(listId);
  if (!list) return;
  list.innerHTML = ''; // Clear existing items

  items.forEach(item => {
      const li = document.createElement('li');
      let text = item;
      let icon = '';
      
      if (type === 'action') {
          icon = '✅ ';
      } else if (type === 'watch') {
          text = `${item.name}: ${item.note}`;
          icon = '🚨 ';
      } else if (type === 'insight') {
          text = item.text;
          icon = '💡 ';
          li.className = 'text-sm italic';
      }

      // Use innerHTML to allow for the emoji icon
      li.innerHTML = `${icon}<span>${text}</span>`; 
      list.appendChild(li);
  });
}


// 4. --- MAIN INITIALIZATION FUNCTION ---
async function initializeDashboard() {
  const data = await fetchAtlasData();
  if (!data) return;

  // 1. Overall Status Card
  renderOverallStatus(data.overall);

  // 2. Macro and Micro Indicators
  renderIndicatorTable('macroTable', data.macro);
  renderIndicatorTable('microTable', data.micro);

  // 3. Actions, Watch List, and Insights
  renderList('actionList', data.actions, 'action');
  renderList('watchList', data.escalation_triggers, 'watch');
  renderList('insightList', data.short_insight, 'insight');

  console.log("Atlas Dashboard successfully rendered data.");
}

// Ensure the HTML DOM is fully loaded before attempting to manipulate any elements.
document.addEventListener('DOMContentLoaded', initializeDashboard);