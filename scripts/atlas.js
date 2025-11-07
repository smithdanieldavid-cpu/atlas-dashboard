// scripts/atlas.js

// --- 1. STATUS AND COLOR MAPPING UTILITY ---
const getStatusDetails = (status) => {
    // Expecting standardized input from Python (e.g. " FULL-STORM (EXTREME RISK)")
    if (!status) {
        return {
            color: 'bg-gray-400 text-white border-gray-500',
            icon: '',
            badge: 'bg-gray-100 text-gray-800',
            narrativeBadge: 'bg-gray-400'
        };
    }

    switch (status.trim()) {
        // --- 4-Tier Overall Composite Risk Statuses (OFFICIAL, NO FALLBACKS) ---
        case ' FULL-STORM (EXTREME RISK)':
            return {
                color: 'bg-red-800 text-white border-red-900',
                icon: '',
                badge: 'bg-red-100 text-red-800',
                narrativeBadge: 'bg-red-800'
            };
        case ' SEVERE RISK (HIGH RISK)':
            return {
                color: 'bg-orange-600 text-white border-orange-700',
                icon: '',
                badge: 'bg-orange-100 text-orange-800',
                narrativeBadge: 'bg-orange-600'
            };
        case ' ELEVATED RISK (MODERATE RISK)':
            return {
                color: 'bg-amber-500 text-black border-amber-600',
                icon: '',
                badge: 'bg-amber-100 text-amber-800',
                narrativeBadge: 'bg-amber-500'
            };
        case ' MONITOR (LOW RISK)':
            return {
                color: 'bg-green-600 text-white border-green-700',
                icon: '',
                badge: 'bg-green-100 text-green-800',
                narrativeBadge: 'bg-green-600'
            };

        // --- 3-Tier Individual Indicator Statuses (FIXED TO USE CSS CLASS NAMES) ---
        case 'RED':
            return {
                color: 'text-red-700',
                icon: 'red',
                badge: 'bg-red-100 text-red-800',
                narrativeBadge: 'bg-red-600'
            };
        case 'AMBER':
            return {
                color: 'text-amber-700',
                icon: 'amber',
                badge: 'bg-amber-100 text-amber-800',
                narrativeBadge: 'bg-amber-500'
            };
        case 'GREEN':
            return {
                color: 'text-green-700',
                icon: 'green',
                badge: 'bg-green-100 text-green-800',
                narrativeBadge: 'bg-green-600'
            };
        // --- Default / Unknown ---
        default:
            return {
                color: 'bg-gray-400 text-white border-gray-500',
                icon: '',
                badge: 'bg-gray-100 text-gray-800',
                narrativeBadge: 'bg-gray-400'
            };
    }
};

// --- 2. DATA FETCHING ---

const ATLAS_DATA_PATH = 'data/atlas-latest.json';
const ARCHIVE_DATA_PATH = 'data/atlas-archive.json';
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
 * Updates the overall status card and the narrative summary.
 * @param {object} overall - The overall status object from the JSON.
 */
function renderOverallStatus(overall) {
    const card = document.getElementById('overallStatusCard');
    const details = getStatusDetails(overall.status);

    if (card) {
        card.className = `p-6 mb-8 rounded-xl shadow-2xl border-4 transform transition duration-500 hover:scale-[1.01] hover:shadow-2xl ${details.color}`;
        const cleanStatus = overall.status.replace(/(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])/g, '').trim();
        const displayScore = (overall.score ?? 0).toFixed(1);
        const displayMaxScore = (overall.max_score ?? 25.0).toFixed(1);
        card.innerHTML = `
            <div class="flex justify-between items-center mb-2">
                <h2 class="text-base font-semibold uppercase">
                    ${details.icon} ${cleanStatus}
                </h2>
                <span class="text-2xl font-mono font-bold">
                    ${displayScore} <span class="text-sm font-normal opacity-70">/${displayMaxScore}</span>
                </span>
            </div>
            <p class="text-xs font-medium opacity-90">${overall.comment}</p>
            <p class="mt-4 text-xs font-light italic">${overall.composite_summary}</p>
        `;
    }

    const narrativeSummary = document.getElementById('narrativeSummaryText');
    if (narrativeSummary) {
        const summaryText = overall.daily_narrative ?
            overall.daily_narrative.split('\n\n')[0] : overall.composite_summary;
        narrativeSummary.textContent = summaryText;
    }

    document.getElementById('triggerSummary').textContent = overall.status;
    document.getElementById('triggerDetails').textContent = overall.comment;
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
    tableBody.innerHTML = '';

    indicators.forEach(indicator => {
        const details = getStatusDetails(indicator.status);

        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50';

        const indicatorValue = indicator.value === 0.0 || indicator.value === null ? 'N/A' : indicator.value;

        let displayValue;
        if (Array.isArray(indicatorValue) && indicatorValue.length === 2) {
            const prev = indicatorValue[0];
            const curr = indicatorValue[1];
            if (prev > 0) {
                 const momChange = ((curr / prev) - 1) * 100;
                 displayValue = `${momChange.toFixed(1)}% MoM`;
            } else {
                 displayValue = `${curr} (N/A MoM)`;
            }
        } else if (typeof indicatorValue === 'number') {
             if (indicator.id === 'SPX_INDEX' ||
                 indicator.id === 'ASX_200') {
                 displayValue = indicatorValue.toLocaleString(undefined, { maximumFractionDigits: 0 });
            } else if (indicator.id === 'FISCAL_RISK') {
                 displayValue = indicatorValue.toFixed(0);
            } else {
                 displayValue = indicatorValue.toFixed(2);
            }
        } else {
            displayValue = indicatorValue || 'N/A';
        }

        const currentStatus = (indicator.status || '').toUpperCase();
        let displayNote;
        let sourceLink = '';

        if (currentStatus === 'N/A' || currentStatus === 'ERROR') {
            displayNote = `
                <span class="font-bold text-red-600"> DATA ${currentStatus}:</span>
                <span class="text-base font-bold">${indicator.note}</span>
                <span class="text-sm text-gray-500">(Action: ${indicator.action})</span>
            `;
        } else {
            const sourceURL = indicator.source_link || indicator.source || indicator.url;

            sourceLink = sourceURL && sourceURL.startsWith('http')
                               ? `<a href="${sourceURL}" target="_blank" rel="noopener noreferrer" class="text-indigo-600 hover:text-indigo-800">[Source]</a>`
                               : '';
            displayNote = `
                <span class="font-semibold">${indicator.note}</span>.
                Action: ${indicator.action}
                ${sourceLink}
            `;
        }

        // --- START OF ICON RENDERING FIX ---
        let iconHtml;
        const iconValue = details.icon;

        if (iconValue === 'red' || iconValue === 'amber' || iconValue === 'green') {
            iconHtml = `<span class="status-dot ${iconValue}"></span>`;
        } else {
            iconHtml = `<span class="mr-2">${iconValue}</span>`;
        }
        // --- END OF ICON RENDERING FIX ---


        row.innerHTML = `
            <td class="w-1/4 px-3 py-3 text-sm font-medium text-gray-900">
                ${iconHtml}${indicator.name}
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

// --- NEW: NEWS RENDERING UTILITY ---

/**
 * Renders the structured list of news articles from the new JSON field 'news'.
 * @param {Array<Object>} newsArticles - The structured news array from the JSON.
 */
function renderNewsFeed(newsArticles) {
    const newsListContainer = document.getElementById('newsArticleList');

    if (!newsListContainer) return;
    if (!Array.isArray(newsArticles) || newsArticles.length === 0) {
        newsListContainer.innerHTML = '<p class="text-gray-500">No contextual news articles were retrieved for this analysis.</p>';
        return;
    }

    newsListContainer.innerHTML = newsArticles.map((article) => {
        const url = article.url || '#';
        const hostname = url.startsWith('http') ? new URL(url).hostname : 'Unknown Source';

        return `
            <div class="border-b border-gray-100 pb-4 last:border-b-0">
                <h3 class="text-base font-semibold text-gray-900">
                    <a href="${url}" target="_blank" rel="noopener noreferrer" class="hover:text-indigo-600 transition duration-150">
                        ${article.title || 'Untitled Article'}
                    </a>
                </h3>
                <p class="text-sm text-gray-600 mt-1">${article.snippet || 'Snippet unavailable.'}</p>
                <a href="${url}" target="_blank" rel="noopener noreferrer"
                   class="text-xs text-indigo-500 hover:text-indigo-700 font-medium mt-1 block">
                    Source: ${hostname}
                </a>
            </div>
        `;
    }).join('');
}


// --- 4. NARRATIVE PAGE RENDERING (UPDATED) ---

/**
 * Renders the full narrative content and the news feed on the narrative.html page.
 */
function initializeNarrativePage() {
    fetchAtlasData().then(data => {
        if (!data) return;

        const overall = data.overall;
        const details = getStatusDetails(overall.status);

        // 1. Update Title, Date, and Status Badge
        const cleanStatus = overall.status.replace(/(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])/g, '').trim();
        document.getElementById('narrativeTitle').textContent = `${cleanStatus} Risk Posture Analysis`;
        document.getElementById('narrativeDate').textContent = `Updated: ${overall.date}`;

        const displayScore = (overall.score ?? 0).toFixed(1);
        const displayMaxScore = (overall.max_score ?? 25.0).toFixed(1);

        const statusBadge = document.getElementById('narrativeStatusBadge');
        statusBadge.textContent = `${cleanStatus} (Score: ${displayScore} / ${displayMaxScore})`;
        statusBadge.className = `mt-4 inline-block px-3 py-1 text-sm font-bold rounded-full text-white ${details.narrativeBadge}`;

        // 2. Render Main Narrative (daily_narrative)
        const narrativeContainer = document.getElementById('dailyNarrativeContainer');
        const dailyNarrative = overall.daily_narrative || "Narrative is currently unavailable.";

        if (narrativeContainer) {
             const narrativeParagraphs = dailyNarrative.split('\n').filter(p => p.trim() !== '').map(p => `<p class="mb-4">${p.trim()}</p>`).join('');
            narrativeContainer.innerHTML = narrativeParagraphs || `<p>Analysis failed to load.</p>`;
        }

        // 3. Render Key Actions (key_actions)
        const actionsList = document.getElementById('keyActionsList');
        const keyActions = overall.key_actions;

        let actionsHtml = '';
        if (actionsList) {
            if (Array.isArray(keyActions) && keyActions.length > 0) {
                actionsHtml = keyActions.map(action => {
                    const cleanAction = action.replace(/^[\s*-]+/, '').trim();
                    return cleanAction ? `<li>${cleanAction}</li>` : '';
                }).join('');
            }

            actionsList.innerHTML = actionsHtml ||
                '<li class="text-gray-500">No specific actionable recommendations were provided.</li>';
        }

        // 4. Render News Feed (using the new 'news' array)
        renderNewsFeed(overall.news);
    });
}

// --- 5. ARCHIVE PAGE RENDERING (INFINITE SCROLL LOGIC) ---

/**
 * Renders a batch of historical posts and advances the index.
 * @param {number} startIndex - The starting index in allArchivePosts.
 */
function renderArchivePosts(startIndex) {
    const container = document.getElementById('archiveContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const endOfArchive = document.getElementById('endOfArchive');

    const postsToRender = allArchivePosts.slice(startIndex, startIndex + POSTS_PER_LOAD);

    if (loadingIndicator) loadingIndicator.style.display = 'none';
    if (postsToRender.length === 0 && startIndex > 0) {
        if (endOfArchive) endOfArchive.classList.remove('hidden');
        return;
    } else if (postsToRender.length === 0 && startIndex === 0) {
         if (container) container.innerHTML = "<p class='text-gray-500'>No historical narratives found in the archive.</p>";
        return;
    }


    postsToRender.forEach(post => {
        const details = getStatusDetails(post.status);
        const postElement = document.createElement('article');

        const datePart = post.date ? post.date.split(' ')[0] : 'N/A';
        const displayDate = new Date(datePart).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

        const cleanStatus = post.status.replace(/(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])/g, '').trim();

        const displayScore = (post.score ?? 0).toFixed(1);

        postElement.className = 'border-b border-gray-200 pb-10';

        const narrativeHTML = (post.daily_narrative || "No detailed narrative provided.")
            .split('\n\n')
            .map(p => `<p class="mb-3">${p.trim()}</p>`)
            .join('');
        postElement.innerHTML = `
            <div class="flex items-start justify-between mb-4">
                <h2 class="text-2xl font-bold text-gray-900">${details.icon} Atlas Update: ${displayDate} (${cleanStatus})</h2>
                <span class="mt-1 inline-block px-3 py-1 text-xs font-bold rounded-full text-white ${details.narrativeBadge}">
                    Score: ${displayScore}
                </span>
            </div>
            <p class="text-base text-gray-700 leading-relaxed">${narrativeHTML}</p>
        `;
        container.appendChild(postElement);
    });

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

    allArchivePosts = await response.json();
    currentPostIndex = 0;

    renderArchivePosts(currentPostIndex);

    const scrollHandler = () => {
        if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 1000) {

            window.removeEventListener('scroll', scrollHandler);
            if (currentPostIndex < allArchivePosts.length) {
                const loadingIndicator = document.getElementById('loadingIndicator');
                if (loadingIndicator) loadingIndicator.style.display = 'block';

                setTimeout(() => {
                    renderArchivePosts(currentPostIndex);
                    if (currentPostIndex < allArchivePosts.length) {
                        window.addEventListener('scroll', scrollHandler);
                    }
                }, 500);
            }
        }
    };
    window.addEventListener('scroll', scrollHandler);
}


// --- 6. MAIN INITIALIZATION LOGIC ---

// Determine which initialization function to run based on the current page
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    if (path.includes('narrative.html')) {
        initializeNarrativePage();
    } else if (path.includes('archive.html')) {
        initializeArchivePage();
    } else {
        initializeDashboard();
    }
});

async function initializeDashboard() {
    const data = await fetchAtlasData();
    if (!data) return;

    renderOverallStatus(data.overall);
    renderIndicatorTable('macroTable', data.macro);
    renderIndicatorTable('microTable', data.micro);

    const overall = data.overall || {};

    // --- INSIGHT (Use the main overall comment) ---
    const insightList = document.getElementById('insightList');
    if (insightList) {
        insightList.innerHTML = `
            <li class="text-base font-bold italic">
                <span class="mr-1"></span> ${overall.comment}
            </li>
        `;
    }

    // --- IMMEDIATE ACTIONS (Use the composite summary) ---
    const actionList = document.getElementById('actionList');
    if (actionList) {
        actionList.innerHTML = `
            <li>
                <span class="mr-1"></span> ${overall.composite_summary}
            </li>
        `;
    }

    // --- ESCALATION WATCH (System-Calculated Triggers) ---
    const watchList = document.getElementById('watchList');
    if (!watchList) return;
    watchList.innerHTML = '<li class="text-green-600">No immediate escalation risks flagged.</li>';

    console.log("Atlas Dashboard successfully rendered data.");
}