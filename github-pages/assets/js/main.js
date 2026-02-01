// WhatThePatch Documentation - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {

    // ==================== Copy to Clipboard ====================

    document.querySelectorAll('.code-block').forEach(block => {
        const copyBtn = block.querySelector('.copy-btn');
        const codeContent = block.querySelector('.code-content');

        if (copyBtn && codeContent) {
            copyBtn.addEventListener('click', async () => {
                const text = codeContent.textContent.trim();

                try {
                    await navigator.clipboard.writeText(text);
                    copyBtn.textContent = 'Copied!';
                    copyBtn.classList.add('copied');

                    setTimeout(() => {
                        copyBtn.textContent = 'Copy';
                        copyBtn.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy:', err);
                }
            });
        }
    });

    // ==================== Sidebar Toggle ====================

    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');

    if (sidebarToggle && sidebar && mainContent) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            mainContent.classList.toggle('expanded');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 900 &&
                !sidebar.classList.contains('collapsed') &&
                !sidebar.contains(e.target) &&
                !sidebarToggle.contains(e.target)) {
                sidebar.classList.add('collapsed');
                mainContent.classList.add('expanded');
            }
        });
    }

    // ==================== Scroll to Top ====================

    const scrollTopBtn = document.querySelector('.scroll-top');

    if (scrollTopBtn) {
        // Show/hide button based on scroll position
        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                scrollTopBtn.classList.add('visible');
            } else {
                scrollTopBtn.classList.remove('visible');
            }
        });

        // Scroll to top on click
        scrollTopBtn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // ==================== Active Page Highlighting ====================

    const currentPage = window.location.pathname.split('/').pop() || 'index.html';

    document.querySelectorAll('.nav-item').forEach(link => {
        const href = link.getAttribute('href');
        // Skip external links
        if (href && href.startsWith('http')) return;

        if (href === currentPage ||
            (currentPage === '' && href === 'index.html') ||
            (currentPage === 'whatthepatch' && href === 'index.html') ||
            (currentPage === 'whatthepatch/' && href === 'index.html')) {
            link.classList.add('active');
        }
    });

    // ==================== Smooth Scroll for Anchors ====================

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') return;

            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

});
