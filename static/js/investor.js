// Logout function
async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        window.location.href = '/';
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = '/';
    }
}

// Investor Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    let companies = [];
    let selectedCompanies = [];
    
    // Load companies
    async function loadCompanies() {
        try {
            const response = await fetch('/api/companies');
            companies = await response.json();
            renderCompanies();
            populateForecastSelector();
        } catch (error) {
            console.error('Error loading companies:', error);
        }
    }
    
    function renderCompanies() {
        const grid = document.getElementById('companies-grid');
        const sectorFilter = document.getElementById('sector-filter').value;
        const sortBy = document.getElementById('sort-filter').value;
        
        let filtered = companies;
        
        if (sectorFilter) {
            filtered = filtered.filter(c => c.sector === sectorFilter);
        }
        
        filtered.sort((a, b) => b[sortBy] - a[sortBy]);
        
        grid.innerHTML = '';
        
        filtered.forEach(company => {
            const isSelected = selectedCompanies.find(c => c.id === company.id);
            const card = document.createElement('div');
            card.className = `company-card ${isSelected ? 'selected' : ''}`;
            card.innerHTML = `
                <div class="company-header">
                    <span class="company-name">${company.name}</span>
                    <span class="company-sector">${company.sector}</span>
                </div>
                <p class="company-description">${company.description}</p>
                <div class="company-metrics">
                    <div class="metric">
                        <span class="metric-value">${company.esg_score}</span>
                        <span class="metric-label">ESG Skor</span>
                    </div>
                    <div class="metric">
                        <span class="metric-value">${company.roi_potential}%</span>
                        <span class="metric-label">ROI</span>
                    </div>
                    <div class="metric">
                        <span class="metric-value">${company.growth_rate}%</span>
                        <span class="metric-label">Artım</span>
                    </div>
                </div>
            `;
            
            card.addEventListener('click', () => toggleCompanySelection(company));
            grid.appendChild(card);
        });
    }
    
    function toggleCompanySelection(company) {
        const index = selectedCompanies.findIndex(c => c.id === company.id);
        
        if (index > -1) {
            selectedCompanies.splice(index, 1);
        } else if (selectedCompanies.length < 3) {
            selectedCompanies.push(company);
        } else {
            alert('Maksimum 3 şirkət seçə bilərsiniz');
            return;
        }
        
        renderCompanies();
        renderSelectedCompanies();
    }
    
    function renderSelectedCompanies() {
        const container = document.getElementById('selected-companies');
        const compareBtn = document.getElementById('compare-btn');
        
        if (selectedCompanies.length === 0) {
            container.innerHTML = '<p class="empty-state">Müqayisə üçün şirkətləri seçin</p>';
            compareBtn.disabled = true;
        } else {
            container.innerHTML = selectedCompanies.map(company => `
                <div class="selected-company-tag">
                    <span>${company.name}</span>
                    <span class="remove-company" data-id="${company.id}">✕</span>
                </div>
            `).join('');
            compareBtn.disabled = selectedCompanies.length < 2;
            
            // Add remove handlers
            container.querySelectorAll('.remove-company').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const id = parseInt(btn.dataset.id);
                    selectedCompanies = selectedCompanies.filter(c => c.id !== id);
                    renderCompanies();
                    renderSelectedCompanies();
                });
            });
        }
    }
    
    function populateForecastSelector() {
        const selector = document.getElementById('forecast-company');
        selector.innerHTML = '<option value="">Şirkət seçin...</option>';
        
        companies.forEach(company => {
            const option = document.createElement('option');
            option.value = company.id;
            option.textContent = company.name;
            selector.appendChild(option);
        });
    }
    
    // Filter handlers
    document.getElementById('sector-filter').addEventListener('change', renderCompanies);
    document.getElementById('sort-filter').addEventListener('change', renderCompanies);
    
    // Compare button
    document.getElementById('compare-btn').addEventListener('click', async function() {
        const btn = this;
        btn.classList.add('loading');
        
        try {
            const response = await fetch('/api/compare-companies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    company_ids: selectedCompanies.map(c => c.id)
                })
            });
            
            const result = await response.json();
            
            if (result.error) {
                alert('Xəta baş verdi: ' + result.error);
                return;
            }
            
            displayCompareResult(result);
        } catch (error) {
            alert('Xəta baş verdi: ' + error.message);
        } finally {
            btn.classList.remove('loading');
        }
    });
    
    function displayCompareResult(result) {
        const resultCard = document.getElementById('compare-result');
        resultCard.classList.remove('hidden');
        
        const analysis = result.analysis || {};
        
        document.getElementById('compare-summary').innerHTML = `<p>${analysis.comparison_summary || '-'}</p>`;
        document.getElementById('best-esg').textContent = analysis.best_esg || '-';
        document.getElementById('best-investment').textContent = analysis.best_investment || '-';
        document.getElementById('recommendation').textContent = analysis.recommendation || '-';
        
        // Detailed analysis
        const detailedContainer = document.getElementById('detailed-analysis');
        detailedContainer.innerHTML = '';
        
        (analysis.detailed_analysis || []).forEach(item => {
            const div = document.createElement('div');
            div.className = 'analysis-item';
            div.innerHTML = `
                <h5>${item.company}</h5>
                <p><strong>Güclü tərəflər:</strong> ${(item.strengths || []).join(', ')}</p>
                <p><strong>Zəif tərəflər:</strong> ${(item.weaknesses || []).join(', ')}</p>
            `;
            detailedContainer.appendChild(div);
        });
        
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // Forecast handlers
    const forecastSelector = document.getElementById('forecast-company');
    const forecastBtn = document.getElementById('forecast-btn');
    
    forecastSelector.addEventListener('change', function() {
        forecastBtn.disabled = !this.value;
    });
    
    forecastBtn.addEventListener('click', async function() {
        const companyId = parseInt(forecastSelector.value);
        if (!companyId) return;
        
        this.classList.add('loading');
        
        try {
            const response = await fetch('/api/company-forecast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ company_id: companyId })
            });
            
            const result = await response.json();
            
            if (result.error) {
                alert('Xəta baş verdi: ' + result.error);
                return;
            }
            
            displayForecastResult(result);
        } catch (error) {
            alert('Xəta baş verdi: ' + error.message);
        } finally {
            this.classList.remove('loading');
        }
    });
    
    function displayForecastResult(result) {
        const resultCard = document.getElementById('forecast-result');
        resultCard.classList.remove('hidden');
        
        const company = result.company || {};
        const forecast = result.forecast || {};
        
        document.getElementById('forecast-company-name').textContent = company.name || '-';
        
        // Growth chart
        const growthChart = document.getElementById('growth-chart');
        const growth = forecast.growth_forecast || {};
        growthChart.innerHTML = `
            <div class="chart-bar">
                <div class="bar" style="height: ${Math.min(parseFloat(growth.year_1) || 0, 100) * 1.2}px"></div>
                <span class="bar-label">İl 1: ${growth.year_1 || '-'}</span>
            </div>
            <div class="chart-bar">
                <div class="bar" style="height: ${Math.min(parseFloat(growth.year_2) || 0, 100) * 1.2}px"></div>
                <span class="bar-label">İl 2: ${growth.year_2 || '-'}</span>
            </div>
            <div class="chart-bar">
                <div class="bar" style="height: ${Math.min(parseFloat(growth.year_3) || 0, 100) * 1.2}px"></div>
                <span class="bar-label">İl 3: ${growth.year_3 || '-'}</span>
            </div>
        `;
        
        // ESG chart
        const esgChart = document.getElementById('esg-chart');
        const esg = forecast.esg_trajectory || {};
        esgChart.innerHTML = `
            <div class="chart-bar">
                <div class="bar" style="height: ${(esg.current || 0) * 1.2}px"></div>
                <span class="bar-label">Cari: ${esg.current || '-'}</span>
            </div>
            <div class="chart-bar">
                <div class="bar" style="height: ${Math.min(parseFloat(esg.year_1) || 0, 100) * 1.2}px"></div>
                <span class="bar-label">İl 1: ${esg.year_1 || '-'}</span>
            </div>
            <div class="chart-bar">
                <div class="bar" style="height: ${Math.min(parseFloat(esg.year_2) || 0, 100) * 1.2}px"></div>
                <span class="bar-label">İl 2: ${esg.year_2 || '-'}</span>
            </div>
            <div class="chart-bar">
                <div class="bar" style="height: ${Math.min(parseFloat(esg.year_3) || 0, 100) * 1.2}px"></div>
                <span class="bar-label">İl 3: ${esg.year_3 || '-'}</span>
            </div>
        `;
        
        // Other info
        document.getElementById('market-position').textContent = forecast.market_position || '-';
        
        const opportunitiesList = document.getElementById('opportunities');
        opportunitiesList.innerHTML = '';
        (forecast.opportunities || []).forEach(opp => {
            const li = document.createElement('li');
            li.textContent = opp;
            opportunitiesList.appendChild(li);
        });
        
        const threatsList = document.getElementById('threats');
        threatsList.innerHTML = '';
        (forecast.threats || []).forEach(threat => {
            const li = document.createElement('li');
            li.textContent = threat;
            threatsList.appendChild(li);
        });
        
        // Investment recommendation
        const recommendation = forecast.investment_recommendation || '-';
        const investBadge = document.getElementById('invest-recommendation');
        investBadge.textContent = recommendation;
        investBadge.className = 'invest-badge';
        if (recommendation.toLowerCase().includes('al')) {
            investBadge.classList.add('buy');
        } else if (recommendation.toLowerCase().includes('saxla')) {
            investBadge.classList.add('hold');
        } else {
            investBadge.classList.add('sell');
        }
        
        document.getElementById('confidence-level').textContent = `Etibarlılıq: ${forecast.confidence_level || '-'}`;
        document.getElementById('forecast-summary').textContent = forecast.summary || '-';
        
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // Initialize
    loadCompanies();
});


