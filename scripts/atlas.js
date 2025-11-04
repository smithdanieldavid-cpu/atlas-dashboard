// scripts/atlas.js

// --- 1. STATUS AND COLOR MAPPING UTILITY ---
const getStatusDetails = (status) => {
    const s = status ? status.toUpperCase() : 'N/A';

    switch (s) {
        // --- 4-Tier Overall Statuses (ALIGNED WITH PYTHON OUTPUT) ---
        case '🔴 HIGH RISK':
        case 'SEVERE RISK':
        case 'FULL-STORM': // Kept for completeness, though not used by Python now
            return { color: 'bg-red-600 text-white border-red-700', icon: '🔴', badge: 'bg-red-100 text-red-800', narrativeBadge: 'bg-red-600' };
        
        case '🟠 ELEVATED RISK':
            return { color: 'bg-amber-500 text-black border-amber-600', icon: '🟠', badge: 'bg-amber-100 text-amber-800', narrativeBadge: 'bg-amber-500' };
            
        case '🟡 WATCH':
            return { color: 'bg-yellow-500 text-black border-yellow-600', icon: '🟡', badge: 'bg-yellow-100 text-yellow-800', narrativeBadge: 'bg-yellow-500' };
            
        case '🟢 LOW RISK':
        case 'MONITOR (GREEN)':
        case 'MONITOR':
            return { color: 'bg-green-600 text-white border-green-700', icon: '🟢', badge: 'bg-green-100 text-green-800', narrativeBadge: 'bg-green-600' };

        // --- 3-Tier Individual Indicator Statuses (ALIGNED WITH PYTHON OUTPUT) ---
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
    // NOTE: overall.status contains the emoji (e.g., "🟢 LOW RISK")
    const details = getStatusDetails(overall.status); 

    // Apply main color and structural classes to the card container
    if (card) {
        card.className = `p-6 mb-8 rounded-xl shadow-2xl border-4 transform transition duration-500 hover:scale-[1.01] hover:shadow-2xl ${details.color}`;
        
        // Remove emoji from status for display if present (e.g. show "LOW RISK" instead of "🟢 LOW RISK")
        const cleanStatus = overall.status.replace(/(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])/g, '').trim();

        card.innerHTML = `
            <div class="flex justify-between items-center mb-2">
                <h2 class="text-base font-semibold uppercase">
                    ${details.icon} ${cleanStatus}
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
        // Use the first paragraph of the AI narrative for the summary text
        const summaryText = overall.daily_narrative ? overall.daily_narrative.split('\n\n')[0] : overall.composite_summary;
        narrativeSummary.textContent = summaryText;
    }
    
    // Update the other side-bar elements
    document.getElementById('triggerSummary').textContent = overall.status; // Shows full status with emoji
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
        const indicatorValue = indicator.value === 0.0 || indicator.value === null ? 'N/A' : indicator.value; 
        
        // Format the value display based on type (for arrays like SNAP_BENEFITS)
        let displayValue;
        if (Array.isArray(indicatorValue) && indicatorValue.length === 2) {
            // Display MoM % change for SNAP
            const prev = indicatorValue[0];
            const curr = indicatorValue[1];
            if (prev > 0) {
                 const momChange = ((curr / prev) - 1) * 100;
                 displayValue = `${momChange.toFixed(1)}% MoM`;
            } else {
                 displayValue = `${curr} (N/A MoM)`;
            }
        } else if (typeof indicatorValue === 'number') {
             // Handle numeric values for display, forcing at least one decimal
             if (indicator.id === 'SPX_INDEX' || indicator.id === 'ASX_200') {
                 displayValue = indicatorValue.toLocaleString(undefined, { maximumFractionDigits: 0 });
             } else if (indicator.id === 'FISCAL_RISK') {
                 displayValue = indicatorValue.toFixed(0);
             } else {
                 displayValue = indicatorValue.toFixed(2);
             }
        } else {
            displayValue = indicatorValue || 'N/A';
        }
        
        // --- START OF HIGH VISIBILITY FIX LOGIC ---
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
                ${displayValue} 
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


// ------------------------------------------------------------------
// OLD UTILITY FUNCTION: renderCommentaryList IS REMOVED as the Python output changed.
// We will use direct DOM manipulation in initializeDashboard.
// ------------------------------------------------------------------


// --- 4. NARRATIVE PAGE RENDERING ---

/**
 * Renders the full narrative content and the news feed on the narrative.html page.
 */
function initializeNarrativePage() {
    fetchAtlasData().then(data => {
        if (!data) return;

        const overall = data.overall;
        // NOTE: overall.status contains the emoji (e.g., "🟢 LOW RISK")
        const details = getStatusDetails(overall.status); 

        // Set title, date, and status badge
        const cleanStatus = overall.status.replace(/(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])/g, '').trim();
        document.getElementById('narrativeTitle').textContent = `${cleanStatus} Risk Posture Analysis`;
        document.getElementById('narrativeDate').textContent = `Updated: ${overall.date}`;
        
        const statusBadge = document.getElementById('narrativeStatusBadge');
        statusBadge.textContent = `${overall.status} (Score: ${overall.score.toFixed(1)} / ${overall.max_score.toFixed(1)})`;
        statusBadge.className = `mt-4 inline-block px-3 py-1 text-sm font-bold rounded-full text-white ${details.narrativeBadge}`;

        // Insert the full narrative text.
        const narrativeContent = document.getElementById('fullNarrativeContent');
        if (narrativeContent) {
            // Using a simple split/join to wrap paragraphs in <p> tags for better formatting
            const paragraphs = overall.daily_narrative ? overall.daily_narrative.split('\n\n') : ["No detailed narrative provided for this update."];
            narrativeContent.innerHTML = paragraphs.map(p => `<p class="mb-4">${p.trim()}</p>`).join('');
        }
        
        // --- NEW: RENDER NEWS ARTICLES (News Integration Feature) ---
        const newsListContainer = document.getElementById('newsArticleList');
        // Ensure you check for data.overall.news_articles
        const articles = overall.news_articles || []; 
        
        if (newsListContainer) {
            if (articles.length === 0) {
                newsListContainer.innerHTML = '<p class="text-gray-500">No highly relevant news articles found for today\'s risk analysis.</p>';
            } else {
                newsListContainer.innerHTML = articles.map(article => `
                    <div class="border-b border-gray-100 pb-3 flex space-x-4">
                        
                        ${article.thumbnail_url ? `
                            <div class="flex-shrink-0">
                                <img src="${article.thumbnail_url}" alt="${article.title}" 
                                     class="h-16 w-16 object-cover rounded-md" />
                            </div>
                        ` : ''}

                        <div>
                            <a href="${article.link}" target="_blank" rel="noopener noreferrer" 
                               class="text-indigo-600 hover:text-indigo-800 font-semibold text-base block">
                                ${article.title}
                            </a>
                            <p class="text-sm text-gray-600 mt-1">${article.snippet}</p>
                        </div>
                    </div>
                `).join('');
            }
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
        // NOTE: post.status contains the emoji (e.g., "🟢 LOW RISK")
        const details = getStatusDetails(post.status);
        const postElement = document.createElement('article');
        
        // Use a simple date format for the archive
        // Check if date contains a space (time), if so, split it.
        const datePart = post.date ? post.date.split(' ')[0] : 'N/A';
        const displayDate = new Date(datePart).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
        
        // Remove emoji from status for the title display
        const cleanStatus = post.status.replace(/(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])/g, '').trim();


        postElement.className = 'border-b border-gray-200 pb-10';
        
        // Replace newline characters with <br> for HTML rendering, wrapping paragraphs in <p> tags
        const narrativeHTML = (post.daily_narrative || "No detailed narrative provided.")
            .split('\n\n')
            .map(p => `<p class="mb-3">${p.trim()}</p>`)
            .join('');

        postElement.innerHTML = `
            <div class="flex items-start justify-between mb-4">
                <h2 class="text-2xl font-bold text-gray-900">${details.icon} Atlas Update: ${displayDate} (${cleanStatus})</h2>
                <span class="mt-1 inline-block px-3 py-1 text-xs font-bold rounded-full text-white ${details.narrativeBadge}">
                    Score: ${post.score.toFixed(1)}
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

    // 3. Render Dashboard Commentary from OVERALL (Refactored due to Python changes)

    const overall = data.overall || {};
    
    // --- 3a. INSIGHT (Use the main overall comment) ---
    const insightList = document.getElementById('insightList');
    if (insightList) {
        insightList.innerHTML = `
            <li class="text-base font-bold italic">
                <span class="mr-1">💡</span> ${overall.comment}
            </li>
        `;
    }
    
    // --- 3b. IMMEDIATE ACTIONS (Use the composite summary) ---
    const actionList = document.getElementById('actionList');
    if (actionList) {
        actionList.innerHTML = `
            <li>
                <span class="mr-1">⚠️</span> ${overall.composite_summary}
            </li>
        `;
    }
    
    // --- 3c. ESCALATION WATCH (System-Calculated Triggers) ---
    const watchList = document.getElementById('watchList');
    if (!watchList) return; 
    watchList.innerHTML = ''; 

    const systemTriggers = overall.escalation_triggers || [];

    if (systemTriggers.length > 0) {
        // Add the system triggers to the list element
        systemTriggers.forEach(trigger => {
            const listItem = document.createElement('li');
            
            listItem.innerHTML = `
                <span class="font-bold text-red-700">🚨 Breach:</span>
                <span class="font-semibold">${trigger.name}</span> 
                (Current: <span class="text-indigo-600">${trigger.current_reading}</span>)
                — Alarm: <span class="text-red-600">${trigger.alarm_threshold}</span>
            `;
            
            watchList.appendChild(listItem);
        });
    } else {
        watchList.innerHTML = '<li class="text-green-600">No immediate escalation risks flagged.</li>';
    }

    console.log("Atlas Dashboard successfully rendered data.");
}