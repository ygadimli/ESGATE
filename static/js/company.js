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

// Company Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(tc => tc.classList.remove('active'));
            
            tab.classList.add('active');
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
    
    // ESG Form
    const esgForm = document.getElementById('esg-form');
    esgForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const btn = esgForm.querySelector('button[type="submit"]');
        btn.classList.add('loading');
        
        const data = {
            sector: document.getElementById('sector').value,
            employees: document.getElementById('employees').value,
            revenue: document.getElementById('revenue').value,
            energy: document.getElementById('energy').value,
            waste: document.getElementById('waste').value,
            social_programs: document.getElementById('social_programs').value,
            governance: document.getElementById('governance').value
        };
        
        try {
            const response = await fetch('/api/calculate-esg', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.error) {
                alert('Xəta baş verdi: ' + result.error);
                return;
            }
            
            displayESGResult(result);
        } catch (error) {
            alert('Xəta baş verdi: ' + error.message);
        } finally {
            btn.classList.remove('loading');
        }
    });
    
    function displayESGResult(result) {
        const resultCard = document.getElementById('esg-result');
        resultCard.classList.remove('hidden');
        
        // Animate overall score
        const overallScore = result.overall_score || 0;
        const overallCircle = document.getElementById('overall-circle');
        const overallScoreEl = document.getElementById('overall-score');
        
        const offset = 283 - (283 * overallScore / 100);
        overallCircle.style.strokeDashoffset = offset;
        
        // Change color based on score
        if (overallScore >= 70) {
            overallCircle.style.stroke = '#10b981';
        } else if (overallScore >= 50) {
            overallCircle.style.stroke = '#f59e0b';
        } else {
            overallCircle.style.stroke = '#ef4444';
        }
        
        animateNumber(overallScoreEl, overallScore);
        
        // Sub scores
        const envScore = result.environmental_score || 0;
        const socialScore = result.social_score || 0;
        const govScore = result.governance_score || 0;
        
        document.getElementById('env-bar').style.width = `${envScore}%`;
        document.getElementById('social-bar').style.width = `${socialScore}%`;
        document.getElementById('gov-bar').style.width = `${govScore}%`;
        
        animateNumber(document.getElementById('env-score'), envScore);
        animateNumber(document.getElementById('social-score'), socialScore);
        animateNumber(document.getElementById('gov-score'), govScore);
        
        // EU Compliance
        const compliance = result.eu_compliance || 'Bilinmir';
        const complianceBadge = document.getElementById('eu-compliance');
        complianceBadge.textContent = compliance;
        complianceBadge.style.background = compliance === 'Yüksək' ? 'rgba(16, 185, 129, 0.2)' :
                                           compliance === 'Orta' ? 'rgba(245, 158, 11, 0.2)' :
                                           'rgba(239, 68, 68, 0.2)';
        complianceBadge.style.color = compliance === 'Yüksək' ? '#10b981' :
                                       compliance === 'Orta' ? '#f59e0b' : '#ef4444';
        
        // Summary
        document.getElementById('summary').textContent = result.summary || '-';
        
        // Recommendations
        const recList = document.getElementById('recommendations');
        recList.innerHTML = '';
        (result.recommendations || []).forEach(rec => {
            const li = document.createElement('li');
            li.textContent = rec;
            recList.appendChild(li);
        });
        
        // Risks
        const riskList = document.getElementById('risks');
        riskList.innerHTML = '';
        (result.risk_areas || []).forEach(risk => {
            const li = document.createElement('li');
            li.textContent = risk;
            riskList.appendChild(li);
        });
        
        // Scroll to result
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // ROI Form
    const roiForm = document.getElementById('roi-form');
    roiForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const btn = roiForm.querySelector('button[type="submit"]');
        btn.classList.add('loading');
        
        const data = {
            current_roi: document.getElementById('current_roi').value,
            budget: document.getElementById('budget').value,
            sector: document.getElementById('roi_sector').value,
            esg_focus: document.getElementById('esg_focus').value,
            risk_tolerance: document.getElementById('risk_tolerance').value
        };
        
        try {
            const response = await fetch('/api/optimize-roi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.error) {
                alert('Xəta baş verdi: ' + result.error);
                return;
            }
            
            displayROIResult(result);
        } catch (error) {
            alert('Xəta baş verdi: ' + error.message);
        } finally {
            btn.classList.remove('loading');
        }
    });
    
    function displayROIResult(result) {
        const resultCard = document.getElementById('roi-result');
        resultCard.classList.remove('hidden');
        
        document.getElementById('optimized-roi').textContent = result.optimized_roi || '-';
        document.getElementById('timeline').textContent = result.timeline || '-';
        
        // Investment areas chart
        const chartContainer = document.getElementById('investment-chart');
        chartContainer.innerHTML = '';
        (result.investment_areas || []).forEach(area => {
            const item = document.createElement('div');
            item.className = 'investment-item';
            item.innerHTML = `
                <span class="investment-name">${area.area}</span>
                <div class="investment-bar">
                    <div class="investment-fill" style="width: ${area.allocation}">${area.allocation} - ${area.expected_return}</div>
                </div>
            `;
            chartContainer.appendChild(item);
        });
        
        // Key actions
        const actionsList = document.getElementById('key-actions');
        actionsList.innerHTML = '';
        (result.key_actions || []).forEach(action => {
            const li = document.createElement('li');
            li.textContent = action;
            actionsList.appendChild(li);
        });
        
        // Summary
        document.getElementById('roi-summary').textContent = result.summary || '-';
        
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // Roadmap Form
    const roadmapForm = document.getElementById('roadmap-form');
    roadmapForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const btn = roadmapForm.querySelector('button[type="submit"]');
        btn.classList.add('loading');
        
        const data = {
            sector: document.getElementById('rm_sector').value,
            size: document.getElementById('size').value,
            current_level: document.getElementById('current_level').value,
            target: document.getElementById('target').value,
            timeline: document.getElementById('rm_timeline').value
        };
        
        try {
            const response = await fetch('/api/generate-roadmap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.error) {
                alert('Xəta baş verdi: ' + result.error);
                return;
            }
            
            displayRoadmapResult(result);
        } catch (error) {
            alert('Xəta baş verdi: ' + error.message);
        } finally {
            btn.classList.remove('loading');
        }
    });
    
    function displayRoadmapResult(result) {
        const resultCard = document.getElementById('roadmap-result');
        resultCard.classList.remove('hidden');
        
        document.getElementById('total-investment').textContent = result.total_investment || '-';
        
        // Phases
        const phasesContainer = document.getElementById('roadmap-phases');
        phasesContainer.innerHTML = '';
        (result.phases || []).forEach(phase => {
            const phaseEl = document.createElement('div');
            phaseEl.className = 'roadmap-phase';
            phaseEl.innerHTML = `
                <div class="phase-header">
                    <span class="phase-number">Faza ${phase.phase}</span>
                    <span class="phase-title">${phase.title}</span>
                    <span class="phase-duration">${phase.duration}</span>
                </div>
                <div class="phase-content">
                    <div class="phase-tasks">
                        <h5>Tapşırıqlar</h5>
                        <ul>
                            ${(phase.tasks || []).map(t => `<li>${t}</li>`).join('')}
                        </ul>
                    </div>
                    <div class="phase-resources">${phase.resources_needed || ''}</div>
                </div>
            `;
            phasesContainer.appendChild(phaseEl);
        });
        
        // Expected outcomes
        const outcomesList = document.getElementById('expected-outcomes');
        outcomesList.innerHTML = '';
        (result.expected_outcomes || []).forEach(outcome => {
            const li = document.createElement('li');
            li.textContent = outcome;
            outcomesList.appendChild(li);
        });
        
        // Success metrics
        const metricsList = document.getElementById('success-metrics');
        metricsList.innerHTML = '';
        (result.success_metrics || []).forEach(metric => {
            const li = document.createElement('li');
            li.textContent = metric;
            metricsList.appendChild(li);
        });
        
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // Helper function to animate numbers
    function animateNumber(element, target) {
        const duration = 800;
        const start = 0;
        const startTime = performance.now();
        
        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            
            element.textContent = Math.round(start + (target - start) * easeProgress);
            
            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }
        
        requestAnimationFrame(update);
    }
});


