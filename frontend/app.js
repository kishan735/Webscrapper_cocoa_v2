// API Configuration - UPDATE THIS WITH YOUR RAILWAY URL
const API_BASE_URL = 'https://web-production-c9ed9.up.railway.app';

// DOM Elements
const elements = {
    currentPrice: document.getElementById('currentPrice'),
    priceChange: document.getElementById('priceChange'),
    openPrice: document.getElementById('openPrice'),
    dayHigh: document.getElementById('dayHigh'),
    dayLow: document.getElementById('dayLow'),
    prevClose: document.getElementById('prevClose'),
    week52High: document.getElementById('week52High'),
    week52Low: document.getElementById('week52Low'),
    pricePosition: document.getElementById('pricePosition'),
    ma50: document.getElementById('ma50'),
    ma200: document.getElementById('ma200'),
    change1w: document.getElementById('change1w'),
    change1m: document.getElementById('change1m'),
    change3m: document.getElementById('change3m'),
    change6m: document.getElementById('change6m'),
    change1y: document.getElementById('change1y'),
    marketOverview: document.getElementById('marketOverview'),
    marketOutlook: document.getElementById('marketOutlook'),
    keyFactorsSection: document.getElementById('keyFactorsSection'),
    keyFactors: document.getElementById('keyFactors'),
    newsList: document.getElementById('newsList'),
    newsCount: document.getElementById('newsCount'),
    lastUpdated: document.getElementById('lastUpdated'),
    refreshIcon: document.getElementById('refreshIcon'),
};

// Utility Functions
function formatPrice(price) {
    return price ? `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--';
}

function formatChange(change) {
    if (change === null || change === undefined) return '--';
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}%`;
}

function getChangeColor(change) {
    if (change === null || change === undefined) return 'text-gray-500';
    return change >= 0 ? 'text-green-600' : 'text-red-600';
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

// API Functions
async function fetchData(endpoint) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${endpoint}:`, error);
        return null;
    }
}

// Update Functions
function updatePrice(data) {
    if (!data) return;

    elements.currentPrice.textContent = formatPrice(data.current_price).replace('$', '');
    elements.currentPrice.classList.remove('loading-pulse');

    const changeHtml = `
        <span class="text-2xl font-semibold ${getChangeColor(data.change_percent)}">
            ${formatChange(data.change_percent)}
        </span>
        <p class="text-sm ${getChangeColor(data.change_amount)}">
            ${data.change_amount >= 0 ? '+' : ''}${data.change_amount?.toFixed(2) || '--'}
        </p>
    `;
    elements.priceChange.innerHTML = changeHtml;

    elements.openPrice.textContent = formatPrice(data.open_price);
    elements.dayHigh.textContent = formatPrice(data.day_high);
    elements.dayLow.textContent = formatPrice(data.day_low);
    elements.prevClose.textContent = formatPrice(data.previous_close);
}

function updateTechnical(data) {
    if (!data) return;

    elements.week52High.textContent = formatPrice(data.week_52_high);
    elements.week52Low.textContent = formatPrice(data.week_52_low);
    elements.ma50.textContent = data.moving_avg_50 ? formatPrice(data.moving_avg_50) : 'N/A';
    elements.ma200.textContent = data.moving_avg_200 ? formatPrice(data.moving_avg_200) : 'N/A';

    // Update price position indicator
    if (data.price_vs_52_high_percent) {
        const position = data.price_vs_52_high_percent;
        elements.pricePosition.style.left = `${position}%`;
    }
}

function updateComparison(data) {
    if (!data) return;

    const updateChangeEl = (el, change) => {
        el.textContent = formatChange(change);
        el.className = `text-lg font-semibold ${getChangeColor(change)}`;
    };

    updateChangeEl(elements.change1w, data.change_1_week);
    updateChangeEl(elements.change1m, data.change_1_month);
    updateChangeEl(elements.change3m, data.change_3_months);
    updateChangeEl(elements.change6m, data.change_6_months);
    updateChangeEl(elements.change1y, data.change_1_year);
}

function updateMarketOverview(data) {
    if (!data) {
        elements.marketOverview.innerHTML = '<p class="text-gray-500">Unable to load market overview</p>';
        return;
    }

    let html = `<p class="text-gray-700 leading-relaxed">${data.summary}</p>`;

    if (data.key_factors && data.key_factors.length > 0) {
        elements.keyFactorsSection.classList.remove('hidden');
        elements.keyFactors.innerHTML = data.key_factors.map(factor =>
            `<span class="px-3 py-1 bg-cocoa-100 text-cocoa-800 rounded-full text-sm">${factor}</span>`
        ).join('');
    }

    if (data.supply_conditions) {
        html += `
            <div class="mt-4 p-3 bg-blue-50 rounded-lg">
                <p class="text-sm font-medium text-blue-800">Supply</p>
                <p class="text-sm text-blue-700">${data.supply_conditions}</p>
            </div>
        `;
    }

    if (data.demand_conditions) {
        html += `
            <div class="mt-2 p-3 bg-purple-50 rounded-lg">
                <p class="text-sm font-medium text-purple-800">Demand</p>
                <p class="text-sm text-purple-700">${data.demand_conditions}</p>
            </div>
        `;
    }

    elements.marketOverview.innerHTML = html;
    elements.marketOverview.classList.add('fade-in');
}

function updateMarketOutlook(data) {
    if (!data) {
        elements.marketOutlook.innerHTML = '<p class="text-gray-500">Unable to load market outlook</p>';
        return;
    }

    let html = `
        <div class="space-y-3">
            <div>
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">Short Term (1-4 weeks)</p>
                <p class="text-gray-700">${data.short_term_outlook}</p>
            </div>
            <div>
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">Medium Term (1-3 months)</p>
                <p class="text-gray-700">${data.medium_term_outlook}</p>
            </div>
    `;

    if (data.trends_to_watch && data.trends_to_watch.length > 0) {
        html += `
            <div class="pt-3 border-t border-gray-100">
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Trends to Watch</p>
                <ul class="space-y-1">
                    ${data.trends_to_watch.map(trend =>
                        `<li class="text-sm text-gray-600 flex items-start">
                            <span class="text-cocoa-500 mr-2">•</span>${trend}
                        </li>`
                    ).join('')}
                </ul>
            </div>
        `;
    }

    html += '</div>';
    elements.marketOutlook.innerHTML = html;
    elements.marketOutlook.classList.add('fade-in');
}

function updateNews(articles) {
    if (!articles || articles.length === 0) {
        elements.newsList.innerHTML = '<p class="text-gray-500">No news available</p>';
        return;
    }

    elements.newsCount.textContent = `${articles.length} articles`;

    const html = articles.slice(0, 10).map(article => {
        const sentimentBadge = article.sentiment ?
            `<span class="px-2 py-0.5 text-xs rounded ${
                article.sentiment === 'positive' ? 'bg-green-100 text-green-700' :
                article.sentiment === 'negative' ? 'bg-red-100 text-red-700' :
                'bg-gray-100 text-gray-700'
            }">${article.sentiment}</span>` : '';

        const importanceBar = article.importance_score ?
            `<div class="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div class="h-full bg-cocoa-500 rounded-full" style="width: ${article.importance_score * 100}%"></div>
            </div>` : '';

        return `
            <a href="${article.url}" target="_blank" rel="noopener noreferrer"
               class="block border-b border-gray-100 pb-4 hover:bg-gray-50 -mx-2 px-2 py-2 rounded-lg transition-colors">
                <div class="flex items-start justify-between gap-4">
                    <div class="flex-1 min-w-0">
                        <h3 class="text-sm font-medium text-gray-900 line-clamp-2 hover:text-cocoa-700">
                            ${article.title}
                        </h3>
                        ${article.summary ? `<p class="text-xs text-gray-500 mt-1 line-clamp-2">${article.summary}</p>` : ''}
                        <div class="flex items-center gap-3 mt-2">
                            <span class="text-xs text-gray-400">${article.source}</span>
                            <span class="text-xs text-gray-400">${timeAgo(article.published_date)}</span>
                            ${sentimentBadge}
                        </div>
                    </div>
                    <div class="flex flex-col items-end gap-1">
                        ${importanceBar}
                    </div>
                </div>
            </a>
        `;
    }).join('');

    elements.newsList.innerHTML = html;
    elements.newsList.classList.add('fade-in');
}

// Main refresh function
async function refreshData() {
    // Add spinning animation to refresh icon
    elements.refreshIcon.classList.add('animate-spin');

    // Fetch all data in parallel
    const [price, technical, comparison, overview, outlook, news] = await Promise.all([
        fetchData('/api/v1/price'),
        fetchData('/api/v1/price/technical'),
        fetchData('/api/v1/price/comparison'),
        fetchData('/api/v1/market/overview'),
        fetchData('/api/v1/market/outlook'),
        fetchData('/api/v1/news?limit=10'),
    ]);

    // Update UI
    updatePrice(price);
    updateTechnical(technical);
    updateComparison(comparison);
    updateMarketOverview(overview);
    updateMarketOutlook(outlook);
    updateNews(news);

    // Update last updated time
    elements.lastUpdated.textContent = `Updated ${new Date().toLocaleTimeString()}`;

    // Remove spinning animation
    elements.refreshIcon.classList.remove('animate-spin');
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    refreshData();

    // Auto-refresh every 5 minutes
    setInterval(refreshData, 5 * 60 * 1000);
});
