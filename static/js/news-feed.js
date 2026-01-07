/**
 * News Feed JavaScript Component
 * Loads and renders media mentions from JSON data
 * Used by media page to display cards with search/filter capabilities
 */

class NewsFeed {
  constructor(config) {
    this.config = config;
    this.allStories = [];
    this.filteredStories = [];
    this.currentPage = 1;
    this.cardsPerPage = config.cardsPerPage || 12;
    this.filterField = config.filterField || 'mention_type';
    this.filterTypes = config.filterTypes || [];
    this.dateField = config.dateField || 'date';
    this.renderCard = config.renderCard || this.defaultRenderCard;
    this.hasFeatured = config.hasFeatured !== false;
    
    this.init();
  }

  async init() {
    try {
      // Load JSON data
      const response = await fetch(this.config.jsonPath);
      if (!response.ok) {
        throw new Error(`Failed to load ${this.config.jsonPath}: ${response.statusText}`);
      }
      
      const data = await response.json();
      this.allStories = data.stories || [];
      
      if (this.allStories.length === 0) {
        this.showNoStories();
        return;
      }
      
      // Sort by date (newest first)
      this.allStories.sort((a, b) => {
        const dateA = new Date(a[this.dateField]);
        const dateB = new Date(b[this.dateField]);
        return dateB - dateA;
      });
      
      // Initial render
      this.filteredStories = [...this.allStories];
      this.render();
      
    } catch (error) {
      console.error('Error loading news feed:', error);
      this.showError(error.message);
    }
  }

  render() {
    const container = document.getElementById(this.config.containerId);
    if (!container) {
      console.error(`Container ${this.config.containerId} not found`);
      return;
    }

    // Separate featured and regular stories
    const featured = this.filteredStories.filter(s => s.featured);
    const regular = this.filteredStories.filter(s => !s.featured);

    let html = '';

    // Featured section
    if (this.hasFeatured && featured.length > 0) {
      html += '<div class="featured-section">';
      html += '<div class="featured-header">';
      html += '<span class="featured-icon">★</span>';
      html += '<h3>Featured Coverage</h3>';
      html += '</div>';
      html += '<div class="news-grid">';
      featured.forEach(story => {
        html += this.renderCard(story, true);
      });
      html += '</div>';
      html += '</div>';
    }

    // Stats bar
    html += '<div class="news-controls">';
    html += `<div class="news-stats">${this.filteredStories.length} stories found</div>`;
    
    if (this.filterTypes.length > 0) {
      html += '<div class="news-filters">';
      html += '<button class="filter-btn active" data-filter="all">All</button>';
      this.filterTypes.forEach(type => {
        html += `<button class="filter-btn" data-filter="${type}">${this.capitalize(type)}</button>`;
      });
      html += '</div>';
    }
    html += '</div>';

    // Regular stories grid
    const startIdx = (this.currentPage - 1) * this.cardsPerPage;
    const endIdx = startIdx + this.cardsPerPage;
    const paginated = regular.slice(startIdx, endIdx);

    html += '<div class="news-grid" role="list">';
    if (paginated.length > 0) {
      paginated.forEach(story => {
        html += this.renderCard(story, false);
      });
    } else if (regular.length === 0 && featured.length === 0) {
      html += '<div class="no-stories">No stories found</div>';
    }
    html += '</div>';

    // Pagination
    const totalPages = Math.ceil(regular.length / this.cardsPerPage);
    if (totalPages > 1) {
      html += this.renderPagination(totalPages);
    }

    container.innerHTML = html;

    // Attach event listeners
    this.attachEventListeners(regular.length);
  }

  renderPagination(totalPages) {
    let html = '<div class="pagination">';
    
    // Previous button
    html += `<button class="pagination-btn" ${this.currentPage === 1 ? 'disabled' : ''} 
             onclick="window.newsFeed.previousPage()">← Previous</button>`;

    // Page buttons
    for (let i = 1; i <= Math.min(totalPages, 7); i++) {
      const isActive = i === this.currentPage;
      html += `<button class="pagination-btn ${isActive ? 'active' : ''}" 
               onclick="window.newsFeed.goToPage(${i})">${i}</button>`;
    }

    if (totalPages > 7) {
      html += '<span class="pagination-info">...</span>';
      html += `<button class="pagination-btn" onclick="window.newsFeed.goToPage(${totalPages})">${totalPages}</button>`;
    }

    // Page info
    html += `<span class="pagination-info">Page ${this.currentPage} of ${totalPages}</span>`;

    // Next button
    html += `<button class="pagination-btn" ${this.currentPage === totalPages ? 'disabled' : ''} 
             onclick="window.newsFeed.nextPage()">Next →</button>`;

    html += '</div>';
    return html;
  }

  attachEventListeners(regularCount) {
    // Filter buttons
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const filter = e.target.getAttribute('data-filter');
        this.applyFilter(filter);
      });
    });
  }

  applyFilter(filterValue) {
    const featured = this.allStories.filter(s => s.featured);
    
    if (filterValue === 'all') {
      this.filteredStories = [...this.allStories];
    } else {
      this.filteredStories = this.allStories.filter(story => {
        const fieldValue = story[this.filterField];
        return fieldValue === filterValue;
      });
    }

    this.currentPage = 1;
    this.render();

    // Update active button
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    event.target.classList.add('active');
  }

  goToPage(pageNum) {
    this.currentPage = pageNum;
    this.render();
  }

  nextPage() {
    const totalPages = Math.ceil(this.filteredStories.length / this.cardsPerPage);
    if (this.currentPage < totalPages) {
      this.currentPage++;
      this.render();
    }
  }

  previousPage() {
    if (this.currentPage > 1) {
      this.currentPage--;
      this.render();
    }
  }

  showNoStories() {
    const container = document.getElementById(this.config.containerId);
    container.innerHTML = '<div class="no-stories">No media mentions found.</div>';
  }

  showError(message) {
    const container = document.getElementById(this.config.containerId);
    container.innerHTML = `<div class="no-stories">Error loading media feed: ${message}</div>`;
  }

  capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  defaultRenderCard(story) {
    return `
      <article class="news-card" role="listitem" tabindex="0">
        <div class="card-header">
          <div class="card-source">${story.source || 'Unknown'}</div>
        </div>
        <div class="card-body">
          <h3 class="card-title">${story.title}</h3>
          <p class="card-summary">${story.summary || ''}</p>
        </div>
        <div class="card-footer">
          <span class="card-date">${story.date}</span>
          <a href="${story.url}" target="_blank" rel="noopener">Read More →</a>
        </div>
      </article>
    `;
  }
}

// Make globally available
window.NewsFeed = NewsFeed;
window.newsFeed = null;

// Initialize on page load if data is present
document.addEventListener('DOMContentLoaded', function() {
  // This will be called by the inline script in media_index.md
  // which instantiates NewsFeed with proper configuration
});
