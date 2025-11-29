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

// Kids Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    let expenses = [];
    
    // Add expense
    document.getElementById('add-expense').addEventListener('click', function() {
        const category = document.getElementById('expense-category').value;
        const amount = parseFloat(document.getElementById('expense-amount').value);
        
        if (!category || !amount || amount <= 0) {
            alert('Kateqoriya seç və məbləğ daxil et!');
            return;
        }
        
        expenses.push({
            id: Date.now(),
            category: category,
            amount: amount
        });
        
        document.getElementById('expense-category').value = '';
        document.getElementById('expense-amount').value = '';
        
        renderExpenses();
    });
    
    function renderExpenses() {
        const container = document.getElementById('expenses-container');
        
        if (expenses.length === 0) {
            container.innerHTML = '<p class="empty-state">Hələ heç bir xərc yoxdur</p>';
            return;
        }
        
        container.innerHTML = expenses.map(expense => `
            <div class="expense-item">
                <div class="expense-info">
                    <span class="expense-category">${expense.category}</span>
                </div>
                <span class="expense-amount">-${expense.amount} AZN</span>
                <span class="delete-expense" data-id="${expense.id}">🗑️</span>
            </div>
        `).join('');
        
        // Add delete handlers
        container.querySelectorAll('.delete-expense').forEach(btn => {
            btn.addEventListener('click', function() {
                const id = parseInt(this.dataset.id);
                expenses = expenses.filter(e => e.id !== id);
                renderExpenses();
            });
        });
    }
    
    // Analyze button
    document.getElementById('analyze-btn').addEventListener('click', async function() {
        const allowance = parseFloat(document.getElementById('allowance').value) || 0;
        const goal = document.getElementById('goal').value || '';
        const goalAmount = parseFloat(document.getElementById('goal-amount').value) || 0;
        
        if (!allowance) {
            alert('Cib xərcliyini daxil et!');
            return;
        }
        
        this.classList.add('loading');
        
        try {
            const response = await fetch('/api/kids-expense', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    expenses: expenses,
                    allowance: allowance,
                    goal: goal,
                    goal_amount: goalAmount
                })
            });
            
            const result = await response.json();
            
            if (result.error) {
                alert('Xəta baş verdi: ' + result.error);
                return;
            }
            
            displayTrackerResult(result, allowance, goal, goalAmount);
        } catch (error) {
            alert('Xəta baş verdi: ' + error.message);
        } finally {
            this.classList.remove('loading');
        }
    });
    
    function displayTrackerResult(result, allowance, goal, goalAmount) {
        const resultCard = document.getElementById('tracker-result');
        resultCard.classList.remove('hidden');
        
        const analysis = result.analysis || {};
        
        document.getElementById('total-allowance').textContent = `${allowance} AZN`;
        document.getElementById('total-spent').textContent = `${result.total_expenses} AZN`;
        document.getElementById('remaining').textContent = `${result.remaining} AZN`;
        
        // Goal progress
        if (goal && goalAmount > 0) {
            const progress = Math.min((result.remaining / goalAmount) * 100, 100);
            document.getElementById('progress-fill').style.width = `${progress}%`;
            document.getElementById('goal-text').textContent = 
                `${goal}: ${result.remaining} / ${goalAmount} AZN (${Math.round(progress)}%)`;
        } else {
            document.getElementById('progress-fill').style.width = '0%';
            document.getElementById('goal-text').textContent = 'Hədəf təyin edilməyib';
        }
        
        // AI tips
        document.getElementById('summary-tip').textContent = analysis.summary || '-';
        document.getElementById('savings-tip').textContent = analysis.savings_tip || '-';
        document.getElementById('achievement').textContent = analysis.achievement || '-';
        document.getElementById('next-step').textContent = analysis.next_step || '-';
        document.getElementById('fun-fact').textContent = analysis.fun_fact || '-';
        
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // Chatbot
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatMessages = document.getElementById('chat-messages');
    
    async function sendMessage(message) {
        if (!message.trim()) return;
        
        // Add user message
        const userMsg = document.createElement('div');
        userMsg.className = 'chat-message user';
        userMsg.innerHTML = `
            <div class="message-avatar">👤</div>
            <div class="message-content">
                <p>${escapeHtml(message)}</p>
            </div>
        `;
        chatMessages.appendChild(userMsg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        chatInput.value = '';
        sendBtn.classList.add('loading');
        
        try {
            const response = await fetch('/api/kids-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            });
            
            const result = await response.json();
            
            // Add bot message
            const botMsg = document.createElement('div');
            botMsg.className = 'chat-message bot';
            botMsg.innerHTML = `
                <div class="message-avatar">🦉</div>
                <div class="message-content">
                    <p>${result.response || 'Bir problem oldu, bir daha cəhd et!'}</p>
                </div>
            `;
            chatMessages.appendChild(botMsg);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } catch (error) {
            const errorMsg = document.createElement('div');
            errorMsg.className = 'chat-message bot';
            errorMsg.innerHTML = `
                <div class="message-avatar">🦉</div>
                <div class="message-content">
                    <p>Ups! Bir problem oldu. Bir daha cəhd edək? 🤔</p>
                </div>
            `;
            chatMessages.appendChild(errorMsg);
        } finally {
            sendBtn.classList.remove('loading');
        }
    }
    
    sendBtn.addEventListener('click', () => sendMessage(chatInput.value));
    
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage(chatInput.value);
        }
    });
    
    // Quick questions
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            sendMessage(this.dataset.question);
        });
    });
    
    // Helper function
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});


