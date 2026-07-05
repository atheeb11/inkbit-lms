from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # Nullable for Google auth users
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' or 'teacher'
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    microsoft_id = db.Column(db.String(100), unique=True, nullable=True)
    telegram_notifications = db.Column(db.Boolean, default=False)
    telegram_chat_id = db.Column(db.String(100), nullable=True)
    preferred_theme = db.Column(db.String(50), default='dark-glass')
    profile_bio = db.Column(db.String(250), nullable=True)
    profile_photo = db.Column(db.String(300), nullable=True)
    social_whatsapp = db.Column(db.String(100), nullable=True)
    social_instagram = db.Column(db.String(100), nullable=True)
    social_telegram = db.Column(db.String(100), nullable=True)
    social_linkedin = db.Column(db.String(100), nullable=True)
    xp_points = db.Column(db.Integer, default=0)
    login_streak = db.Column(db.Integer, default=1)
    last_login_date = db.Column(db.Date, nullable=True)
    ai_queries_count = db.Column(db.Integer, default=0)
    is_verified = db.Column(db.Boolean, default=False)
    verification_otp = db.Column(db.String(10), nullable=True)
    verification_otp_expiry = db.Column(db.DateTime, nullable=True)
    two_factor_otp = db.Column(db.String(10), nullable=True)
    two_factor_otp_expiry = db.Column(db.DateTime, nullable=True)
    is_approved_by_admin = db.Column(db.Boolean, default=False)
    failed_login_attempts = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime, nullable=True)
    personalized_roadmap = db.Column(db.Text, nullable=True)
    bookmarks_json = db.Column(db.Text, nullable=True)
    registration_number = db.Column(db.String(50), unique=True, nullable=True)
    
    
    # Relationships
    courses_taught = db.relationship('Course', backref='teacher', lazy=True, cascade="all, delete-orphan")
    enrollments = db.relationship('Enrollment', backref='student', lazy=True, cascade="all, delete-orphan")
    submissions = db.relationship('Submission', backref='student', lazy=True, cascade="all, delete-orphan")
    quiz_results = db.relationship('QuizResult', backref='student', lazy=True, cascade="all, delete-orphan")
    progress_records = db.relationship('Progress', backref='student', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        import bcrypt
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        self.password_hash = hashed.decode('utf-8')

    def check_password(self, password):
        if not self.password_hash:
            return False
        import bcrypt
        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except Exception:
            # Fallback for old pbkdf2/scrypt hashed user records in database
            try:
                return check_password_hash(self.password_hash, password)
            except Exception:
                return False


class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department = db.Column(db.String(100), default='Teknik Informatika')
    tags = db.Column(db.String(200), default='Project Based Learning,Case Method,Partisipatif Kolaboratif')
    schedule = db.Column(db.String(100), default='Jumat, 20:55 - 21:45')
    total_sessions = db.Column(db.Integer, default=16)
    is_paid = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float, default=0.0)
    
    # Relationships
    enrollments = db.relationship('Enrollment', backref='course', lazy=True, cascade="all, delete-orphan")
    materials = db.relationship('Material', backref='course', lazy=True, cascade="all, delete-orphan")
    assignments = db.relationship('Assignment', backref='course', lazy=True, cascade="all, delete-orphan")
    quizzes = db.relationship('Quiz', backref='course', lazy=True, cascade="all, delete-orphan")
    progress_records = db.relationship('Progress', backref='course', lazy=True, cascade="all, delete-orphan")
    forum_threads = db.relationship('ForumThread', backref='course', lazy=True, cascade="all, delete-orphan")


class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    attendance_count = db.Column(db.Integer, default=10)
    payment_status = db.Column(db.String(20), default='free')


class Material(db.Model):
    __tablename__ = 'materials'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(300), nullable=False)
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=False)
    points = db.Column(db.Integer, default=100)
    file_path = db.Column(db.String(300), nullable=True)  # Optional prompt reference file
    auto_grade = db.Column(db.Boolean, default=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade="all, delete-orphan")


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    file_path = db.Column(db.String(300), nullable=True)  # File upload
    text_content = db.Column(db.Text, nullable=True)      # Essay text submission
    grade = db.Column(db.Float, nullable=True)            # Numeric grade
    feedback = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='submitted')  # 'submitted', 'graded'


class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade="all, delete-orphan")
    results = db.relationship('QuizResult', backref='quiz', lazy=True, cascade="all, delete-orphan")


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', or 'D'


class QuizResult(db.Model):
    __tablename__ = 'quiz_results'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Progress(db.Model):
    __tablename__ = 'progress'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    materials_viewed = db.Column(db.Integer, default=0)
    assignments_completed = db.Column(db.Integer, default=0)
    quizzes_completed = db.Column(db.Integer, default=0)


user_badges = db.Table('user_badges',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    db.Column('badge_id', db.Integer, db.ForeignKey('badges.id', ondelete='CASCADE'), primary_key=True),
    db.Column('awarded_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
)


class LiveClass(db.Model):
    __tablename__ = 'live_classes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    meeting_link = db.Column(db.String(300), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    recording_url = db.Column(db.String(300), nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    
    course = db.relationship('Course', backref=db.backref('live_classes', lazy=True, cascade="all, delete-orphan"))


class ForumThread(db.Model):
    __tablename__ = 'forum_threads'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    author = db.relationship('User', backref=db.backref('threads', lazy=True, cascade="all, delete-orphan"))
    replies = db.relationship('ForumReply', backref='thread', lazy=True, cascade="all, delete-orphan")


class ForumReply(db.Model):
    __tablename__ = 'forum_replies'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    thread_id = db.Column(db.Integer, db.ForeignKey('forum_threads.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    author = db.relationship('User', backref=db.backref('replies', lazy=True, cascade="all, delete-orphan"))


class Badge(db.Model):
    __tablename__ = 'badges'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(250), nullable=False)
    icon_code = db.Column(db.String(50), nullable=False)  # Font Awesome or emoji symbol
    
    users = db.relationship('User', secondary=user_badges, backref=db.backref('badges', lazy='dynamic'))


class Certificate(db.Model):
    __tablename__ = 'certificates'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    certificate_code = db.Column(db.String(100), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_approved = db.Column(db.Boolean, default=False)
    
    # Relationships
    student = db.relationship('User', backref=db.backref('certificates', lazy=True, cascade="all, delete-orphan"))
    course = db.relationship('Course', backref=db.backref('certificates', lazy=True, cascade="all, delete-orphan"))


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(250), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))

