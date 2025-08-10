// NLWeb Search Results Page
class NLWebSearchResults {
    constructor() {
        this.searchForm = document.getElementById('search-form');
        this.searchInput = document.getElementById('search-input');
        this.searchQueryDisplay = document.getElementById('search-query');
        this.resultsContainer = document.getElementById('search-results');
        this.loadingState = document.getElementById('loading-state');
        this.errorState = document.getElementById('error-state');
        this.noResultsState = document.getElementById('no-results');
        this.filterButtons = document.querySelectorAll('.filter-button');
        this.sortSelect = document.getElementById('sort-select');
        
        this.allResults = [];
        this.filteredResults = [];
        this.currentFilter = 'all';
        this.site = 'bon_appetit';
        
        this.init();
    }
    
    init() {
        // Get query from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('q') || '';
        
        if (query) {
            this.searchInput.value = query;
            this.searchQueryDisplay.textContent = query;
            this.performSearch(query);
        }
        
        // Set up event listeners
        this.searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const query = this.searchInput.value.trim();
            if (query) {
                // Update URL
                const newUrl = `${window.location.pathname}?q=${encodeURIComponent(query)}`;
                window.history.pushState({}, '', newUrl);
                
                this.searchQueryDisplay.textContent = query;
                this.performSearch(query);
            }
        });
        
        this.filterButtons.forEach(button => {
            button.addEventListener('click', () => {
                this.currentFilter = button.dataset.type;
                this.filterButtons.forEach(b => b.classList.remove('active'));
                button.classList.add('active');
                this.filterAndDisplayResults();
            });
        });
        
        this.sortSelect.addEventListener('change', () => {
            this.sortResults();
            this.displayResults();
        });
    }
    
    async performSearch(query) {
        // Show loading state
        this.showLoadingState();
        
        try {
            // Build URL with parameters
            const params = new URLSearchParams({
                query: query,
                generate_mode: 'list',
                display_mode: 'full',
                site: this.site
            });
            
            const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
            const url = `${baseUrl}/ask?${params.toString()}`;
            
            // Use EventSource for streaming
            const eventSource = new EventSource(url);
            let accumulatedResults = [];
            
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'result') {
                        accumulatedResults.push(data.data);
                    } else if (data.type === 'end') {
                        eventSource.close();
                        this.processResults(accumulatedResults);
                    }
                } catch (e) {
                }
            };
            
            eventSource.onerror = (error) => {
                eventSource.close();
                this.showErrorState();
            };
            
        } catch (error) {
            this.showErrorState();
        }
    }
    
    processResults(results) {
        this.allResults = results;
        this.updateResultCounts();
        this.filterAndDisplayResults();
    }
    
    updateResultCounts() {
        const counts = {
            all: this.allResults.length,
            Recipe: 0,
            Article: 0
        };
        
        this.allResults.forEach(result => {
            const type = result['@type'] || 'Article';
            if (counts[type] !== undefined) {
                counts[type]++;
            }
        });
        
        // Update filter button counts
        this.filterButtons.forEach(button => {
            const type = button.dataset.type;
            const countSpan = button.querySelector('.count');
            countSpan.textContent = counts[type] || 0;
        });
    }
    
    filterAndDisplayResults() {
        if (this.currentFilter === 'all') {
            this.filteredResults = [...this.allResults];
        } else {
            this.filteredResults = this.allResults.filter(result => 
                (result['@type'] || 'Article') === this.currentFilter
            );
        }
        
        this.sortResults();
        this.displayResults();
    }
    
    sortResults() {
        const sortBy = this.sortSelect.value;
        
        switch (sortBy) {
            case 'date':
                this.filteredResults.sort((a, b) => {
                    const dateA = new Date(a.datePublished || '1970-01-01');
                    const dateB = new Date(b.datePublished || '1970-01-01');
                    return dateB - dateA;
                });
                break;
            case 'rating':
                this.filteredResults.sort((a, b) => {
                    const ratingA = a.aggregateRating?.ratingValue || 0;
                    const ratingB = b.aggregateRating?.ratingValue || 0;
                    return ratingB - ratingA;
                });
                break;
            // 'relevance' is default, no sorting needed
        }
    }
    
    displayResults() {
        if (this.filteredResults.length === 0) {
            this.showNoResultsState();
            return;
        }
        
        // Hide loading and error states
        this.loadingState.style.display = 'none';
        this.errorState.style.display = 'none';
        this.noResultsState.style.display = 'none';
        this.resultsContainer.style.display = 'grid';
        
        // Clear existing results
        this.resultsContainer.innerHTML = '';
        
        // Display each result
        this.filteredResults.forEach(result => {
            const card = this.createResultCard(result);
            this.resultsContainer.appendChild(card);
        });
    }
    
    createResultCard(result) {
        const card = document.createElement('article');
        card.className = 'result-card';
        
        const type = result['@type'] || 'Article';
        const title = result.name || result.headline || 'Untitled';
        const description = result.description || '';
        const image = this.getImageUrl(result);
        const url = result.url || '#';
        const category = result.recipeCategory || result.articleSection || '';
        const rating = result.aggregateRating?.ratingValue || 0;
        const cookTime = result.totalTime || '';
        
        card.innerHTML = `
            <a href="${url}" target="_blank">
                <div class="result-image-wrapper">
                    ${image ? `<img src="${image}" alt="${title}" class="result-image">` : ''}
                    <span class="result-type-badge">${type}</span>
                </div>
                <div class="result-content">
                    ${category ? `<div class="result-category">${category}</div>` : ''}
                    <h3 class="result-title">${title}</h3>
                    ${description ? `<p class="result-description">${description}</p>` : ''}
                    <div class="result-meta">
                        ${rating > 0 ? this.createRatingStars(rating) : ''}
                        ${cookTime ? `<span class="cook-time">${this.formatCookTime(cookTime)}</span>` : ''}
                    </div>
                </div>
            </a>
        `;
        
        return card;
    }
    
    getImageUrl(result) {
        if (result.image) {
            if (typeof result.image === 'string') {
                return result.image;
            } else if (result.image.url) {
                return result.image.url;
            } else if (Array.isArray(result.image) && result.image.length > 0) {
                return typeof result.image[0] === 'string' ? result.image[0] : result.image[0].url;
            }
        }
        return null;
    }
    
    createRatingStars(rating) {
        const fullStars = Math.floor(rating);
        const hasHalfStar = rating % 1 >= 0.5;
        
        let stars = `<div class="result-rating">`;
        
        for (let i = 0; i < 5; i++) {
            if (i < fullStars) {
                stars += `<svg class="star" viewBox="0 0 16 16"><path d="M8 0l2.5 5.3 5.5.8-4 4.1.9 5.8L8 13.3 3.1 16l.9-5.8L0 6.1l5.5-.8z"/></svg>`;
            } else if (i === fullStars && hasHalfStar) {
                stars += `<svg class="star" viewBox="0 0 16 16"><path d="M8 0l2.5 5.3 5.5.8-4 4.1.9 5.8L8 13.3V0z" opacity="0.3"/><path d="M8 0l2.5 5.3 5.5.8-4 4.1.9 5.8L8 13.3z"/></svg>`;
            } else {
                stars += `<svg class="star" viewBox="0 0 16 16"><path d="M8 0l2.5 5.3 5.5.8-4 4.1.9 5.8L8 13.3 3.1 16l.9-5.8L0 6.1l5.5-.8z" opacity="0.3"/></svg>`;
            }
        }
        
        stars += `<span>(${rating})</span></div>`;
        return stars;
    }
    
    formatCookTime(duration) {
        // Convert ISO 8601 duration to readable format
        const match = duration.match(/PT(?:(\d+)H)?(?:(\d+)M)?/);
        if (match) {
            const hours = match[1] ? parseInt(match[1]) : 0;
            const minutes = match[2] ? parseInt(match[2]) : 0;
            
            if (hours && minutes) {
                return `${hours}h ${minutes}m`;
            } else if (hours) {
                return `${hours} hour${hours > 1 ? 's' : ''}`;
            } else if (minutes) {
                return `${minutes} min`;
            }
        }
        return duration;
    }
    
    showLoadingState() {
        this.loadingState.style.display = 'block';
        this.errorState.style.display = 'none';
        this.noResultsState.style.display = 'none';
        this.resultsContainer.style.display = 'none';
    }
    
    showErrorState() {
        this.loadingState.style.display = 'none';
        this.errorState.style.display = 'block';
        this.noResultsState.style.display = 'none';
        this.resultsContainer.style.display = 'none';
    }
    
    showNoResultsState() {
        this.loadingState.style.display = 'none';
        this.errorState.style.display = 'none';
        this.noResultsState.style.display = 'block';
        this.resultsContainer.style.display = 'none';
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new NLWebSearchResults();
});
