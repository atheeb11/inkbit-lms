// INKBIT LMS - Quiz Runner Controller

document.addEventListener('DOMContentLoaded', () => {
    const slides = document.querySelectorAll('.question-slide');
    if (slides.length === 0) return;

    let currentStep = 0;
    const totalQuestions = slides.length;
    const progressFill = document.querySelector('.quiz-progress-fill');
    const prevBtn = document.getElementById('prev-question-btn');
    const nextBtn = document.getElementById('next-question-btn');
    const timerDisplay = document.getElementById('timer-count');
    const form = document.getElementById('quiz-submit-form');
    const answersInput = document.getElementById('quiz-answers-input');

    // Selected answers store: {question_id: choice}
    const userAnswers = {};

    // Initialize progress bar
    updateProgress();
    showSlide(currentStep);

    // Timer Setup (Default 5 minutes = 300 seconds)
    let timeLeft = parseInt(document.getElementById('quiz-timer-bar')?.getAttribute('data-duration') || '300');
    let timerInterval;

    if (timerDisplay) {
        startTimer();
    }

    // Set up option clicks
    slides.forEach(slide => {
        const questionId = slide.getAttribute('data-question-id');
        const options = slide.querySelectorAll('.quiz-option-card');
        
        options.forEach(option => {
            option.addEventListener('click', () => {
                // Clear selection in this slide
                options.forEach(o => o.classList.remove('selected'));
                
                // Select clicked option
                option.classList.add('selected');
                const choice = option.getAttribute('data-choice');
                userAnswers[questionId] = choice;
                
                // Update hidden input
                answersInput.value = JSON.stringify(userAnswers);
            });
        });
    });

    // Nav buttons
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (currentStep < totalQuestions - 1) {
                currentStep++;
                showSlide(currentStep);
                updateProgress();
            } else {
                // Submit Form
                submitQuiz();
            }
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentStep > 0) {
                currentStep--;
                showSlide(currentStep);
                updateProgress();
            }
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
            prevBtn.style.display = index === 0 ? 'none' : 'inline-flex';
        }
        
        if (nextBtn) {
            if (index === totalQuestions - 1) {
                nextBtn.innerHTML = `Submit Quiz 
                    <svg class="feather" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                `;
                nextBtn.classList.remove('btn-primary');
                nextBtn.classList.add('btn-primary'); // keep styling primary, maybe change text
            } else {
                nextBtn.innerHTML = `Next Question 
                    <svg class="feather" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                `;
            }
        }
    }

    function updateProgress() {
        if (progressFill) {
            const percentage = ((currentStep) / totalQuestions) * 100;
            progressFill.style.width = `${percentage}%`;
        }
    }

    function startTimer() {
        timerInterval = setInterval(() => {
            timeLeft--;
            
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timerDisplay.textContent = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;

            if (timeLeft <= 30) {
                timerDisplay.parentElement.style.color = 'var(--danger)';
            }

            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                alert("Time's up! Submitting your answers.");
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
});
