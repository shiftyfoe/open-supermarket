/**
 * Open Supermarket Singapore - Dashboard
 */

const DATA_URL = 'data/latest.json';
const HISTORY_URL = 'data/price_history.json';

let allProducts = [];
let priceHistory = {};

/**
 * Load data from JSON files
 */
async function loadData() {
    try {
        const [productsResp, historyResp] = await Promise.all([
            fetch(DATA_URL),
            fetch(HISTORY_URL)
        ]);

        if (productsResp.ok) {
            allProducts = await productsResp.json();
        }

        if (historyResp.ok) {
            priceHistory = await historyResp.json();
        }
    } catch (err) {
        console.error('Error loading data:', err);
    }
}

/**
 * Update summary statistics
 */
function updateStats() {
    document.getElementById('total-products').textContent = allProducts.length;

    const supermarkets = [...new Set(allProducts.map(p => p.supermarket))];
    document.getElementById('supermarkets').textContent = supermarkets.length;

    // Count price drops (compare with previous day)
    let drops = 0;
    const today = new Date().toISOString().split('T')[0];
    for (const product of allProducts) {
        const hist = priceHistory[product.id];
        if (hist && hist.prices) {
            const dates = Object.keys(hist.prices).sort();
            if (dates.length >= 2) {
                const prev = hist.prices[dates[dates.length - 2]];
                const curr = hist.prices[dates[dates.length - 1]];
                if (curr < prev) drops++;
            }
        }
    }
    document.getElementById('price-drops').textContent = drops;
    document.getElementById('last-updated').textContent = new Date().toLocaleDateString('en-SG');
}

/**
 * Create comparison chart
 */
function createComparisonChart() {
    const ctx = document.getElementById('comparisonChart').getContext('2d');

    // Group by category and supermarket
    const categories = [...new Set(allProducts.map(p => p.category))];
    const supermarkets = [...new Set(allProducts.map(p => p.supermarket))];

    // Calculate average price per category per supermarket
    const data = {};
    for (const store of supermarkets) {
        data[store] = categories.map(cat => {
            const products = allProducts.filter(p => p.supermarket === store && p.category === cat);
            if (products.length === 0) return 0;
            return products.reduce((sum, p) => sum + p.price, 0) / products.length;
        });
    }

    const colors = {
        fairprice: '#2563eb',
        shengsiong: '#22c55e',
        coldstorage: '#f59e0b',
    };

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: categories,
            datasets: supermarkets.map(store => ({
                label: store.charAt(0).toUpperCase() + store.slice(1),
                data: data[store],
                backgroundColor: colors[store] || '#94a3b8',
            })),
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                title: { display: true, text: 'Average Price by Category' },
            },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Price (SGD)' } },
            },
        },
    });
}

/**
 * Create trends chart
 */
function createTrendsChart() {
    const ctx = document.getElementById('trendsChart').getContext('2d');

    // Get all unique dates
    const allDates = new Set();
    for (const hist of Object.values(priceHistory)) {
        Object.keys(hist.prices).forEach(d => allDates.add(d));
    }
    const dates = [...allDates].sort();

    // Sample some products for the chart
    const sampleProducts = Object.entries(priceHistory)
        .slice(0, 5)
        .map(([id, hist]) => ({
            label: hist.name,
            data: dates.map(d => hist.prices[d] || null),
            borderColor: `hsl(${Math.random() * 360}, 70%, 50%)`,
            fill: false,
        }));

    new Chart(ctx, {
        type: 'line',
        data: { labels: dates, datasets: sampleProducts },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                title: { display: true, text: 'Price Trends Over Time' },
            },
            scales: {
                y: { title: { display: true, text: 'Price (SGD)' } },
            },
        },
    });
}

/**
 * Render product list
 */
function renderProducts(products) {
    const container = document.getElementById('product-list');
    container.innerHTML = products.map(p => `
        <div class="product-card">
            <div class="product-header">
                <div class="product-name">${p.name}</div>
                <span class="product-supermarket">${p.supermarket}</span>
            </div>
            <div>
                <span class="product-price">$${p.price.toFixed(2)}</span>
                ${p.original_price > p.price ? `<span class="product-original">$${p.original_price.toFixed(2)}</span>` : ''}
            </div>
            <div class="product-meta">
                <span>${p.brand || ''}</span>
                <span>${p.size || p.unit || ''}</span>
            </div>
        </div>
    `).join('');
}

/**
 * Set up filters
 */
function setupFilters() {
    const supermarketFilter = document.getElementById('supermarket-filter');
    const categoryFilter = document.getElementById('category-filter');
    const searchInput = document.getElementById('search');

    // Populate filters
    const supermarkets = [...new Set(allProducts.map(p => p.supermarket))];
    const categories = [...new Set(allProducts.map(p => p.category))];

    supermarkets.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s.charAt(0).toUpperCase() + s.slice(1);
        supermarketFilter.appendChild(opt);
    });

    categories.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        categoryFilter.appendChild(opt);
    });

    // Filter logic
    const applyFilters = () => {
        let filtered = [...allProducts];

        const store = supermarketFilter.value;
        if (store !== 'all') {
            filtered = filtered.filter(p => p.supermarket === store);
        }

        const cat = categoryFilter.value;
        if (cat !== 'all') {
            filtered = filtered.filter(p => p.category === cat);
        }

        const search = searchInput.value.toLowerCase();
        if (search) {
            filtered = filtered.filter(p =>
                p.name.toLowerCase().includes(search) ||
                (p.brand && p.brand.toLowerCase().includes(search))
            );
        }

        renderProducts(filtered);
    };

    supermarketFilter.addEventListener('change', applyFilters);
    categoryFilter.addEventListener('change', applyFilters);
    searchInput.addEventListener('input', applyFilters);
}

/**
 * Initialize the dashboard
 */
async function init() {
    await loadData();

    if (allProducts.length > 0) {
        updateStats();
        createComparisonChart();
        createTrendsChart();
        renderProducts(allProducts);
        setupFilters();
    } else {
        document.getElementById('product-list').innerHTML = '<p>No data available. Scrapers run daily at 10 AM SGT.</p>';
    }
}

init();
