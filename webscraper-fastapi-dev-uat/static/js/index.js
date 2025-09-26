
class FashionScraper {
    constructor() {
        this.isScrapingActive = false;
        this.currentTaskId = null;
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.initializeElements();
        this.bindEvents();
        this.setupNotifications();
        // this.getDomainUrls();
        this.urls = [];
        this.currentPage = 1;
        this.domainList = document.getElementById("domainList");
        this.pagination = document.getElementById("pagination");
        this.perPageSelect = document.getElementById("perPageSelect");
        if (!this.perPageSelect) {
            console.error("perPageSelect element not found in DOM at init");
        }

        // bind events
        document.getElementById("scrapeDomain")
            .addEventListener("click", () => this.getDomainUrls());

        if (this.perPageSelect) {
            this.perPageSelect.addEventListener("change", () => {
                this.currentPage = 1;
                this.render();
            });
        }
    }

    initializeElements() {
        this.urlInput = document.getElementById('urlInput');
        this.scrapeBtn = document.getElementById('scrapeBtn');
        // this.scrapeBtnDomain = document.getElementById('scrapeDomain');
        this.clearBtn = document.getElementById('clearBtn');
        this.activeTasksBtn = document.getElementById('activeTasksBtn');
        this.activeTasksCount = document.getElementById('activeTasksCount');
        this.chatMessages = document.getElementById('chatMessages');
        this.maxPages = document.getElementById('maxPages');
        this.aiPagination = document.getElementById('aiPagination');
        this.aiExtraction = document.getElementById('aiExtraction');
        this.showDomain = document.getElementById('showDomain');
        this.showProducts = document.getElementById('showProducts');

        this.inputSectionurl = document.getElementById('inputSectionurl');
        this.inputSectionScrape = document.getElementById('inputSectionScrape');

        this.showDomain.checked = true;
        this.showProducts.checked = false;
        this.inputSectionScrape.classList.add('hidden');
    }

    bindEvents() {
        this.scrapeBtn.addEventListener('click', () => this.startScraping());
        // this.scrapeBtnDomain.addEventListener('click', () => this.getDomainUrls());
        this.clearBtn.addEventListener('click', () => this.clearAll());
        this.activeTasksBtn.addEventListener('click', () => this.showActiveTasksModal());
        this.showDomain.addEventListener('change', () => {
            if (this.showDomain.checked) {
                // this.showProducts.checked = true;
                this.inputSectionurl.classList.remove('hidden');
                this.inputSectionScrape.classList.add('hidden');
            }
        });
        this.showProducts.addEventListener('change', () => {
            if (this.showProducts.checked) {
                // this.showDomain.checked = false;
                this.inputSectionScrape.classList.remove('hidden');
                this.inputSectionurl.classList.add('hidden');
            }
        });


        this.urlInput.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.startScraping();
            }
        });

        this.urlInput.addEventListener('input', () => {
            this.updateScrapeButton();
        });

        // Check for active tasks periodically
        this.startActiveTasksMonitoring();
    }

    startActiveTasksMonitoring() {
        // Check immediately
        this.updateActiveTasksDisplay();

        // Then check every 10 seconds
        setInterval(() => {
            this.updateActiveTasksDisplay();
        }, 10000);
    }

    handleSelection() {
        console.log(this.showDomain);
        if (this.showDomain.checked) {
            this.inputSectionurl.classList.remove("hidden");
            // this.inputSectionScrape.classList.add("hidden");
        } else if (this.showProducts.checked) {
            // this.inputSectionurl.classList.remove("hidden");
            this.inputSectionScrape.classList.add("hidden");
        }
    }

    async updateActiveTasksDisplay() {
        try {
            const response = await fetch('/api/active-tasks');
            if (response.ok) {
                const data = await response.json();
                const activeCount = data.total_active || 0;

                this.activeTasksCount.textContent = activeCount;

                if (activeCount > 0) {
                    this.activeTasksBtn.style.display = 'inline-flex';
                    this.activeTasksBtn.classList.add('pulse-animation');
                } else {
                    this.activeTasksBtn.style.display = 'none';
                    this.activeTasksBtn.classList.remove('pulse-animation');
                }
            }
        } catch (error) {
            console.error('Error checking active tasks:', error);
        }
    }

    async showActiveTasksModal() {
        try {
            const response = await fetch('/api/active-tasks');
            if (response.ok) {
                const data = await response.json();
                const activeTasks = data.active_tasks || [];

                if (activeTasks.length === 0) {
                    this.addMessage('ℹ️ No currently active tasks found.', 'system');
                    return;
                }

                let tasksInfo = `📊 <strong>Active Tasks (${activeTasks.length}):</strong><br><br>`;
                activeTasks.forEach((task, index) => {
                    const startTime = new Date(task.start_time).toLocaleString();
                    const progress = task.current_progress?.percentage || 0;
                    tasksInfo += `<div style="background: rgba(139, 92, 246, 0.1); padding: 8px; border-radius: 6px; margin: 4px 0;">`;
                    tasksInfo += `<strong>${index + 1}. ${task.scraper_type.toUpperCase()}</strong><br>`;
                    tasksInfo += `<code>ID: ${task.task_id}</code><br>`;
                    tasksInfo += `Status: ${task.status} (${progress}%)<br>`;
                    tasksInfo += `URLs: ${task.urls_count} | Started: ${startTime}`;
                    tasksInfo += `</div>`;
                });

                this.addMessage(tasksInfo, 'system');
            }
        } catch (error) {
            this.addMessage('❌ Error fetching active tasks: ' + error.message, 'error');
        }
    }

    updateScrapeButton() {
        const hasUrls = this.urlInput.value.trim().length > 0;
        this.scrapeBtn.disabled = !hasUrls || this.isScrapingActive;
    }

    async clearAll() {
        // First, terminate any active tasks
        await this.terminateActiveTasks();

        // Clear the UI
        this.urlInput.value = '';
        this.chatMessages.innerHTML = `
                    <div class="empty-state">
                        <h3>Ready to Scrape Fashion Products</h3>
                        <p>Enter one or more e-commerce URLs below to start extracting product data with AI intelligence.</p>
                        <p><strong>Supported:</strong> Shopify, WooCommerce, and custom e-commerce sites</p>
                    </div>
                `;

        // Reset scraping state
        this.resetScrapingState();
        this.updateScrapeButton();
    }

    async terminateActiveTasks() {
        try {
            // Get active tasks
            const activeTasksResponse = await fetch('/api/active-tasks');
            if (!activeTasksResponse.ok) {
                console.log('No active tasks to terminate');
                return;
            }

            const activeTasksData = await activeTasksResponse.json();
            const activeTasks = activeTasksData.active_tasks || [];

            if (activeTasks.length === 0) {
                console.log('No active tasks found');
                return;
            }

            // Extract task IDs
            const taskIds = activeTasks.map(task => task.task_id);
            console.log('🛑 Terminating active tasks:', taskIds);

            // Add notification about termination
            this.addMessage(`🛑 <strong>Terminating ${taskIds.length} active task(s)...</strong><br>Closing connections and cleaning up.`, 'system');

            // Terminate tasks
            const terminateResponse = await fetch('/api/terminate-tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    task_ids: taskIds,
                    reason: 'User clicked Clear button'
                })
            });

            if (terminateResponse.ok) {
                const terminateData = await terminateResponse.json();
                console.log('✅ Tasks terminated successfully:', terminateData);

                if (terminateData.total_terminated > 0) {
                    this.addMessage(`✅ <strong>Successfully terminated ${terminateData.total_terminated} task(s)</strong><br>All connections closed.`, 'success');
                }

                if (terminateData.failed_terminations.length > 0) {
                    console.warn('Some tasks failed to terminate:', terminateData.failed_terminations);
                }
            } else {
                console.error('Failed to terminate tasks:', terminateResponse.status);
                this.addMessage('⚠️ <strong>Warning:</strong> Some tasks may still be running.', 'error');
            }

        } catch (error) {
            console.error('Error terminating tasks:', error);
            this.addMessage('⚠️ <strong>Error terminating tasks:</strong> ' + error.message, 'error');
        }
    }

    clearResults() {
        // Remove any existing progress containers or results
        const progressContainers = this.chatMessages.querySelectorAll('.progress-container, .stats-container, .products-grid');
        progressContainers.forEach(container => container.remove());
    }

    addMessage(content, type = 'system') {
        if (this.chatMessages.querySelector('.empty-state')) {
            this.chatMessages.innerHTML = '';
        }

        const message = document.createElement('div');
        message.className = `message ${type}`;
        message.innerHTML = content;
        this.chatMessages.appendChild(message);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    async startScraping() {
    const urls = this.urlInput.value.trim();
    if (!urls) {
        this.addMessage('⚠️ Please enter at least one URL to scrape.', 'error');
        return;
    }

    const urlList = urls.split('\n').filter(url => url.trim()).map(url => url.trim());
    if (urlList.length === 0) {
        this.addMessage('⚠️ Please enter valid URLs.', 'error');
        return;
    }

    // Get settings
    const maxPages = parseInt(this.maxPages.value) || 50;
    const useAiPagination = this.aiPagination.checked;
    const aiExtractionMode = this.aiExtraction.checked;

    // Clear previous results and start fresh
    this.clearResults();
    this.isScrapingActive = true;
    this.scrapeBtn.textContent = 'AI Processing...';
    this.scrapeBtn.disabled = true;

    try {
        // ✅ Step 1: Save URLs to backend file for cron usage
        const saveResp = await fetch('/api/save-urls', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: urlList })
        });
        if (!saveResp.ok) {
            throw new Error(`Failed to save URLs (status: ${saveResp.status})`);
        }
        const saveData = await saveResp.json();
        console.log("URLs saved:", saveData);

        // ✅ Step 2: Start scraping task (old flow preserved)
        const response = await fetch('/scrape/ai', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                urls: urlList,
                max_pages_per_url: maxPages,
                use_ai_pagination: useAiPagination,
                ai_extraction_mode: aiExtractionMode
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            this.currentTaskId = result.data.task_id;
            this.addMessage(`
                <div class="task-started-compact">
                    <span class="status-icon">✅</span>
                    <span class="status-text">Task started</span>
                    <span class="task-id-container">
                        <span class="task-id-label">ID:</span>
                        <code class="task-id-code"
                              onclick="navigator.clipboard.writeText('${this.currentTaskId}'); this.classList.add('copied'); setTimeout(() => this.classList.remove('copied'), 2000)"
                              title="Click to copy">${this.currentTaskId}</code>
                    </span>
                </div>
            `, 'success');

            // Start monitoring progress with WebSocket
            await this.monitorProgress();

        } else {
            throw new Error(result.error || 'Unknown error occurred');
        }

    } catch (error) {
        console.error('Error starting scraping:', error);
        this.addMessage(`❌ <strong>Failed to start scraping:</strong> ${error.message}`, 'error');
        this.resetScrapingState();
    }
}


    setupNotifications() {
        if ('Notification' in window) {
            Notification.requestPermission();
        }
    }

    showNotification(title, body, type = 'info') {
        if ('Notification' in window && Notification.permission === 'granted') {
            const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
            new Notification(`${icon} ${title}`, {
                body: body,
                icon: '/favicon.ico'
            });
        }
    }

    connectWebSocket(taskId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${taskId}`;

        console.log('🔌 Connecting to WebSocket:', wsUrl);
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('🔌 WebSocket connected for real-time updates');
            this.reconnectAttempts = 0;
            this.addMessage('🔌 <strong>Real-time connection established</strong><br>Live updates enabled', 'success');
        };

        this.websocket.onmessage = (event) => {
            console.log('📨 WebSocket message received:', event.data);
            try {
                const message = JSON.parse(event.data);
                this.handleWebSocketMessage(message);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.addMessage('⚠️ <strong>Connection issue:</strong> Falling back to polling updates', 'error');
        };

        this.websocket.onclose = (event) => {
            console.log('WebSocket connection closed:', event.code, event.reason);
            if (this.isScrapingActive && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`🔄 Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                setTimeout(() => this.connectWebSocket(taskId), 2000 * this.reconnectAttempts);
            }
        };
    }

    handleWebSocketMessage(message) {
        console.log('🔄 Processing WebSocket message:', message.type, message.data);

        switch (message.type) {
            case 'progress_update':
                this.updateProgress(message.data);
                break;
            case 'task_completed':
                this.handleTaskCompletion(message.data);
                break;
            case 'task_failed':
                this.handleTaskFailure(message.data);
                break;
            case 'task_terminated':
                this.handleTaskTermination(message.data);
                break;
            case 'status_update':
                this.handleStatusUpdate(message.data);
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    handleTaskTermination(terminationData) {
        console.log('🛑 Task terminated:', terminationData);
        this.addMessage(`🛑 <strong>Task Terminated:</strong> ${terminationData.reason}<br><code>Task ID: ${terminationData.task_id}</code>`, 'error');
        this.resetScrapingState();
    }

    updateProgress(progressData) {
        console.log('📊 Updating progress:', progressData);

        const progressText = document.getElementById('progressText');
        const progressFill = document.getElementById('progressFill');
        const progressDetails = document.getElementById('progressDetails');
        const progressLog = document.getElementById('progressLog');

        if (progressText && progressFill && progressDetails) {
            const percentage = progressData.percentage || 0;
            const details = progressData.details || 'Processing...';

            progressText.textContent = `${percentage}%`;
            progressFill.style.width = `${percentage}%`;
            progressDetails.innerHTML = `<i class="fas fa-robot"></i> ${details}`;

            // Add stage-specific styling
            progressFill.className = 'progress-fill';
            if (progressData.stage === 'ai_analysis') {
                progressFill.style.background = 'linear-gradient(90deg, var(--accent-purple), var(--accent-pink))';
            } else if (progressData.stage === 'extraction' || progressData.stage === 'scraping_pages') {
                progressFill.style.background = 'linear-gradient(90deg, var(--accent-blue), var(--accent-purple))';
            } else if (progressData.stage === 'completed') {
                progressFill.style.background = 'linear-gradient(90deg, var(--success-green), var(--accent-blue))';
            } else {
                progressFill.style.background = 'var(--primary-gradient)';
            }

            // Add detailed log entry
            if (progressLog) {
                this.addLogEntry(progressData.stage, details, progressData.stats);
            }

            console.log(`✅ Progress updated: ${percentage}% - ${details}`);
        } else {
            console.error('❌ Progress elements not found in DOM');
        }
    }

    addLogEntry(stage, details, stats) {
        const progressLog = document.getElementById('progressLog');
        if (!progressLog) return;

        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');

        // Determine log entry class based on content
        let entryClass = 'log-entry';
        if (details.includes('✅') || details.includes('Success') || details.includes('complete')) {
            entryClass += ' success';
        } else if (details.includes('❌') || details.includes('Failed') || details.includes('Error')) {
            entryClass += ' error';
        } else if (stage === 'ai_analysis') {
            entryClass += ' ai-analysis';
        } else if (stage === 'extraction') {
            entryClass += ' extraction';
        }

        logEntry.className = entryClass;

        // Add stats if available
        let statsText = '';
        if (stats && (stats.products_found > 0 || stats.pages_analyzed > 0)) {
            statsText = ` [Products: ${stats.products_found || 0}, Pages: ${stats.pages_analyzed || 0}]`;
        }

        logEntry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${details}${statsText}`;

        progressLog.appendChild(logEntry);

        // Auto-scroll to bottom
        const detailedProgress = document.getElementById('detailedProgress');
        if (detailedProgress) {
            detailedProgress.scrollTop = detailedProgress.scrollHeight;
        }

        // Limit log entries to prevent memory issues
        if (progressLog.children.length > 50) {
            progressLog.removeChild(progressLog.firstChild);
        }
    }

    handleTaskCompletion(taskData) {
        console.log('🎉 Task completed:', taskData);
        this.showNotification('Scraping Completed!', `Found ${taskData.result?.products?.length || 0} products`);

        setTimeout(() => {
            this.displayResults(taskData.result);
            this.resetScrapingState();
        }, 1000);
    }

    handleTaskFailure(taskData) {
        console.log('❌ Task failed:', taskData);
        this.showNotification('Scraping Failed', taskData.error || 'Unknown error', 'error');
        this.addMessage(`❌ <strong>Scraping failed:</strong> ${taskData.error || 'Unknown error'}`, 'error');
        this.resetScrapingState();
    }

    handleStatusUpdate(statusData) {
        console.log('📈 Status update:', statusData);
        if (statusData.current_progress) {
            this.updateProgress(statusData.current_progress);
        }
    }

    async monitorProgress() {
        // Create enhanced progress container with detailed updates
        const progressContainer = document.createElement('div');
        progressContainer.className = 'progress-container';
        progressContainer.innerHTML = `
                    <div class="progress-header">
                        <div class="progress-title">
                            <i class="fas fa-brain"></i>
                            <strong>AI Scraping Progress</strong>
                        </div>
                        <div class="progress-stats">
                            <span id="progressText" class="progress-percentage">0%</span>
                            <div class="connection-status">
                                <i class="fas fa-wifi connection-icon"></i>
                                <span>Live</span>
                            </div>
                        </div>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill"></div>
                            <div class="progress-glow"></div>
                        </div>
                    </div>
                    <div id="progressDetails" class="progress-details">
                        <i class="fas fa-robot"></i> Initializing AI agent...
                    </div>
                    <div id="detailedProgress" class="detailed-progress">
                        <div class="progress-log" id="progressLog">
                            <div class="log-entry">🚀 AI scraping session started...</div>
                        </div>
                    </div>
                `;

        this.chatMessages.appendChild(progressContainer);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;

        // Connect WebSocket for real-time updates
        console.log('🚀 Starting WebSocket connection for task:', this.currentTaskId);
        this.connectWebSocket(this.currentTaskId);
    }
debugGridLayout() {
    const grid = document.getElementById("productsGrid");
    if (!grid) {
        console.error("❌ Products grid not found");
        return;
    }

    console.log("🔍 Grid Debug Info:", {
        element: grid,
        inlineStyle: grid.getAttribute('style'),
        computedDisplay: window.getComputedStyle(grid).display,
        computedGridTemplateColumns: window.getComputedStyle(grid).gridTemplateColumns,
        computedWidth: window.getComputedStyle(grid).width,
        childrenCount: grid.children.length,
        parent: grid.parentElement
    });

    // Force grid layout
    grid.style.display = 'grid';
    grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(300px, 1fr))';
    grid.style.gap = '20px';
    grid.style.width = '100%';
    
    // Remove any flex properties
    grid.style.flex = '';
    grid.style.flexDirection = '';
    grid.style.flexWrap = '';
    
    console.log("✅ Grid layout enforced");
}
displayResults(result) {
    const products = result.products || [];
    const metadata = result.metadata || {};

    // Add stats container at the top
    const statsHtml = `
        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-number">${products.length}</div>
                <div class="stat-label">Products Found</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${metadata.urls_processed || 0}</div>
                <div class="stat-label">URLs Processed</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${metadata.ai_stats?.ai_extraction_success || 0}</div>
                <div class="stat-label">AI Extractions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${metadata.total_pages_processed || 0}</div>
                <div class="stat-label">Pages Processed</div>
            </div>
        </div>
    `;

    // Insert stats
    this.addMessage(statsHtml, "success");

    // If no products, show message
    if (products.length === 0) {
        this.addMessage("ℹ️ No products were found in the provided URLs.", "system");
        return;
    }

    this.currentProducts = products;

    // Build products section
    const productsSection = document.createElement("div");
    productsSection.className = "products-section";
    
    productsSection.innerHTML = `
        <div class="products-header">
            <div class="products-actions">
                <button id="selectAllBtn" class="btn btn-secondary">
                    <i class="fas fa-check-square"></i> Select All
                </button>
                <button id="editUploadBtn" class="btn btn-primary" style="display: none;">
                    <i class="fas fa-edit"></i> Edit & Upload (<span id="selectedCount">0</span>)
                </button>
            </div>
        </div>
        <h3 style="margin: 15px 0;">🛍️ Extracted Products (${products.length})</h3>
        <div class="products-grid" id="productsGrid">
            ${products.map((product, index) => this.createProductCard(product, index)).join("")}
        </div>
    `;

    this.chatMessages.appendChild(productsSection);

    // Clean up any inline styles and setup event listeners
    setTimeout(() => {
        this.debugGridLayout();
        this.cleanupGridStyles();
        this.setupProductEventListeners();
    }, 100);
}

// Add this cleanup method to remove any conflicting inline styles
cleanupGridStyles() {
    const grid = document.getElementById("productsGrid");
    if (!grid) return;

    // Remove all inline styles that might interfere with CSS grid
    grid.removeAttribute('style');
    
    // Remove any flexbox properties
    grid.style.display = 'grid';
    grid.style.flexDirection = '';
    grid.style.flexWrap = '';
    grid.style.justifyContent = '';
    grid.style.alignItems = '';
    grid.style.flex = '';
    
    console.log('Grid styles cleaned up:', {
        display: window.getComputedStyle(grid).display,
        gridTemplateColumns: window.getComputedStyle(grid).gridTemplateColumns,
        childrenCount: grid.children.length
    });
}

// Update your setupProductEventListeners to remove ensureGridLayout call
setupProductEventListeners() {
    console.log('🔧 Setting up product event listeners...');
    
    // Select All button
    const selectAllBtn = document.getElementById('selectAllBtn');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('✅ Select All button clicked');
            this.selectAllProducts();
        });
    }

    // Edit & Upload button  
    const editUploadBtn = document.getElementById('editUploadBtn');
    if (editUploadBtn) {
        editUploadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('✅ Edit & Upload button clicked');
            this.editSelectedProducts();
        });
    }

    // Product checkboxes with event delegation
    const productsGrid = document.getElementById('productsGrid');
    if (productsGrid) {
        productsGrid.addEventListener('change', (e) => {
            if (e.target && e.target.classList.contains('product-checkbox')) {
                this.handleProductSelection();
            }
        });
    }

    // Initialize selection state
    this.handleProductSelection();
}



// Add this method to your FashionScraper class
ensureGridLayout() {
    const grid = document.getElementById("productsGrid");
    if (!grid) {
        console.error("Products grid not found");
        return;
    }

    // Remove any conflicting inline styles
    grid.removeAttribute('style');
    
    // Force grid layout
    grid.style.display = 'grid';
    grid.style.gridTemplateColumns = 'repeat(3, 1fr)';
    grid.style.gap = '16px';
    grid.style.marginTop = '16px';
    grid.style.width = '100%';
    
    // Remove any flexbox properties that might have been added
    grid.style.flexDirection = '';
    grid.style.flexWrap = '';
    grid.style.justifyContent = '';
    grid.style.alignItems = '';
    
    console.log('Grid layout enforced:', {
        display: grid.style.display,
        gridTemplateColumns: grid.style.gridTemplateColumns,
        childrenCount: grid.children.length
    });
}

// Update your setupProductEventListeners method to include this:
setupProductEventListeners() {
    console.log('🔧 Setting up product event listeners...');
    
    // Ensure proper grid layout first
    this.ensureGridLayout();
    
    // Select All button
    const selectAllBtn = document.getElementById('selectAllBtn');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('✅ Select All button clicked');
            this.selectAllProducts();
        });
        console.log('✅ Select All button listener attached');
    } else {
        console.error('❌ selectAllBtn not found in DOM');
    }

    // Edit & Upload button  
    const editUploadBtn = document.getElementById('editUploadBtn');
    if (editUploadBtn) {
        editUploadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('✅ Edit & Upload button clicked');
            this.editSelectedProducts();
        });
        console.log('✅ Edit & Upload button listener attached');
    } else {
        console.error('❌ editUploadBtn not found in DOM');
    }

    // Product checkboxes with event delegation
    const productsGrid = document.getElementById('productsGrid');
    if (productsGrid) {
        productsGrid.addEventListener('change', (e) => {
            if (e.target && e.target.classList.contains('product-checkbox')) {
                console.log(`✅ Checkbox ${e.target.id} changed to: ${e.target.checked}`);
                this.handleProductSelection();
            }
        });
        console.log('✅ Product grid change listener attached');
    } else {
        console.error('❌ productsGrid not found in DOM');
    }

    // Initialize selection state
    this.handleProductSelection();
    console.log('🎉 All event listeners setup complete');
}
setupProductEventListeners() {
    console.log('🔧 Setting up product event listeners...');
    
    // Select All button
    const selectAllBtn = document.getElementById('selectAllBtn');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('✅ Select All button clicked');
            this.selectAllProducts();
        });
        console.log('✅ Select All button listener attached');
    } else {
        console.error('❌ selectAllBtn not found in DOM');
    }

    // Edit & Upload button  
    const editUploadBtn = document.getElementById('editUploadBtn');
    if (editUploadBtn) {
        editUploadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('✅ Edit & Upload button clicked');
            this.editSelectedProducts();
        });
        console.log('✅ Edit & Upload button listener attached');
    } else {
        console.error('❌ editUploadBtn not found in DOM');
    }

    // Product checkboxes with event delegation
    const productsGrid = document.getElementById('productsGrid');
    if (productsGrid) {
        productsGrid.addEventListener('change', (e) => {
            if (e.target && e.target.classList.contains('product-checkbox')) {
                console.log(`✅ Checkbox ${e.target.id} changed to: ${e.target.checked}`);
                this.handleProductSelection();
            }
        });
        console.log('✅ Product grid change listener attached');
    } else {
        console.error('❌ productsGrid not found in DOM');
    }

    // Initialize selection state
    this.handleProductSelection();
    console.log('🎉 All event listeners setup complete');
}
    // UPDATED: Remove inline onclick handlers from createProductCard
createProductCard(product, index) {
    console.log('product price:', product);
    
    const price = product.price && product.price > 0 
        ? `₹${product.price.toLocaleString()}` 
        : 'Price not available';
        
    const image = product.product_images && product.product_images.length > 0
        ? product.product_images[0]
        : 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDMwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIzMDAiIGhlaWdodD0iMjAwIiBmaWxsPSIjRjFGNUY5Ii8+CjxwYXRoIGQ9Ik0xNTAgMTAwQzE1MCA4Mi4zNDMxIDE2NS4zNDMgNjcgMTgzIDY3QzIwMC42NTcgNjcgMjE2IDgyLjM0MzEgMjE2IDEwMEMyMTYgMTE3LjY1NyAyMDAuNjU3IDEzMyAxODMgMTMzQzE2NS4zNDMgMTMzIDE1MCAxMTcuNjU3IDE1MCAxMDBaIiBmaWxsPSIjQ0JENUUxIi8+CjxwYXRoIGQ9Ik0xMjAgMTMzSDE4MEwxNzAgMTUzSDE0MEwxMjAgMTMzWiIgZmlsbD0iI0NCRDVFMSIvPgo8L3N2Zz4K';

    // Fix: Properly handle description - strip HTML tags and truncate
    const description = product.description 
        ? product.description.replace(/<[^>]*>/g, '').substring(0, 100) + (product.description.length > 100 ? '...' : '')
        : 'No description available';

    const sizes = product.sizes && product.sizes.length > 0
        ? product.sizes.slice(0, 3).map(size => `<span class="tag">${size}</span>`).join('')
        : '';

    const colors = product.colors && product.colors.length > 0
        ? product.colors.slice(0, 2).map(color => `<span class="tag">${color}</span>`).join('')
        : '';

    const material = product.material ? `<span class="tag">${product.material}</span>` : '';

    return `
        <div class="product-card" data-product-index="${index}">
            <div class="product-select-overlay">
                <input type="checkbox" class="product-checkbox" id="product-${index}">
                <label for="product-${index}" class="product-select-label">
                    <i class="fas fa-check"></i>
                </label>
            </div>
            <img src="${image}" alt="${product.product_name}" class="product-image" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDMwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIzMDAiIGhlaWdodD0iMjAwIiBmaWxsPSIjRjFGNUY5Ii8+CjxwYXRoIGQ9Ik0xNTAgMTAwQzE1MCA4Mi4zNDMxIDE2NS4zNDMgNjcgMTgzIDY3QzIwMC42NTcgNjcgMjE2IDgyLjM0MzEgMjE2IDEwMEMyMTYgMTE3LjY1NyAyMDAuNjU3IDEzMyAxODMgMTMzQzE2NS4zNDMgMTMzIDE1MCAxMTcuNjU3IDE1MCAxMDBaIiBmaWxsPSIjQ0JENUUxIi8+CjxwYXRoIGQ9Ik0xMjAgMTMzSDE4MEwxNzAgMTUzSDE0MEwxMjAgMTMzWiIgZmlsbD0iI0NCRDVFMSIvPgo8L3N2Zz4K'">
            <div class="product-info">
                <div class="product-name">${product.product_name || 'Unnamed Product'}</div>
                <div class="product-price">${price}</div>
                <div class="product-details">${description}</div>
                <div class="product-tags">
                    ${sizes}
                    ${colors}
                    ${material}
                </div>
            </div>
        </div>
    `;
}

    resetScrapingState() {
        this.isScrapingActive = false;
        this.currentTaskId = null;
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        this.scrapeBtn.textContent = 'Grab Products';
        this.scrapeBtn.disabled = false;
    }

    handleProductSelection() {
        const checkboxes = document.querySelectorAll('.product-checkbox');
        const selectedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        
        console.log(`📊 Selection update: ${selectedCount}/${checkboxes.length} selected`);

        // Update selected count display
        const selectedCountSpan = document.getElementById('selectedCount');
        if (selectedCountSpan) {
            selectedCountSpan.textContent = selectedCount;
        }

        // Show/hide Edit & Upload button
        const editUploadBtn = document.getElementById('editUploadBtn');
        if (editUploadBtn) {
            if (selectedCount > 0) {
                editUploadBtn.style.display = 'inline-flex';
                console.log(`✅ Showing Edit & Upload button (${selectedCount} selected)`);
            } else {
                editUploadBtn.style.display = 'none';
                console.log('➖ Hiding Edit & Upload button (none selected)');
            }
        }

        // Update visual selection state for product cards
        checkboxes.forEach(checkbox => {
            const productCard = checkbox.closest('.product-card');
            if (productCard) {
                if (checkbox.checked) {
                    productCard.classList.add('selected');
                } else {
                    productCard.classList.remove('selected');
                }
            }
        });

        // Update Select All button text
        const selectAllBtn = document.getElementById('selectAllBtn');
        if (selectAllBtn) {
            const allSelected = selectedCount === checkboxes.length && checkboxes.length > 0;
            selectAllBtn.innerHTML = allSelected
                ? '<i class="fas fa-square"></i> Deselect All'
                : '<i class="fas fa-check-square"></i> Select All';
        }
    }


    selectAllProducts() {
        console.log('selectAllProducts called');
        
        const checkboxes = document.querySelectorAll('.product-checkbox');
        console.log(`Found ${checkboxes.length} checkboxes`);
        
        if (checkboxes.length === 0) {
            console.error('❌ No checkboxes found');
            return;
        }
        
        const allSelected = Array.from(checkboxes).every(cb => cb.checked);
        console.log(`All selected: ${allSelected}, toggling to: ${!allSelected}`);

        // Toggle all checkboxes
        checkboxes.forEach((checkbox, index) => {
            checkbox.checked = !allSelected;
            console.log(`Checkbox ${index} set to: ${checkbox.checked}`);
        });

        // Update UI
        this.handleProductSelection();
        console.log('✅ selectAllProducts completed');
}

    editSelectedProducts() {
        const checkboxes = document.querySelectorAll('.product-checkbox:checked');
        const selectedIndices = Array.from(checkboxes).map(cb =>
            parseInt(cb.closest('.product-card').dataset.productIndex)
        );

        if (selectedIndices.length === 0) {
            alert('Please select at least one product to edit.');
            return;
        }

        const selectedProducts = selectedIndices.map(index => this.currentProducts[index]);

        // Store selected products in localStorage for the edit page
        localStorage.setItem('selectedProducts', JSON.stringify(selectedProducts));

        // Open edit page
        // Also store the current task ID if available
        if (this.currentTaskId) {
            localStorage.setItem('currentTaskId', this.currentTaskId);
        }

        // Open edit page
        const url = '/edit-products';
        window.open(url, '_blank');
    }

    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    }




    async getDomainUrls() {
        const button = document.getElementById("scrapeDomain");
        try {
            const domainurlInput = document.getElementById("domainurlInput");
            const domainurl = domainurlInput.value.trim();
            if (!domainurl) {
                alert("Please enter a domain URL.");
                return;
            }

            button.disabled = true;
            button.innerHTML = "⏳ Loading...";

            console.log("Fetching domain URLs for:", domainurl);

            const response = await fetch("/api/get-domain-urls", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ base_url: domainurl }),
            });

            if (response.ok) {
                const data = await response.json();
                console.log("Domain URLs fetched:", data);
                this.urls = data.collections_with_products || [];
                this.currentPage = 1;
                this.render();
            } else {
                console.error("Failed to fetch domain URLs:", response.statusText);
            }
        } catch (error) {
            console.error("Error fetching domain URLs:", error);
        } finally {
            // Reset button state
            button.disabled = false;
            button.innerHTML = "🚀 Grab SubDomain";
        }
    }

    render() {
        if (!this.perPageSelect) {
            console.error("perPageSelect element not found in DOM");
            return;
        }

        const perPage = Number(this.perPageSelect.value);
        const total = this.urls.length;
        const totalPages = Math.ceil(total / perPage);
        const start = (this.currentPage - 1) * perPage;
        const end = start + perPage;
        const pageItems = this.urls.slice(start, end);

        // render list
        this.domainList.innerHTML = "";
        if (pageItems.length === 0) {
            this.domainList.innerHTML = "<p>No subdomains found.</p>";
        } else {
            pageItems.forEach((url) => {
                const row = document.createElement("div");
                row.classList.add("url-row");

                // button
                const btn = document.createElement("button");
                btn.classList.add("url-btn");
                btn.textContent = "🔗"; // you can use an icon or text
                btn.addEventListener("click", () => {
                    // action when button is clicked
                    this.grabProduct(url, row);
                    // alert('Grab request for: ' + url);
                    // console.log("Grab product:", url);
                    // document.getElementById('urlInput').value = url;
                    // window.open(url, "_blank");
                });

                // url text
                const span = document.createElement("span");
                span.textContent = url;
                span.classList.add("url-text");

                row.appendChild(btn);
                row.appendChild(span);
                this.domainList.appendChild(row);
            });
        }

        // render pagination
        this.pagination.innerHTML = "";
        if (totalPages > 1) {
            for (let i = 1; i <= totalPages; i++) {
                const btn = document.createElement("button");
                btn.textContent = i;
                if (i === this.currentPage) btn.classList.add("active");
                btn.addEventListener("click", () => {
                    this.currentPage = i;
                    this.render();
                });
                this.pagination.appendChild(btn);
            }
        }
    }




    grabProduct(url, rowEl) {
        // alert('Grab request for: ' + url);
        // console.log("Grab product:", url);
        document.getElementById('urlInput').value = url;
        this.startScraping();
    }

    // this.perPageSelect.addEventListener('change', () => { currentPage = 1; render(); });



}




// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    window.fashionScraper = new FashionScraper();
});
