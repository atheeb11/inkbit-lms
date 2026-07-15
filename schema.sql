-- InkBit LMS MySQL Database Schema
-- Fully updated to match the application models and migrations.

CREATE DATABASE `inkbit`;
USE `inkbit`;

-- 1. Users Table
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `email` VARCHAR(120) NOT NULL UNIQUE,
    `password_hash` VARCHAR(256) DEFAULT NULL,
    `name` VARCHAR(100) NOT NULL,
    `role` VARCHAR(20) NOT NULL,
    `google_id` VARCHAR(100) UNIQUE DEFAULT NULL,
    `microsoft_id` VARCHAR(100) UNIQUE DEFAULT NULL,
    `telegram_notifications` TINYINT(1) DEFAULT 0,
    `telegram_chat_id` VARCHAR(100) DEFAULT NULL,
    `preferred_theme` VARCHAR(50) DEFAULT 'dark-glass',
    `profile_bio` VARCHAR(250) DEFAULT NULL,
    `profile_photo` VARCHAR(300) DEFAULT NULL,
    `social_whatsapp` VARCHAR(100) DEFAULT NULL,
    `social_instagram` VARCHAR(100) DEFAULT NULL,
    `social_telegram` VARCHAR(100) DEFAULT NULL,
    `social_linkedin` VARCHAR(100) DEFAULT NULL,
    `xp_points` INT DEFAULT 0,
    `login_streak` INT DEFAULT 1,
    `last_login_date` DATE DEFAULT NULL,
    `ai_queries_count` INT DEFAULT 0,
    `is_verified` TINYINT(1) DEFAULT 0,
    `verification_otp` VARCHAR(10) DEFAULT NULL,
    `verification_otp_expiry` DATETIME DEFAULT NULL,
    `two_factor_otp` VARCHAR(10) DEFAULT NULL,
    `two_factor_otp_expiry` DATETIME DEFAULT NULL,
    `is_approved_by_admin` TINYINT(1) DEFAULT 0,
    `failed_login_attempts` INT DEFAULT 0,
    `lockout_until` DATETIME DEFAULT NULL,
    `personalized_roadmap` TEXT DEFAULT NULL,
    `bookmarks_json` TEXT DEFAULT NULL,
    `registration_number` VARCHAR(50) UNIQUE DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Courses Table
CREATE TABLE `courses` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `code` VARCHAR(20) NOT NULL UNIQUE,
    `name` VARCHAR(150) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `teacher_id` INT NOT NULL,
    `department` VARCHAR(100) DEFAULT 'Teknik Informatika',
    `tags` VARCHAR(200) DEFAULT 'Project Based Learning,Case Method,Partisipatif Kolaboratif',
    `schedule` VARCHAR(100) DEFAULT 'Jumat, 20:55 - 21:45',
    `total_sessions` INT DEFAULT 16,
    `is_paid` TINYINT(1) DEFAULT 0,
    `price` DOUBLE DEFAULT 0.0,
    CONSTRAINT `fk_courses_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Enrollments Table
CREATE TABLE `enrollments` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `course_id` INT NOT NULL,
    `enrolled_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `attendance_count` INT DEFAULT 10,
    `payment_status` VARCHAR(20) DEFAULT 'free',
    CONSTRAINT `fk_enrollments_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_enrollments_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Materials Table
CREATE TABLE `materials` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(150) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `file_path` VARCHAR(300) NOT NULL,
    `upload_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `course_id` INT NOT NULL,
    CONSTRAINT `fk_materials_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Assignments Table
CREATE TABLE `assignments` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(150) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `due_date` DATETIME NOT NULL,
    `points` INT DEFAULT 100,
    `file_path` VARCHAR(300) DEFAULT NULL,
    `auto_grade` TINYINT(1) DEFAULT 0,
    `course_id` INT NOT NULL,
    CONSTRAINT `fk_assignments_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Submissions Table
CREATE TABLE `submissions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `assignment_id` INT NOT NULL,
    `student_id` INT NOT NULL,
    `submitted_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `file_path` VARCHAR(300) DEFAULT NULL,
    `text_content` TEXT DEFAULT NULL,
    `grade` DOUBLE DEFAULT NULL,
    `feedback` TEXT DEFAULT NULL,
    `status` VARCHAR(20) DEFAULT 'submitted',
    CONSTRAINT `fk_submissions_assignment` FOREIGN KEY (`assignment_id`) REFERENCES `assignments` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_submissions_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Quizzes Table
CREATE TABLE `quizzes` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(150) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `due_date` DATETIME DEFAULT NULL,
    `course_id` INT NOT NULL,
    CONSTRAINT `fk_quizzes_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Questions Table
CREATE TABLE `questions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `quiz_id` INT NOT NULL,
    `question_text` TEXT NOT NULL,
    `option_a` VARCHAR(200) NOT NULL,
    `option_b` VARCHAR(200) NOT NULL,
    `option_c` VARCHAR(200) NOT NULL,
    `option_d` VARCHAR(200) NOT NULL,
    `correct_answer` VARCHAR(1) NOT NULL,
    `explanation` TEXT DEFAULT NULL,
    CONSTRAINT `fk_questions_quiz` FOREIGN KEY (`quiz_id`) REFERENCES `quizzes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Quiz Results Table
CREATE TABLE `quiz_results` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `quiz_id` INT NOT NULL,
    `student_id` INT NOT NULL,
    `score` DOUBLE NOT NULL,
    `total_questions` INT NOT NULL,
    `submitted_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `answers_json` TEXT DEFAULT NULL,
    CONSTRAINT `fk_results_quiz` FOREIGN KEY (`quiz_id`) REFERENCES `quizzes` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_results_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Progress Table
CREATE TABLE `progress` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `course_id` INT NOT NULL,
    `materials_viewed` INT DEFAULT 0,
    `assignments_completed` INT DEFAULT 0,
    `quizzes_completed` INT DEFAULT 0,
    CONSTRAINT `fk_progress_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_progress_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. Badges Table
CREATE TABLE `badges` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL UNIQUE,
    `description` VARCHAR(250) NOT NULL,
    `icon_code` VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. User Badges Junction Table (Many-to-Many)
CREATE TABLE `user_badges` (
    `user_id` INT NOT NULL,
    `badge_id` INT NOT NULL,
    `awarded_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`user_id`, `badge_id`),
    CONSTRAINT `fk_ub_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ub_badge` FOREIGN KEY (`badge_id`) REFERENCES `badges` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 13. Live Classes Table
CREATE TABLE `live_classes` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(150) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `meeting_link` VARCHAR(300) NOT NULL,
    `scheduled_time` DATETIME NOT NULL,
    `course_id` INT NOT NULL,
    `recording_url` VARCHAR(300) DEFAULT NULL,
    `ai_summary` TEXT DEFAULT NULL,
    CONSTRAINT `fk_lc_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 14. Forum Threads Table
CREATE TABLE `forum_threads` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(150) NOT NULL,
    `content` TEXT NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `course_id` INT NOT NULL,
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_ft_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ft_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 15. Forum Replies Table
CREATE TABLE `forum_replies` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `content` TEXT NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `thread_id` INT NOT NULL,
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_fr_thread` FOREIGN KEY (`thread_id`) REFERENCES `forum_threads` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_fr_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 16. Certificates Table
CREATE TABLE `certificates` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `course_id` INT NOT NULL,
    `certificate_code` VARCHAR(100) NOT NULL UNIQUE,
    `issued_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `is_approved` TINYINT(1) DEFAULT 0,
    CONSTRAINT `fk_certs_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_certs_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 17. Audit Logs Table
CREATE TABLE `audit_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT DEFAULT NULL,
    `action` VARCHAR(100) NOT NULL,
    `ip_address` VARCHAR(45) DEFAULT NULL,
    `user_agent` VARCHAR(250) DEFAULT NULL,
    `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
