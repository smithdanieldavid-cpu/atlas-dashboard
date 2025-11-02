// scripts/atlas.js

// --- 1. STATUS AND COLOR MAPPING UTILITY ---
const getStatusDetails = (status) => {
    const s = status ? status.toUpperCase() : 'N/A';

    switch (s) {
        // --- 4-Tier Overall Statuses ---
        case 'FULL-STORM':
            return { color: 'bg-red-800 text-white border-red-900', icon: '⛈️', badge: 'bg-red-100 text-red-800', narrativeBadge: 'bg-red-600' };
        case 'SEVERE RISK':
            return { color: 'bg-red-600 text-white border-red-700', icon: '🔴', badge: 'bg-red-100 text-red-800', narrativeBadge: 'bg-red-600' };
        case 'ELEVATED RISK':
            return { color: 'bg-amber-500 text-black border-amber-600', icon: '🟡', badge: 'bg-amber-100 text-amber-800', narrativeBadge: 'bg-amber-500' };
        case 'MONITOR (GREEN)':
        case 'MONITOR':
            return { color: 'bg-green-600 text-white border-green-700', icon: '🟢', badge: 'bg-green-100 text-green-800', narrativeBadge: 'bg-green-600' };
        // --- 3-Tier Individual Indicator Statuses ---
        case 'RED':
            return { color: 'border-red-600', icon: '🟥', badge: 'bg-red-100 text-red-800', narrativeBadge: 'bg-red-600' };
        case 'AMBER':
            return { color: 'border-amber-600', icon: '🟠', badge: 'bg-amber-100 text-amber-800', narrativeBadge: 'bg-amber-500' }; 
        case 'GREEN':
            return { color: 'border-green-600', icon: '✅', badge: 'bg-green-100 text-green-800', narrativeBadge: 'bg-green-600' };
        case 'N/A':
        default:
            return { color: 'bg-gray-400 text-white border-gray-500', icon: '⚪', badge: 'bg-gray-100 text-gray-800', narrativeBadge: 'bg-gray-400' };
    }
};


// --- 2. DATA FETCHING ---
const ATLAS_DATA_PATH = 'data/atlas-latest.json'; 
// NEW: Path to the archive file
const ARCHIVE_DATA_PATH = 'data/atlas-archive.json';

// NEW: Global variables for infinite scroll state
let allArchivePosts = [];
const POSTS_PER_LOAD = 5;
let currentPostIndex = 0;

async function fetchAtlasData() {
    try {
        const response = await fetch(ATLAS_DATA_PATH);
        if (!response.ok) {
            if (response.status === 404) {
                console.error(`Atlas data file not found at: ${ATLAS_DATA_PATH}`);
            }
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch Atlas data:", error);
        // Show error message on the main status card
        if (document.getElementById('overallStatusCard')) {
             document.getElementById('overallStatusCard').innerHTML = `
                <div class="text-center text-red-600 font-bold">
                    ERROR: Could not load risk data. Check console (F12).
                </div>
            `;
        }
        return null;
    }
}


// --- 3. RENDERING FUNCTIONS (DASHBOARD) ---

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
        // Ensure only the top line of the daily narrative is shown for the summary
        const summaryText = overall.daily_narrative ? overall.daily_narrative.split('\n')[0] : overall.narrative_summary;
        narrativeSummary.textContent = summaryText || overall.composite_summary;
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
 * CRITICAL FIX: Adds high visual prominence for N/A or Error statuses.
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
        
        // Ensure a value exists for display
        const indicatorValue = indicator.value || 'N/A'; 
        
        // --- START OF HIGH VISIBILITY FIX LOGIC (The updated part) ---
        const currentStatus = (indicator.status || '').toUpperCase();
        let displayNote;
        let sourceLink = ''; // Initialized outside the conditional to ensure clean display

        // Check for missing or erroneous data status
        if (currentStatus === 'N/A' || currentStatus === 'ERROR') {
            // HIGH VISIBILITY ALARM for missing/errored data
            displayNote = `
                <span class="font-bold text-red-600">🔴 DATA ${currentStatus}:</span> 
                <span class="text-base font-bold">${indicator.note}</span> 
                <span class="text-sm text-gray-500">(Action: ${indicator.action})</span>
            `;
            // sourceLink remains "" (empty) to suppress the [Source] button
        } else {
            // Normal display when data is Green, Amber, or Red
            const sourceURL = indicator.source_link || indicator.source || indicator.url;
            
            // Create the hyperlinked source tag only if a valid URL exists
            sourceLink = sourceURL && sourceURL.startsWith('http') 
                               ? `<a href="${sourceURL}" target="_blank" rel="noopener noreferrer" class="text-indigo-600 hover:text-indigo-800">[Source]</a>`
                               : '';

            displayNote = `
                <span class="font-semibold">${indicator.note}</span>. 
                Action: ${indicator.action} 
                ${sourceLink}
            `;
        }
        // --- END OF HIGH VISIBILITY FIX LOGIC ---

        row.innerHTML = `
            <td class="w-1/4 px-3 py-3 text-sm font-medium text-gray-900">
                <span class="mr-2">${details.icon}</span>${indicator.name}
            </td>

            <td class="w-24 px-3 py-3 text-sm font-semibold text-gray-700 whitespace-nowrap">
                ${indicatorValue} 
                <span class="px-2 py-0.5 ml-2 text-xs font-bold rounded-full uppercase ${details.badge}">
                    ${indicator.status || 'N/A'}
                </span>
            </td>

            <td class="px-3 py-3 text-sm text-gray-700">
                ${displayNote}
            </td>
        `;
        tableBody.appendChild(row);
    });
}


/**
 * Renders simple bulleted lists for actions, watch list, and insights.
 */
function renderList(listId, items, type) {
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
            // Note: Escalation Triggers list contains 'name' and 'note' fields
            text = `${item.name}: ${item.note}`; 
            icon = '🚨 ';
        } else if (type === 'insight') {
            text = item.text; // Short Insight list contains 'text' field
            icon = '💡 ';
            li.className = 'text-sm italic';
        }

        li.innerHTML = `${icon}<span>${text}</span>`; 
        list.appendChild(li);
    });
}


// --- 4. NARRATIVE PAGE RENDERING ---

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
            narrativeContent.innerHTML = paragraphs.map(p => `<p class="mb-4">${p.trim()}</p>`).join('');
        }
        
        // Update footer date
        document.getElementById('footerDate').textContent = overall.date;
    });
}

// --- 5. ARCHIVE PAGE RENDERING (NEW INFINITE SCROLL LOGIC) ---

/**
 * Renders a batch of historical posts and advances the index.
 * @param {number} startIndex - The starting index in allArchivePosts.
 */
function renderArchivePosts(startIndex) {
    const container = document.getElementById('archiveContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const endOfArchive = document.getElementById('endOfArchive');

    const postsToRender = allArchivePosts.slice(startIndex, startIndex + POSTS_PER_LOAD);
    
    // Hide loading indicator
    if (loadingIndicator) loadingIndicator.style.display = 'none';

    if (postsToRender.length === 0 && startIndex > 0) {
        // Show end message only if we have rendered at least one post
        if (endOfArchive) endOfArchive.classList.remove('hidden');
        return;
    } else if (postsToRender.length === 0 && startIndex === 0) {
        // Handle an empty archive file
         if (container) container.innerHTML = "<p class='text-gray-500'>No historical narratives found in the archive.</p>";
         return;
    }


    postsToRender.forEach(post => {
        const details = getStatusDetails(post.status);
        const postElement = document.createElement('article');
        
        // Use a simple date format for the archive
        // Check if date contains a space (time), if so, split it.
        const datePart = post.date ? post.date.split(' ')[0] : 'N/A';
        const displayDate = new Date(datePart).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

        postElement.className = 'border-b border-gray-200 pb-10';
        
        // Replace newline characters with <br> for HTML rendering, wrapping paragraphs in <p> tags
        const narrativeHTML = (post.daily_narrative || "No detailed narrative provided.")
            .split('\n\n')
            .map(p => `<p class="mb-3">${p.trim()}</p>`)
            .join('');

        postElement.innerHTML = `
            <div class="flex items-start justify-between mb-4">
                <h2 class="text-2xl font-bold text-gray-900">${details.icon} Atlas Update: ${displayDate}</h2>
                <span class="mt-1 inline-block px-3 py-1 text-xs font-bold rounded-full text-white ${details.narrativeBadge}">
                    ${post.status} (Score: ${post.score.toFixed(1)})
                </span>
            </div>
            <p class="text-base text-gray-700 leading-relaxed">${narrativeHTML}</p>
        `;
        container.appendChild(postElement);
    });

    // Update the index for the next load
    currentPostIndex += POSTS_PER_LOAD;
}

/**
 * Initializes the archive page, fetches all data, and sets up scroll listener.
 */
async function initializeArchivePage() {
    const response = await fetch(ARCHIVE_DATA_PATH);
    if (!response.ok) {
        console.error("Failed to fetch archive data.");
        document.getElementById('archiveContainer').innerHTML = "<p class='text-red-500'>Error loading archive. Check the console and confirm 'data/atlas-archive.json' exists.</p>";
        return;
    }
    
    // Reset state in case this function is called multiple times (though shouldn't be in this setup)
    allArchivePosts = await response.json();
    currentPostIndex = 0;
    
    // 1. Initial render of the first batch
    renderArchivePosts(currentPostIndex);

    // 2. Setup Infinite Scroll Listener
    const scrollHandler = () => {
        // Check if the user is near the bottom of the page (e.g., within 1000px)
        if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 1000) {
            
            // Remove the handler temporarily to prevent multiple simultaneous calls
            window.removeEventListener('scroll', scrollHandler);

            if (currentPostIndex < allArchivePosts.length) {
                // Show loading indicator
                const loadingIndicator = document.getElementById('loadingIndicator');
                if (loadingIndicator) loadingIndicator.style.display = 'block';

                // Render the next batch after a short delay (for visual effect)
                setTimeout(() => {
                    renderArchivePosts(currentPostIndex);
                    // Re-add the scroll listener only if there are more posts to load
                    if (currentPostIndex < allArchivePosts.length) {
                        window.addEventListener('scroll', scrollHandler);
                    }
                }, 500);
            }
        }
    };

    // Add the scroll listener
    window.addEventListener('scroll', scrollHandler);
}


// --- 6. MAIN INITIALIZATION LOGIC ---

// Determine which initialization function to run based on the current page
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    
    if (path.includes('narrative.html')) {
        initializeNarrativePage();
    } else if (path.includes('archive.html')) {
        initializeArchivePage(); // <-- NEW: Load archive logic
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