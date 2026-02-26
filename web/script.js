// --- Dividend Radar Table Rendering ---
function renderDividendRadarTable(data) {
    const tbody = document.getElementById('dividend-radar-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12">No dividend candidates detected.</td></tr>';
        return;
    }
    data.forEach(candidate => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${candidate.symbol || ''}</td>
            <td>${candidate.company_name || ''}</td>
            <td>${candidate.ex_date || ''}</td>
            <td>${candidate.yield_percent != null ? candidate.yield_percent.toFixed(2) : ''}</td>
            <td>${candidate.roe != null ? candidate.roe.toFixed(2) : ''}</td>
            <td>${candidate.payout_ratio != null ? candidate.payout_ratio.toFixed(2) : ''}</td>
            <td>${candidate.price != null ? candidate.price.toFixed(2) : ''}</td>
            <td>${candidate.dma_20 != null ? candidate.dma_20.toFixed(2) : ''}</td>
            <td>${candidate.dma_50 != null ? candidate.dma_50.toFixed(2) : ''}</td>
            <td>${candidate.dma_200 != null ? candidate.dma_200.toFixed(2) : ''}</td>
            <td>${candidate.dividend_score != null ? candidate.dividend_score : ''}</td>
            <td>${candidate.trend || ''}</td>
        `;
        tbody.appendChild(row);
    });
}

// Example: Hook into dashboard data update (WebSocket or API)
// Replace this with your actual dashboard data update logic
function onDashboardDataUpdate(dashboardData) {
    if (dashboardData && dashboardData.dividend_radar) {
        renderDividendRadarTable(dashboardData.dividend_radar);
    }
}
// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            const offset = 80; // Account for fixed navbar
            const targetPosition = target.offsetTop - offset;
            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        }
    });
});

// Navbar scroll effect
let lastScroll = 0;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll <= 0) {
        navbar.style.boxShadow = 'none';
    } else {
        navbar.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
    }
    
    lastScroll = currentScroll;
});

// Animate elements on scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe feature cards and other elements
document.querySelectorAll('.feature-card, .workflow-step, .performance-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
});

// Add active state to navigation links
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');

window.addEventListener('scroll', () => {
    let current = '';
    
    sections.forEach(section => {
        const sectionTop = section.offsetTop;
        const sectionHeight = section.clientHeight;
        if (window.pageYOffset >= (sectionTop - 100)) {
            current = section.getAttribute('id');
        }
    });
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${current}`) {
            link.classList.add('active');
        }
    });
});

// Performance counter animation
function animateCounter(element, target, duration = 2000) {
    let start = 0;
    const increment = target / (duration / 16);
    
    const timer = setInterval(() => {
        start += increment;
        if (start >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(start);
        }
    }, 16);
}

// Trigger counter animation when stats section is visible
const statsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const statValue = entry.target.querySelector('.stat-value');
            if (statValue && !statValue.classList.contains('animated')) {
                statValue.classList.add('animated');
                // Add animation logic here if needed
            }
        }
    });
}, { threshold: 0.5 });

document.querySelectorAll('.stat').forEach(stat => {
    statsObserver.observe(stat);
});
