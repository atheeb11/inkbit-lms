// INKBIT LMS - Quiz Runner Controller

document.addEventListener('DOMContentLoaded', () => {
    const slides = document.querySelectorAll('.question-slide');
    if (slides.length === 0) return;

    let currentStep = 0;
    const totalQuestions = slides.length;
    const prevBtn = document.getElementById('prev-question-btn');
    const nextBtn = document.getElementById('next-question-btn');
    const timerDisplay = document.getElementById('timer-count');
    const form = document.getElementById('quiz-submit-form');
    const answersInput = document.getElementById('quiz-answers-input');
    const navBadgeContainer = document.getElementById('nav-badge-container');
    
    // Modal elements
    const submitModal = document.getElementById('submit-confirm-modal');
    const triggerSubmitBtn = document.getElementById('trigger-submit-modal');
    const cancelModalBtn = document.getElementById('modal-cancel-btn');
    const confirmModalBtn = document.getElementById('modal-confirm-btn');

    // Selected answers store: {question_id: choice}
    const userAnswers = {};
    
    // Flagged questions store: {question_id: boolean}
    const flaggedQuestions = {};

    // 1. Build Navigation sidebar badges dynamically
    buildNavigationGrid();
    
    // Initialize first question
    showSlide(currentStep);

    // 2. Timer Setup (Default 5 minutes = 300 seconds)
    const timerBar = document.getElementById('quiz-timer-bar');
    let timeLeft = parseInt(timerBar?.getAttribute('data-duration') || '300');
    let timerInterval;

    if (timerDisplay) {
        startTimer();
    }

    // 3. Set up option clicks and keyboard shortcuts
    slides.forEach((slide, slideIndex) => {
        const questionId = slide.getAttribute('data-question-id');
        const options = slide.querySelectorAll('.quiz-option-card');
        
        options.forEach(option => {
            option.addEventListener('click', () => {
                selectOption(slideIndex, questionId, option, options);
            });
        });

        // Flag toggle click
        const flagBtn = slide.querySelector('.flag-toggle-btn');
        if (flagBtn) {
            flagBtn.addEventListener('click', () => {
                toggleFlag(questionId, flagBtn);
            });
        }
    });

    // Keyboard Shortcuts
    document.addEventListener('keydown', (e) => {
        // Prevent key triggers if user is typing in inputs or modal is open
        if (submitModal && submitModal.classList.contains('show')) return;
        
        const activeSlide = slides[currentStep];
        const questionId = activeSlide.getAttribute('data-question-id');
        const options = activeSlide.querySelectorAll('.quiz-option-card');
        
        const key = e.key.toUpperCase();
        
        // Option selection shortcuts: A, B, C, D
        if (['A', 'B', 'C', 'D'].includes(key)) {
            const targetOption = activeSlide.querySelector(`.quiz-option-card[data-choice="${key}"]`);
            if (targetOption) {
                selectOption(currentStep, questionId, targetOption, options);
            }
        }
        
        // Nav shortcuts: ArrowLeft (Previous), ArrowRight (Next)
        if (e.key === 'ArrowLeft') {
            if (currentStep > 0) {
                currentStep--;
                showSlide(currentStep);
            }
        } else if (e.key === 'ArrowRight') {
            if (currentStep < totalQuestions - 1) {
                currentStep++;
                showSlide(currentStep);
            }
        } else if (key === 'F') {
            // Flag shortcut
            const flagBtn = activeSlide.querySelector('.flag-toggle-btn');
            if (flagBtn) toggleFlag(questionId, flagBtn);
        }
    });

    function selectOption(slideIndex, questionId, option, options) {
        // Clear selection in this slide
        options.forEach(o => o.classList.remove('selected'));
        
        // Select clicked option
        option.classList.add('selected');
        const choice = option.getAttribute('data-choice');
        userAnswers[questionId] = choice;
        
        // Update hidden input
        answersInput.value = JSON.stringify(userAnswers);
        
        // Update navigation badge status
        const badge = document.querySelector(`.nav-badge[data-index="${slideIndex}"]`);
        if (badge && !flaggedQuestions[questionId]) {
            badge.className = 'nav-badge answered';
            if (slideIndex === currentStep) badge.classList.add('active');
        } else if (badge) {
            badge.classList.add('answered');
        }
    }

    function toggleFlag(questionId, button) {
        const isFlagged = !flaggedQuestions[questionId];
        flaggedQuestions[questionId] = isFlagged;
        
        const badge = document.querySelector(`.nav-badge[data-index="${currentStep}"]`);
        
        if (isFlagged) {
            button.classList.remove('btn-secondary');
            button.classList.add('btn-warning');
            button.style.background = '#f59e0b';
            button.style.color = '#000';
            button.querySelector('.flag-text').textContent = 'Flagged';
            if (badge) badge.classList.add('flagged');
        } else {
            button.classList.remove('btn-warning');
            button.classList.add('btn-secondary');
            button.style.background = '';
            button.style.color = '';
            button.querySelector('.flag-text').textContent = 'Flagged for Review';
            if (badge) badge.classList.remove('flagged');
        }
    }

    // Nav buttons
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (currentStep < totalQuestions - 1) {
                currentStep++;
                showSlide(currentStep);
            } else {
                openSubmitModal();
            }
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentStep > 0) {
                currentStep--;
                showSlide(currentStep);
            }
        });
    }

    // Modal navigation
    if (triggerSubmitBtn) {
        triggerSubmitBtn.addEventListener('click', openSubmitModal);
    }
    
    if (cancelModalBtn) {
        cancelModalBtn.addEventListener('click', closeSubmitModal);
    }
    
    if (confirmModalBtn) {
        confirmModalBtn.addEventListener('click', submitQuiz);
    }

    function openSubmitModal() {
        if (!submitModal) return;
        
        // Calculate status counts
        const answeredCount = Object.keys(userAnswers).length;
        const unansweredCount = totalQuestions - answeredCount;
        const flaggedCount = Object.values(flaggedQuestions).filter(Boolean).length;
        
        document.getElementById('modal-total-count').textContent = totalQuestions;
        document.getElementById('modal-answered-count').textContent = answeredCount;
        document.getElementById('modal-unanswered-count').textContent = unansweredCount;
        document.getElementById('modal-flagged-count').textContent = flaggedCount;
        
        submitModal.classList.add('show');
    }
    
    function closeSubmitModal() {
        if (submitModal) submitModal.classList.remove('show');
    }

    function buildNavigationGrid() {
        if (!navBadgeContainer) return;
        navBadgeContainer.innerHTML = '';
        
        slides.forEach((slide, index) => {
            const badge = document.createElement('div');
            badge.className = 'nav-badge';
            badge.setAttribute('data-index', index);
            badge.textContent = index + 1;
            
            badge.addEventListener('click', () => {
                currentStep = index;
                showSlide(currentStep);
            });
            
            navBadgeContainer.appendChild(badge);
        });
    }

    function showSlide(index) {
        slides.forEach((slide, i) => {
            if (i === index) {
                slide.style.display = 'block';
                slide.classList.add('active');
            } else {
                slide.style.display = 'none';
                slide.classList.remove('active');
            }
        });

        // Update Nav Buttons
        if (prevBtn) {
            prevBtn.style.visibility = index === 0 ? 'hidden' : 'visible';
        }
        
        if (nextBtn) {
            if (index === totalQuestions - 1) {
                nextBtn.innerHTML = `Review & Submit 
                    <svg class="feather" style="width: 16px; height: 16px;" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                `;
                nextBtn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
                nextBtn.style.borderColor = '#10b981';
            } else {
                nextBtn.innerHTML = `Next Question 
                    <svg class="feather" style="width: 16px; height: 16px;" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                `;
                nextBtn.style.background = '';
                nextBtn.style.borderColor = '';
            }
        }

        // Update Navigation badges active classes
        document.querySelectorAll('.nav-badge').forEach((badge, idx) => {
            if (idx === index) {
                badge.classList.add('active');
            } else {
                badge.classList.remove('active');
            }
        });
    }

    function startTimer() {
        timerInterval = setInterval(() => {
            timeLeft--;
            
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timerDisplay.textContent = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;

            if (timeLeft <= 30) {
                timerBar.style.borderColor = 'rgba(239, 68, 68, 0.4)';
                timerBar.style.background = 'rgba(239, 68, 68, 0.1)';
                timerDisplay.style.color = '#f87171';
                
                // Pulsing animation
                timerDisplay.style.animation = 'pulse 1s infinite alternate';
            }

            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                alert("Time's up! Submitting your answers automatically.");
                submitQuiz();
            }
        }, 1000);
    }

    function submitQuiz() {
        clearInterval(timerInterval);
        
        // Ensure answers input is populated
        answersInput.value = JSON.stringify(userAnswers);
        
        // Submit the form
        form.submit();
    }

    // Format all question texts with code blocks on load
    document.querySelectorAll('.quiz-question-text').forEach(el => {
        el.innerHTML = formatQuestionText(el.textContent);
    });
});

function formatQuestionText(text) {
    if (!text) return '';
    
    // Escape HTML characters
    let escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

    // Extract and preserve code blocks (```python ... ```)
    const codeBlocks = [];
    escaped = escaped.replace(/```(?:[a-zA-Z0-9]+)?\n([\s\S]*?)\n```/g, function(match, code) {
        const placeholder = `__CODE_BLOCK_PLACEHOLDER_${codeBlocks.length}__`;
        codeBlocks.push(`<pre style="background: #0b0e14; border: 1px solid var(--border-color); padding: 1.25rem; border-radius: 12px; font-family: 'Consolas', 'Courier New', monospace; font-size: 0.9rem; color: #f8f8f2; overflow-x: auto; margin: 1rem 0; text-align: left; line-height: 1.5; font-weight: 400;"><code style="font-family: inherit; white-space: pre;">${code}</code></pre>`);
        return placeholder;
    });

    // Replace inline code blocks: `code`
    escaped = escaped.replace(/`(.*?)`/g, '<code style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.4rem; border-radius: 4px; font-family: \'Consolas\', \'Courier New\', monospace; font-size: 0.9em; color: var(--secondary); font-weight: 500;">$1</code>');

    // Replace newlines with <br>
    escaped = escaped.replace(/\n/g, '<br>');

    // Restore the formatted code blocks
    codeBlocks.forEach((blockHtml, index) => {
        escaped = escaped.replace(`__CODE_BLOCK_PLACEHOLDER_${index}__`, blockHtml);
    });

    return escaped;
}
