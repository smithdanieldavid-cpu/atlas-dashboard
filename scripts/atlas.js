// scripts/atlas.js

// 1. --- STATUS AND COLOR MAPPING UTILITY ---
const getStatusDetails = (status) => {
    const s = status.toUpperCase();

    switch (s) {
        // --- 4-Tier Overall Statuses ---
        case 'FULL-STORM':
            return { color: 'bg-red-800 text-white border-red-900', icon: '⛈️', badge: 'bg-red-100 text-red-800', narrativeBadge: 'bg-red-600' };
        case 'SEVERE RISK':
            return { color: 'bg-red-600 text-white border-red-700', icon: '🔴', badge: 'bg-red-100 text-red-800', narrativeBadge: 'bg-red-600' };
        case 'ELEVATED RISK':
            return { color: 'bg-amber-500 text-black border-amber-600', icon: '🟡', badge: 'bg-amber-100 text-amber-800', narrativeBadge: 'bg-amber-500' };
        case 'MONITOR (GREEN)':
            return { color: 'bg-green-600 text-white border-green-700', icon: '🟢', badge: 'bg-green-100 text-green-800', narrativeBadge: 'bg-green-600' };
        // --- 3-Tier Individual Indicator Statuses ---
        case 'RED':
            return { color: 'border-red-600', icon: '🟥', badge: 'bg-red-100 text-red-800', narrativeBadge: 'bg-red-600' };
        case 'AMBER':
            return { color: 'border-amber-600', icon: '🟠', badge: 'bg-amber-100 text-amber-800', narrativeBadge: 'bg-amber-500' }; 
        case 'GREEN':
            return { color: 'border-green-600', icon: '✅', badge: 'bg-green-100 text-green-800', narrativeBadge: 'bg-green-600' };
        default:
            return { color: 'bg-gray-400 text-white border-gray-500', icon: '⚪', badge: 'bg-gray-100 text-gray-800', narrativeBadge: 'bg-gray-400' };
    }
};


// 2. --- DATA FETCHING ---
const ATLAS_DATA_PATH = 'data/atlas-latest.json'; 

async function fetchAtlasData() {
    try {
        const response = await fetch(ATLAS_DATA_PATH);
        if (!response.ok) {
            if (response.status === 404) {
                console.error(`Atlas data file not found at: ${ATLAS_DATA_PATH}`);
                return null;
            }
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch Atlas data:", error);
        if (document.getElementById('overallStatusCard')) {
             document.getElementById('overallStatusCard').innerHTML = `
                <div class="text-center text-red-600 font-bold">
                    ERROR: Could not load risk data. Check console for details (F12).
                </div>
            `;
        }
        return null;
    }
}


// 3. --- RENDERING FUNCTIONS (DASHBOARD) ---

/**
 * Updates the overall status card and the NEW narrative summary.
 * @param {object} overall - The overall status object from the JSON.
 */
function renderOverallStatus(overall) {
    const card = document.getElementById('overallStatusCard');
    const details = getStatusDetails(overall.status);

    // Apply main color and structural classes to the card container
    if (card) {
        card.className = `p-6 mb-8 rounded-xl shadow-2xl border-4 transform transition duration-500 hover:scale-[1.01] hover:shadow-2xl ${details.color}`;
        
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
    }

    // Update the NEW narrative summary on the main dashboard
    const narrativeSummary = document.getElementById('narrativeSummaryText');
    if (narrativeSummary) {
        narrativeSummary.textContent = overall.narrative_summary || overall.composite_summary;
    }
    
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
        
        // Corrected logic to check for source_link, source, or url
        const sourceURL = indicator.source_link || indicator.source || indicator.url;
        
        // Create the hyperlinked source tag only if a URL exists
        const sourceLink = sourceURL 
            ? `<a href="${sourceURL}" target="_blank" rel="noopener noreferrer" class="text-indigo-600 hover:text-indigo-800">[Source]</a>`
            : ''; 

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
                <span class="font-semibold">${indicator.note}</span>. Action: ${indicator.action} ${sourceLink}
            </td>
        `;
        tableBody.appendChild(row);
    });
}

/**
 * Renders simple bulleted lists for actions, watch list, and insights.
 */
function renderList(listId, items, type) {
    // ... (This function remains the same as previous versions) ...
    const list = document.getElementById(listId);
    if (!list) return;
    list.innerHTML = ''; 

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

        li.innerHTML = `${icon}<span>${text}</span>`; 
        list.appendChild(li);
    });
}


// 4. --- NARRATIVE PAGE RENDERING ---

/**
 * Renders the full narrative content on the narrative.html page.
 */
function initializeNarrativePage() {
    fetchAtlasData().then(data => {
        if (!data) return;

        const overall = data.overall;
        const details = getStatusDetails(overall.status);

        // Set title, date, and status badge
        document.getElementById('narrativeTitle').textContent = `${overall.status} Risk Posture Analysis`;
        document.getElementById('narrativeDate').textContent = `Updated: ${overall.date}`;
        
        const statusBadge = document.getElementById('narrativeStatusBadge');
        statusBadge.textContent = `${overall.status} (Score: ${overall.score.toFixed(1)} / ${overall.max_score.toFixed(1)})`;
        statusBadge.className = `mt-4 inline-block px-3 py-1 text-sm font-bold rounded-full text-white ${details.narrativeBadge}`;

        // Insert the full narrative text. We replace newline characters with <br> for HTML rendering.
        const narrativeContent = document.getElementById('fullNarrativeContent');
        if (narrativeContent) {
            // Using a simple split/join to wrap paragraphs in <p> tags for better formatting
            const paragraphs = overall.daily_narrative ? overall.daily_narrative.split('\n\n') : ["No detailed narrative provided for this update."];
            narrativeContent.innerHTML = paragraphs.map(p => `<p class="mb-4">${p}</p>`).join('');
        }
        
        // Update footer date
        document.getElementById('footerDate').textContent = overall.date;
    });
}


// 5. --- MAIN INITIALIZATION LOGIC ---

// Determine which initialization function to run based on the current page
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    
    if (path.includes('narrative.html')) {
        initializeNarrativePage();
    } else {
        // Default to dashboard initialization (index.html)
        initializeDashboard();
    }
});


async function initializeDashboard() {
    const data = await fetchAtlasData();
    if (!data) return;

    // 1. Overall Status Card (includes narrative_summary update)
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