// INKBIT LMS - Global Frontend Controller

document.addEventListener('DOMContentLoaded', () => {
    // 1. Theme Toggle System
    const themeToggleBtns = document.querySelectorAll('.theme-toggle');
    const getSavedTheme = () => localStorage.getItem('theme') || 'dark';
    
    // Apply saved theme
    document.documentElement.setAttribute('data-theme', getSavedTheme());
    
    const updateThemeIcons = (theme) => {
        themeToggleBtns.forEach(btn => {
            if (theme === 'light') {
                btn.innerHTML = `
                    <svg class="feather" viewBox="0 0 24 24" style="width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 2;">
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                    </svg>
                `; // moon icon when in light theme
            } else {
                btn.innerHTML = `
                    <svg class="feather" viewBox="0 0 24 24" style="width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 2;">
                        <circle cx="12" cy="12" r="5"></circle>
                        <line x1="12" y1="1" x2="12" y2="3"></line>
                        <line x1="12" y1="21" x2="12" y2="23"></line>
                        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                        <line x1="1" y1="12" x2="3" y2="12"></line>
                        <line x1="21" y1="12" x2="23" y2="12"></line>
                        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                    </svg>
                `; // sun icon when in dark theme
            }
        });
    };
    
    updateThemeIcons(getSavedTheme());

    themeToggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcons(newTheme);
        });
    });

    // 1b. Mobile Navigation Drawer Toggle
    const sidebar = document.querySelector('.app-sidebar');
    const menuToggleBtn = document.querySelector('#mobile-menu-toggle-btn');
    const overlay = document.querySelector('#sidebar-overlay-layer');
    
    const toggleSidebar = () => {
        if (sidebar && overlay) {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        }
    };
    
    if (menuToggleBtn) {
        menuToggleBtn.addEventListener('click', toggleSidebar);
    }
    if (overlay) {
        overlay.addEventListener('click', toggleSidebar);
    }
    
    // Auto-close sidebar on sidebar link click on mobile
    const sidebarLinks = document.querySelectorAll('.app-sidebar a, .app-sidebar button');
    sidebarLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (sidebar && sidebar.classList.contains('open')) {
                toggleSidebar();
            }
        });
    });

    // 2. Tab Control System
    const setupTabs = () => {
        const tabButtons = document.querySelectorAll('.tab-btn');
        tabButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetId = btn.getAttribute('data-tab');
                if (!targetId) return;

                // Find tab siblings
                const parent = btn.closest('.tabs-container') || document;
                const siblingsButtons = parent.querySelectorAll('.tab-btn');
                const siblingContents = parent.querySelectorAll('.tab-content');

                // Toggle buttons
                siblingsButtons.forEach(sBtn => sBtn.classList.remove('active'));
                btn.classList.add('active');

                // Toggle content panels
                siblingContents.forEach(content => {
                    if (content.id === targetId) {
                        content.classList.add('active');
                    } else {
                        content.classList.remove('active');
                    }
                });
            });
        });
    };
    setupTabs();

    // 3. Modal Overlays System
    window.openModal = (modalId) => {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden'; // Stop body scrolling
        }
    };

    window.closeModal = (modalId) => {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    };

    // Close modal if user clicks background overlay
    document.querySelectorAll('.modal-overlay').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal.id);
            }
        });
    });

    // 4. Automatically Clear Flash Alerts
    document.querySelectorAll('.flash-messages .alert').forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(100px)';
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    });

    // 5. Auth Credentials Injector for Quick Seeding login (Teacher/Student mock helper)
    window.injectCredentials = (email, password) => {
        const emailInput = document.getElementById('login-email');
        const passInput = document.getElementById('login-password');
        if (emailInput && passInput) {
            emailInput.value = email;
            passInput.value = password;
        }
    };

    // 6. Dynamic Calendar System
    const calendarContainer = document.getElementById('dynamic-calendar');
    if (calendarContainer) {
        initCalendar(calendarContainer);
    }

    function initCalendar(container) {
        // Today is June 23, 2026 as per local time context
        let currentDate = new Date(2026, 5, 23); // June is month index 5
        let displayDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
        let eventsData = {};

        // Render base elements inside container
        container.innerHTML = `
            <div class="calendar-widget">
                <div class="calendar-nav-row">
                    <button class="calendar-nav-btn" id="cal-prev" type="button">
                        <svg class="feather" style="width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 2.5;" viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"></polyline></svg>
                    </button>
                    <span class="calendar-nav-title" id="cal-title"></span>
                    <button class="calendar-nav-btn" id="cal-next" type="button">
                        <svg class="feather" style="width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 2.5;" viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"></polyline></svg>
                    </button>
                </div>
                <div class="calendar-header-row">
                    <span>Su</span><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span>
                </div>
                <div class="calendar-days-grid" id="cal-days"></div>
            </div>
        `;

        const prevBtn = container.querySelector('#cal-prev');
        const nextBtn = container.querySelector('#cal-next');
        const titleEl = container.querySelector('#cal-title');
        const daysGrid = container.querySelector('#cal-days');

        // Fetch calendar events from API
        fetch('/api/calendar-events')
            .then(res => res.json())
            .then(data => {
                // Pre-index events by YYYY-MM-DD to avoid O(N*C) calculations during render
                eventsData = {};
                data.forEach(event => {
                    if (event.start) {
                        const eventDate = new Date(event.start);
                        const evStr = eventDate.getFullYear() + '-' + 
                            String(eventDate.getMonth() + 1).padStart(2, '0') + '-' + 
                            String(eventDate.getDate()).padStart(2, '0');
                        if (!eventsData[evStr]) {
                            eventsData[evStr] = [];
                        }
                        eventsData[evStr].push(event);
                    }
                });
                render();
            })
            .catch(err => {
                console.error("Error loading calendar events:", err);
                render(); // Render empty calendar if fetch fails
            });

        prevBtn.addEventListener('click', () => {
            displayDate.setMonth(displayDate.getMonth() - 1);
            render();
        });

        nextBtn.addEventListener('click', () => {
            displayDate.setMonth(displayDate.getMonth() + 1);
            render();
        });

        function render() {
            const year = displayDate.getFullYear();
            const month = displayDate.getMonth();

            const monthNames = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ];
            titleEl.textContent = `${monthNames[month]} ${year}`;

            // Clear days grid
            daysGrid.innerHTML = '';

            // Calculate days:
            // First day of month's weekday
            const firstDayOfWeek = new Date(year, month, 1).getDay();
            // Total days in month
            const totalDays = new Date(year, month + 1, 0).getDate();
            // Total days in previous month
            const prevTotalDays = new Date(year, month, 0).getDate();

            // 1. Previous month offsets
            for (let i = firstDayOfWeek - 1; i >= 0; i--) {
                const dayNum = prevTotalDays - i;
                const cell = createDayCell(dayNum, true, new Date(year, month - 1, dayNum));
                daysGrid.appendChild(cell);
            }

            // 2. Current month days
            for (let day = 1; day <= totalDays; day++) {
                const cell = createDayCell(day, false, new Date(year, month, day));
                daysGrid.appendChild(cell);
            }

            // 3. Next month offsets to fill grid to multiple of 7
            const totalCells = daysGrid.children.length;
            const remaining = (7 - (totalCells % 7)) % 7;
            for (let day = 1; day <= remaining; day++) {
                const cell = createDayCell(day, true, new Date(year, month + 1, day));
                daysGrid.appendChild(cell);
            }
        }

        function createDayCell(dayNum, isOtherMonth, cellDate) {
            const cell = document.createElement('div');
            cell.className = 'calendar-day-cell';
            if (isOtherMonth) {
                cell.className += ' other-month';
            }

            // Add text element for date number
            const numSpan = document.createElement('span');
            numSpan.textContent = dayNum;
            cell.appendChild(numSpan);

            // Set up date key for event lookup
            const dateStr = cellDate.getFullYear() + '-' + 
                String(cellDate.getMonth() + 1).padStart(2, '0') + '-' + 
                String(cellDate.getDate()).padStart(2, '0');

            // Check if cell represents today (June 23, 2026)
            const isToday = cellDate.getFullYear() === currentDate.getFullYear() &&
                            cellDate.getMonth() === currentDate.getMonth() &&
                            cellDate.getDate() === currentDate.getDate();
            if (isToday) {
                cell.className += ' today';
            }

            // Find events for this specific date (O(1) lookup)
            const dayEvents = eventsData[dateStr] || [];

            // If there are events, render dots below
            if (dayEvents.length > 0) {
                const dotsContainer = document.createElement('div');
                dotsContainer.className = 'calendar-dots';

                // Categorize events to prevent duplicate dots for same type
                const types = new Set(dayEvents.map(e => e.type));
                types.forEach(type => {
                    const dot = document.createElement('span');
                    dot.className = `calendar-dot ${type}`;
                    dotsContainer.appendChild(dot);
                });
                cell.appendChild(dotsContainer);
            }

            // Handle date click
            cell.addEventListener('click', () => {
                // Remove selected class from all other cells
                container.querySelectorAll('.calendar-day-cell').forEach(c => c.classList.remove('selected'));
                cell.classList.add('selected');

                openDayTimetable(cellDate, dayEvents);
            });

            return cell;
        }

        function openDayTimetable(date, events) {
            const modal = document.getElementById('timetable-modal');
            if (!modal) return;

            const dateTitle = document.getElementById('timetable-modal-date');
            const classesList = document.getElementById('timetable-classes-list');
            const deadlinesList = document.getElementById('timetable-deadlines-list');
            const classesSection = document.getElementById('timetable-classes-section');
            const deadlinesSection = document.getElementById('timetable-deadlines-section');
            const emptyState = document.getElementById('timetable-empty-state');

            // Format title date nicely (e.g., Tuesday, June 23, 2026)
            const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            dateTitle.textContent = date.toLocaleDateString('en-US', options);

            // Filter classes vs tasks
            const classes = events.filter(e => e.type === 'class');
            const deadlines = events.filter(e => e.type === 'assignment' || e.type === 'quiz');

            // Render live classes list
            classesList.innerHTML = '';
            if (classes.length > 0) {
                classesSection.style.display = 'block';
                classes.forEach(cls => {
                    // Extract hours/minutes if available
                    const dt = new Date(cls.start);
                    const timeStr = String(dt.getHours()).padStart(2, '0') + ':' + String(dt.getMinutes()).padStart(2, '0');
                    
                    const card = document.createElement('div');
                    card.className = 'timetable-card';
                    card.innerHTML = `
                        <div class="timetable-info">
                            <span class="timetable-course">${cls.course_name}</span>
                            <span class="timetable-title">${cls.title}</span>
                            <span class="timetable-time">🕒 Scheduled at ${timeStr}</span>
                        </div>
                        <a href="${cls.link}" target="_blank" class="btn btn-primary timetable-badge class" style="text-decoration: none; padding: 0.4rem 0.8rem; border-radius: 8px;">Join</a>
                    `;
                    classesList.appendChild(card);
                });
            } else {
                classesSection.style.display = 'none';
            }

            // Render deadlines list
            deadlinesList.innerHTML = '';
            if (deadlines.length > 0) {
                deadlinesSection.style.display = 'block';
                deadlines.forEach(dl => {
                    const dt = new Date(dl.start);
                    const timeStr = String(dt.getHours()).padStart(2, '0') + ':' + String(dt.getMinutes()).padStart(2, '0');
                    const badgeText = dl.type === 'quiz' ? 'Quiz' : 'Assignment';
                    const detailText = dl.type === 'assignment' ? `Points: ${dl.points || 100}` : 'Standard Assessment';
                    
                    const card = document.createElement('div');
                    card.className = 'timetable-card';
                    card.innerHTML = `
                        <div class="timetable-info">
                            <span class="timetable-course">${dl.course_name}</span>
                            <span class="timetable-title">${dl.title}</span>
                            <span class="timetable-time">⚠️ Due by ${timeStr} (${detailText})</span>
                        </div>
                        <span class="timetable-badge ${dl.type}">${badgeText}</span>
                    `;
                    deadlinesList.appendChild(card);
                });
            } else {
                deadlinesSection.style.display = 'none';
            }

            // Toggle empty state if zero total events
            if (events.length === 0) {
                emptyState.style.display = 'block';
            } else {
                emptyState.style.display = 'none';
            }

            openModal('timetable-modal');
        }
    }

    // 7. Sidebar Link Workability System
    const setupSidebarLinks = () => {
        const sidebarLinks = document.querySelectorAll('.sidebar-link');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                const label = link.textContent.trim().toLowerCase();
                
                // standard links shouldn't be overridden
                if (link.getAttribute('href') && link.getAttribute('href') !== '#' && !link.getAttribute('href').startsWith('#')) {
                    return;
                }

                const isHomepage = window.location.pathname === '/' || window.location.pathname === '';
                
                const handleLinkAction = (targetId, fallbackUrl) => {
                    if (isHomepage && document.getElementById(targetId)) {
                        e.preventDefault();
                        smoothScrollTo(targetId);
                    } else {
                        window.location.href = fallbackUrl || `/#${targetId}`;
                    }
                };

                // 1. MESSAGES - triggers AI Chat Panel
                if (label.includes('messages')) {
                    e.preventDefault();
                    const aiChatToggle = document.getElementById('ai-chat-toggle');
                    const aiChatPanel = document.getElementById('ai-chat-panel');
                    const aiChatInput = document.getElementById('ai-chat-input');
                    if (aiChatPanel) {
                        aiChatPanel.style.display = aiChatPanel.style.display === 'none' ? 'flex' : 'none';
                        if (aiChatPanel.style.display === 'flex' && aiChatInput) {
                            aiChatInput.focus();
                        }
                    } else {
                        window.location.href = '/';
                    }
                    return;
                }

                // 2. NOTIFICATIONS - triggers notifications modal
                if (label.includes('notifications')) {
                    e.preventDefault();
                    openModal('notifications-modal');
                    return;
                }

                // 3. GRADES - triggers grades modal or deadlines section
                if (label.includes('grades')) {
                    e.preventDefault();
                    const gradesModal = document.getElementById('grades-modal');
                    if (gradesModal) {
                        openModal('grades-modal');
                    } else {
                        handleLinkAction('deadlines-section');
                    }
                    return;
                }

                // 4. RESOURCES - triggers resources modal
                if (label.includes('resources')) {
                    e.preventDefault();
                    openModal('resources-modal');
                    return;
                }

                // 5. FINANCIALS - triggers financials modal
                if (label.includes('financials')) {
                    e.preventDefault();
                    openModal('financials-modal');
                    return;
                }

                // 6. MY COURSES / ACTIVE COURSES / ACTIVE ROOMS
                if (label.includes('courses') || label.includes('rooms') || label.includes('classroom')) {
                    handleLinkAction('courses-section');
                    return;
                }

                // 7. ASSIGNMENTS / QUIZZES
                if (label.includes('assignments') || label.includes('quizzes')) {
                    if (label.includes('quizzes') && window.location.pathname !== '/self-learning') {
                        window.location.href = '/self-learning';
                    } else {
                        handleLinkAction('deadlines-section');
                    }
                    return;
                }

                // 8. LIVE CLASSES / STUDENTS / TUTORS / ATTENDANCE
                if (label.includes('live classes') || label.includes('classes') || label.includes('tutors') || label.includes('students') || label.includes('attendance')) {
                    if (label.includes('tutors')) {
                        handleLinkAction('tutors-section');
                    } else if (label.includes('students') || label.includes('attendance')) {
                        handleLinkAction('students-section');
                    } else {
                        handleLinkAction('classes-section');
                    }
                    return;
                }

                // 9. ANALYTICS / REPORTS
                if (label.includes('analytics') || label.includes('reports')) {
                    handleLinkAction('analytics-section');
                    return;
                }

                // 10. CALENDAR
                if (label.includes('calendar')) {
                    e.preventDefault();
                    const calendarCard = document.querySelector('#dynamic-calendar');
                    if (calendarCard) {
                        const cardWrapper = calendarCard.closest('.sidebar-card') || calendarCard;
                        cardWrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        cardWrapper.classList.add('calendar-pulse');
                        setTimeout(() => cardWrapper.classList.remove('calendar-pulse'), 2500);
                    } else {
                        window.location.href = '/#dynamic-calendar';
                    }
                    return;
                }
            });
        });
    };

    window.smoothScrollTo = (id) => {
        const el = document.getElementById(id);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.style.transition = 'box-shadow 0.5s ease, border-color 0.5s ease';
            const originalShadow = el.style.boxShadow;
            const originalBorder = el.style.borderColor;
            
            // Highlight target widget temporarily
            el.style.boxShadow = '0 0 20px var(--primary-glow)';
            el.style.borderColor = 'var(--primary)';
            setTimeout(() => {
                el.style.boxShadow = originalShadow;
                el.style.borderColor = originalBorder;
            }, 2000);
        }
    };

    window.showToast = (message, type = 'success') => {
        let container = document.querySelector('.flash-messages');
        if (!container) {
            container = document.createElement('div');
            container.className = 'flash-messages';
            document.body.appendChild(container);
        }
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type === 'error' ? 'danger' : type}`;
        
        let iconSvg = '';
        if (type === 'success') {
            iconSvg = `<svg class="feather" viewBox="0 0 24 24" style="width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
        } else {
            iconSvg = `<svg class="feather" viewBox="0 0 24 24" style="width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
        }
        
        alert.innerHTML = `
            ${iconSvg}
            <span>${message}</span>
        `;
        
        container.appendChild(alert);
        
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(100px)';
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    };

    setupSidebarLinks();
});

