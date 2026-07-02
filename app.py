import os
import json
import urllib
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, Course, Enrollment, Material, Assignment, Submission, Quiz, Question, QuizResult, Progress, Badge, LiveClass, ForumThread, ForumReply, Certificate, AuditLog

app = Flask(__name__)
app.config.from_object(Config)

# Check MySQL connection and auto-create database if configured
db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
if 'mysql' in db_uri:
    import pymysql
    try:
        # Connect to MySQL server to ensure schema is present
        connection = pymysql.connect(
            host=app.config.get('MYSQL_HOST', 'localhost'),
            user=app.config.get('MYSQL_USER', 'root'),
            password=app.config.get('MYSQL_PASSWORD', ''),
            port=int(app.config.get('MYSQL_PORT', 3306)),
            connect_timeout=2
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {app.config.get('MYSQL_DB', 'inkbit')}")
            connection.commit()
            print(f"Verified/Created MySQL Database: {app.config.get('MYSQL_DB', 'inkbit')}")
        finally:
            connection.close()
    except Exception as e:
        print("=" * 80)
        print(f"[DATABASE WARNING] Failed to connect to MySQL database at {app.config.get('MYSQL_HOST')}:{app.config.get('MYSQL_PORT')}")
        print(f"Connection Error: {e}")
        print("FALLING BACK TO LOCAL SQLITE DATABASE FOR APPLICATION STABILITY.")
        print("=" * 80)
        
        # Switch back to local sqlite database
        basedir = os.path.abspath(os.path.dirname(__file__))
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'inkbit.db')

# Initialize Flask Plugins
db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Context processor to inject datetime for footer
@app.context_processor
def inject_datetime():
    return {'datetime': datetime, 'timezone': timezone}

@app.before_request
def update_user_streak():
    if current_user.is_authenticated and current_user.role == 'student':
        today = datetime.now(timezone.utc).date()
        if not current_user.last_login_date:
            current_user.last_login_date = today
            current_user.login_streak = 1
            db.session.commit()
        else:
            last_date = current_user.last_login_date
            if isinstance(last_date, str):
                try:
                    last_date = datetime.strptime(last_date, '%Y-%m-%d').date()
                except Exception:
                    last_date = today
            
            delta = today - last_date
            if delta.days == 1:
                current_user.login_streak += 1
                current_user.xp_points += current_user.login_streak * 10
                current_user.last_login_date = today
                
                streak_badge = Badge.query.filter_by(name="Streak Master").first()
                if streak_badge and current_user.login_streak >= 7:
                    if streak_badge not in current_user.badges:
                        current_user.badges.append(streak_badge)
                        flash("🏆 New Badge Unlocked: Streak Master! (7-Day Streak)", "info")
                db.session.commit()
            elif delta.days > 1:
                current_user.login_streak = 1
                current_user.last_login_date = today
                db.session.commit()

@app.after_request
def add_header(response):
    # Enable aggressive cache control for static assets to reduce device lag on page reloads
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=2592000, must-revalidate'
    return response

# File Upload helper
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']



def seed_database(seed_courses=False):
    # Ensure default seeded users are marked verified and approved
    default_seed_emails = ['teacher@inkbit.com', 'student@inkbit.com', 'institution@inkbit.com', 'teacher2@inkbit.com', 'student2@inkbit.com', 'atheeb1311@gmail.com', 'inkbitdigitalstudio@gmail.com']
    for email in default_seed_emails:
        user = User.query.filter_by(email=email).first()
        if user:
            user.is_verified = True
            if user.role in ['teacher', 'institution']:
                user.is_approved_by_admin = True
    db.session.commit()

    # Seed users
    users_to_seed = [
        ('teacher@inkbit.com', 'Turing Teacher', 'teacher', 'inkbit123'),
        ('student@inkbit.com', 'Steve Student', 'student', 'inkbit123'),
        ('institution@inkbit.com', 'InkBit Institute', 'institution', 'inkbit123'),
        ('atheeb1311@gmail.com', 'Atheeb', 'student', 'Password123!'),
        ('inkbitdigitalstudio@gmail.com', 'InkBit Studio', 'student', 'Password123!'),
        ('teacher2@inkbit.com', 'Grace Hopper', 'teacher', 'inkbit123'),
        ('student2@inkbit.com', 'Ada Lovelace', 'student', 'inkbit123')
    ]
    
    seeded_users = {}
    for email, name, role, pswd in users_to_seed:
        user = User.query.filter_by(email=email).first()
        if not user:
            is_approved = role in ['teacher', 'institution']
            user = User(email=email, name=name, role=role, is_verified=True, is_approved_by_admin=is_approved)
            user.set_password(pswd)
            db.session.add(user)
            db.session.commit()
            print(f"Seeded user: {email}")
        else:
            user.is_verified = True
            if role in ['teacher', 'institution']:
                user.is_approved_by_admin = True
            db.session.commit()
        seeded_users[email] = user

    # Seed Courses and enrollments if Course table is empty AND seed_courses is True
    if seed_courses and Course.query.count() == 0:
        print("Seeding courses...")
        teacher = seeded_users.get('teacher@inkbit.com') or User.query.filter_by(email='teacher@inkbit.com').first()
        student = seeded_users.get('student@inkbit.com') or User.query.filter_by(email='student@inkbit.com').first()
        
        courses_data = [
            {
                'code': 'CS-201',
                'name': 'Civic Education (CS-201)',
                'desc': 'Learn national cultural values, national identity, and patriotic values.',
                'dept': 'Computer Science',
                'tags': 'Project Based Learning,Case Method,Participatory Collaborative',
                'sched': 'Friday, 13:00 - 15:30',
                'attendance': 0,
                'sessions': 16,
                'is_paid': True,
                'price': 49.99
            },
            {
                'code': 'CS-202',
                'name': 'Operating Systems (CS-202)',
                'desc': 'Covers memory management, processor scheduling, file systems, and computer virtualization.',
                'dept': 'Computer Science',
                'tags': 'Project Based Learning,Case Method,Participatory Collaborative',
                'sched': 'Thursday, 16:00 - 17:40',
                'attendance': 6,
                'sessions': 16
            },
            {
                'code': 'CS-101',
                'name': 'Introduction to Programming (CS-101)',
                'desc': 'Foundations of computer programming logic and problem solving using Python.',
                'dept': 'Computer Science',
                'tags': 'Project Based Learning,Case Method,Participatory Collaborative',
                'sched': 'Friday, 08:00 - 10:30',
                'attendance': 10,
                'sessions': 16
            },
            {
                'code': 'CS-203',
                'name': 'Database Systems (CS-203)',
                'desc': 'ERD design, normalization, relational algebra, and SQL query implementation.',
                'dept': 'Computer Science',
                'tags': 'Case Method',
                'sched': 'Monday, 13:00 - 15:30',
                'attendance': 9,
                'sessions': 16
            },
            {
                'code': 'CS-102',
                'name': 'Linear Algebra (CS-102)',
                'desc': 'Vectors, matrices, systems of linear equations, and transformations.',
                'dept': 'Computer Science',
                'tags': 'Project Based Learning,Case Method,Participatory Collaborative',
                'sched': 'Monday, 10:00 - 12:30',
                'attendance': 5,
                'sessions': 16
            },
            {
                'code': 'CS-103',
                'name': 'Discrete Mathematics (CS-103)',
                'desc': 'Propositional logic, sets, relations, functions, graphs, and combinatorics.',
                'dept': 'Computer Science',
                'tags': 'Project Based Learning,Case Method,Participatory Collaborative',
                'sched': 'Wednesday, 13:00 - 15:30',
                'attendance': 12,
                'sessions': 16
            }
        ]
        
        courses_db = []
        for cdata in courses_data:
            course = Course(
                code=cdata['code'],
                name=cdata['name'],
                description=cdata['desc'],
                department=cdata['dept'],
                tags=cdata['tags'],
                schedule=cdata['sched'],
                total_sessions=cdata['sessions'],
                is_paid=cdata.get('is_paid', False),
                price=cdata.get('price', 0.0),
                teacher_id=teacher.id if teacher else None
            )
            db.session.add(course)
            courses_db.append((course, cdata['attendance']))
        db.session.commit()
        
        md_course = Course.query.filter_by(code='CS-103').first()
        kp_course = Course.query.filter_by(code='CS-201').first()
        
        materials_seeding_data = {
            'CS-201': [
                {
                    'title': 'Civic Education Syllabus & Outline',
                    'desc': 'Overview of patriotic values, national identity, and weekly syllabus topics.',
                    'filename': 'cs201_syllabus.pdf',
                    'content': 'INKBIT LMS - Civic Education (CS-201) Course Syllabus\n\nWeekly Schedule:\n1. National Cultural Values\n2. History and National Identity\n3. Democratic Practices\n4. Collaborative Community Projects\n\nReference: National Citizenship Guidelines.'
                },
                {
                    'title': 'Case Study: Participatory Democracy',
                    'desc': 'Analysis paper on local community decision-making and democratic frameworks.',
                    'filename': 'cs201_case_study.pdf',
                    'content': 'Case Study: Participatory Democracy in Community Development\n\nAbstract:\nThis study evaluates collaborative models where citizens take active roles in regional resource allocation, reflecting patriotic duty and civic engagement.'
                }
            ],
            'CS-202': [
                {
                    'title': 'Operating Systems Lecture Notes',
                    'desc': 'Concepts of processor scheduling, memory management, and virtualization.',
                    'filename': 'cs202_syllabus.pdf',
                    'content': 'Operating Systems (CS-202) Reference Manual\n\nTopics:\n- CPU Scheduling (Round Robin, FIFO, Shortest Job First)\n- Memory Allocation & Virtual Memory\n- File System Layouts and Security\n- Virtualization and Containers.'
                },
                {
                    'title': 'Lab Manual: Semaphore Synchronization',
                    'desc': 'Guidelines for solving the Producer-Consumer problem using Semaphores in C.',
                    'filename': 'cs202_lab_manual.pdf',
                    'content': 'Lab Manual - Process Synchronization & Mutexes\n\nInstructions:\nImplement a bounded buffer using pthread mutexes and condition variables. Ensure there are no race conditions or deadlocks.'
                }
            ],
            'CS-101': [
                {
                    'title': 'Python Programming Slides',
                    'desc': 'Fundamental syntax, conditionals, loops, and list structures.',
                    'filename': 'cs101_lecture_slides.pdf',
                    'content': 'Introduction to Programming (CS-101) Slides\n\nSession 1: Python Basics\n- Variables and Data Types\n- If/Else Conditions\n- For & While Loops\n- Functions and Arguments'
                },
                {
                    'title': 'Python Practice Lab Book',
                    'desc': '15 exercises ranging from Fibonacci sequence to basic file manipulation.',
                    'filename': 'cs101_lab_exercises.pdf',
                    'content': 'Programming Lab Exercises\n\nProblems:\n1. Print Prime Numbers in a range.\n2. Write a recursive Fibonacci function.\n3. Read a CSV file and output summary statistics.'
                }
            ],
            'CS-203': [
                {
                    'title': 'Relational Database Design & Normalization',
                    'desc': 'Deep-dive into ERD layouts and normalization rules up to BCNF.',
                    'filename': 'cs203_lecture_notes.pdf',
                    'content': 'Database Systems (CS-203) - Normalization Guide\n\nSteps:\n- 1NF: Eliminate repeating groups.\n- 2NF: Eliminate partial dependencies.\n- 3NF: Eliminate transitive dependencies.\n- BCNF: Determinants must be candidate keys.'
                },
                {
                    'title': 'SQL Query Cheat Sheet',
                    'desc': 'Comprehensive syntax list for joins, group by, window functions, and aggregates.',
                    'filename': 'cs203_sql_cheatsheet.pdf',
                    'content': 'SQL Cheat Sheet\n\nQueries:\n- SELECT name, COUNT(*) FROM users GROUP BY name HAVING COUNT(*) > 1;\n- SELECT u.name, e.course_id FROM users u INNER JOIN enrollments e ON u.id = e.student_id;'
                }
            ],
            'CS-102': [
                {
                    'title': 'Linear Algebra Syllabus & Guide',
                    'desc': 'Course overview covering vector spaces and systems of equations.',
                    'filename': 'cs102_syllabus.pdf',
                    'content': 'Linear Algebra (CS-102) Course Guide\n\nTopics:\n- Matrix Multiplication and Inverses\n- Determinants and Cramer\'s Rule\n- Vector Spaces and Subspaces\n- Eigenvalues and Eigenvectors'
                },
                {
                    'title': 'Practice Set: Linear Transformations',
                    'desc': 'Problems covering rotation, scaling, and projection matrices.',
                    'filename': 'cs102_exercises.pdf',
                    'content': 'Practice Exercises: Linear Transformations\n\nSolve the following transformation mapping problems. Explain the basis change and kernel calculations step-by-step.'
                }
            ],
            'CS-103': [
                {
                    'title': 'Syllabus & Logic Introduction',
                    'desc': 'Welcome guidelines and weekly breakdown of propositional logic and set theory.',
                    'filename': 'cs103_syllabus.pdf',
                    'content': 'Discrete Mathematics (CS-103) Syllabus\n\nOverview:\n- Mathematical Logic and Proofs\n- Set Theory and Relations\n- Combinatorics and Probability\n- Graph Theory applications'
                },
                {
                    'title': 'Graph Theory Cheat Sheet',
                    'desc': 'Brief definitions of graphs, trees, paths, Euler circuits, and Hamiltonian cycles.',
                    'filename': 'cs103_graph_theory.pdf',
                    'content': 'Graph Theory Quick Reference\n\nDefinitions:\n- Vertex / Edge\n- Directed / Undirected\n- Euler Path: Visits every edge exactly once.\n- Hamiltonian Cycle: Visits every vertex exactly once.'
                }
            ]
        }
        
        for c_code, mats in materials_seeding_data.items():
            course_ptr = Course.query.filter_by(code=c_code).first()
            if course_ptr:
                for mat in mats:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], mat['filename'])
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(mat['content'])
                    
                    new_mat = Material(
                        title=mat['title'],
                        description=mat['desc'],
                        file_path=mat['filename'],
                        course_id=course_ptr.id
                    )
                    db.session.add(new_mat)
        
        if kp_course:
            due_assign = datetime.now(timezone.utc) + timedelta(days=6)
            assignment1 = Assignment(title='Assignment - Session #14', description='Civics response paper writing on global citizenship.', due_date=due_assign, points=100, course_id=kp_course.id)
            assignment2 = Assignment(title='Final Project - Collaborative Report', description='Collaboration report on civic values.', due_date=datetime.now(timezone.utc) + timedelta(days=8), points=100, course_id=kp_course.id)
            db.session.add_all([assignment1, assignment2])
        
        if md_course:
            due_quiz_close = datetime.now(timezone.utc) + timedelta(days=2)
            quiz12 = Quiz(title='Quiz #12', description='Discrete Mathematics - Mathematical Logic.', due_date=due_quiz_close, course_id=md_course.id)
            quiz13 = Quiz(title='Quiz #13', description='Discrete Mathematics - Relations and Sets.', due_date=due_quiz_close, course_id=md_course.id)
            quiz14 = Quiz(title='Quiz - Session #14', description='Discrete Mathematics - Graph Theory.', due_date=datetime.now(timezone.utc) + timedelta(days=6), course_id=md_course.id)
            
            db.session.add_all([quiz12, quiz13, quiz14])
            db.session.commit()
            
            q1 = Question(quiz_id=quiz12.id, question_text="What is the result of 3 + 2 * 4 in Python?", option_a="20", option_b="14", option_c="11", option_d="None of the above", correct_answer="C")
            q2 = Question(quiz_id=quiz12.id, question_text="Which data type stores text in Python?", option_a="int", option_b="float", option_c="str", option_d="bool", correct_answer="C")
            q3 = Question(quiz_id=quiz12.id, question_text="What is the output of print(len('Inkbit'))?", option_a="5", option_b="6", option_c="7", option_d="Error", correct_answer="B")
            db.session.add_all([q1, q2, q3])
            db.session.commit()
            
        # Seed LiveClasses if empty
        python_course = Course.query.filter_by(code='CS-101').first()
        db_course = Course.query.filter_by(code='CS-203').first()
        os_course = Course.query.filter_by(code='CS-202').first()
        
        if python_course and db_course and os_course:
            live1 = LiveClass(
                title="Python Programming Live Lecture",
                description="Live classroom webinar focusing on object-oriented structures, inheritance, and magic methods.",
                meeting_link="https://meet.google.com/abc-defg-hij",
                scheduled_time=datetime.now() + timedelta(hours=2),
                course_id=python_course.id
            )
            live2 = LiveClass(
                title="Operating Systems Live Workshop",
                description="Interactive workshop detailing CPU scheduling algorithms.",
                meeting_link="https://meet.google.com/klm-nopq-rst",
                scheduled_time=datetime.now() + timedelta(hours=4),
                course_id=os_course.id
            )
            live3 = LiveClass(
                title="Database Systems Normalization Q&A",
                description="Review session on 1NF, 2NF, 3NF, and BCNF structures ahead of the exam.",
                meeting_link="https://meet.google.com/uvw-xyza-bcd",
                scheduled_time=datetime.now() + timedelta(days=1),
                course_id=db_course.id
            )
            
            # Past classes with recordings and AI summaries
            live_past1 = LiveClass(
                title="Python Basics & Variables Review",
                description="Review of primitive types, variables, and expressions in Python.",
                meeting_link="https://meet.google.com/abc-defg-hij",
                scheduled_time=datetime.now() - timedelta(days=3),
                course_id=python_course.id,
                recording_url="https://www.w3schools.com/html/mov_bbb.mp4",
                ai_summary="### Lecture Summary: Python Variables & Types\n\n1. **Dynamic Typing**: Explored how Python dynamically sets type based on assignment.\n2. **Type Casting**: Studied type conversion using `int()`, `float()`, `str()`.\n3. **String Interpolation**: Reviewed old format strings and modern f-strings."
            )
            live_past2 = LiveClass(
                title="Operating Systems Process Life Cycle",
                description="Detailed review of Process States, PCB, and Context Switching.",
                meeting_link="https://meet.google.com/klm-nopq-rst",
                scheduled_time=datetime.now() - timedelta(days=2),
                course_id=os_course.id,
                recording_url="https://www.w3schools.com/html/movie.mp4",
                ai_summary="### Lecture Summary: Process Management & Life Cycle\n\n- **Process States**: Active, Blocked, Ready, Terminated.\n- **Process Control Block (PCB)**: Memory footprint of processes, registers, and program counters.\n- **Context Switching**: The mechanical overhead of register swaps."
            )
            
            db.session.add_all([live1, live2, live3, live_past1, live_past2])
            db.session.commit()
            print("Live classes seeded successfully.")
        
    # Seed Badges
    if Badge.query.count() == 0:
        b1 = Badge(name="Syllabus Explorer", description="Viewed course syllabus and guidelines", icon_code="📖")
        b2 = Badge(name="First Submission", description="Submitted your first assignment", icon_code="🚀")
        b3 = Badge(name="Quiz Master", description="Scored 100% on any quiz", icon_code="🏆")
        b4 = Badge(name="Community Voice", description="Posted a thread in the classroom forum", icon_code="💬")
        db.session.add_all([b1, b2, b3, b4])
        db.session.commit()
        
    # Ensure Self-Learning badges are present
    sl_badges = [
        ("AI Trailblazer", "Used AI Tutor 5 times to study course content", "🤖"),
        ("Streak Master", "Reached a 7-day learning streak", "🔥"),
        ("Quiz Conqueror", "Scored 100% on 3 AI-generated practice quizzes", "🧠")
    ]
    for b_name, b_desc, b_icon in sl_badges:
        badge_exists = Badge.query.filter_by(name=b_name).first()
        if not badge_exists:
            new_b = Badge(name=b_name, description=b_desc, icon_code=b_icon)
            db.session.add(new_b)
    db.session.commit()
    print("Database seeded successfully.")


# Initialize Database and Seed Data if empty
with app.app_context():
    # Ensure certificates has the is_approved column
    from sqlalchemy import text
    try:
        db.session.execute(text("ALTER TABLE certificates ADD COLUMN is_approved BOOLEAN DEFAULT FALSE"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        
    new_user_cols = [
        ("is_verified", "BOOLEAN DEFAULT FALSE"),
        ("verification_otp", "VARCHAR(10) DEFAULT NULL"),
        ("verification_otp_expiry", "DATETIME DEFAULT NULL"),
        ("two_factor_otp", "VARCHAR(10) DEFAULT NULL"),
        ("two_factor_otp_expiry", "DATETIME DEFAULT NULL"),
        ("is_approved_by_admin", "BOOLEAN DEFAULT FALSE"),
        ("failed_login_attempts", "INTEGER DEFAULT 0"),
        ("lockout_until", "DATETIME DEFAULT NULL"),
        ("microsoft_id", "VARCHAR(100) DEFAULT NULL"),
        ("login_streak", "INTEGER DEFAULT 1"),
        ("last_login_date", "DATE DEFAULT NULL"),
        ("ai_queries_count", "INTEGER DEFAULT 0"),
        ("personalized_roadmap", "TEXT DEFAULT NULL"),
        ("bookmarks_json", "TEXT DEFAULT NULL"),
        ("registration_number", "VARCHAR(50) UNIQUE DEFAULT NULL")
    ]
    for col_name, col_type in new_user_cols:
        try:
            db.session.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
            db.session.commit()
            print(f"Migration: Added column {col_name} to users table.")
        except Exception:
            db.session.rollback()

    new_live_cols = [
        ("recording_url", "VARCHAR(300) DEFAULT NULL"),
        ("ai_summary", "TEXT DEFAULT NULL")
    ]
    for col_name, col_type in new_live_cols:
        try:
            db.session.execute(text(f"ALTER TABLE live_classes ADD COLUMN {col_name} {col_type}"))
            db.session.commit()
            print(f"Migration: Added column {col_name} to live_classes table.")
        except Exception:
            db.session.rollback()

    # Re-verify and create tables (e.g. audit_logs)
    db.create_all()
    
    # Ensure uploads folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        
    # Call database seeding (courses disabled on startup by default)
    seed_database(seed_courses=False)


# --- SECURITY HELPERS ---
import re
import random

def validate_email_format(email):
    email_regex = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    return re.match(email_regex, email) is not None

def is_disposable_email(email):
    if '@' not in email:
        return True
    domain = email.split('@')[1].lower()
    disposable_domains = {'tempmail.com', '10minutemail.com', 'guerrillamail.com'}
    return domain in disposable_domains

def validate_password_strength(password):
    strong_password = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$"
    return re.match(strong_password, password) is not None

def generate_captcha():
    from flask import session
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    session['captcha_answer'] = str(a + b)
    return f"{a} + {b}"

def verify_captcha(user_input):
    if app.config.get('TESTING'):
        return True
    from flask import session
    stored = session.get('captcha_answer')
    if stored is None or user_input is None:
        return False
    session.pop('captcha_answer', None)
    return str(user_input).strip() == stored.strip()

def log_security_event(user_id, action):
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
        ua = request.headers.get('User-Agent', '')
        log = AuditLog(user_id=user_id, action=action, ip_address=ip, user_agent=ua)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Failed to log security event: {e}")
        db.session.rollback()


def send_otp_email(to_email, otp, purpose="verification", reset_link=None):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import threading
    import urllib.request
    import urllib.parse
    import json
    
    resend_api_key = app.config.get('RESEND_API_KEY')
    brevo_api_key = app.config.get('BREVO_API_KEY')
    mail_server = app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(app.config.get('MAIL_PORT', 465))
    mail_use_tls = app.config.get('MAIL_USE_TLS', 'True') == 'True'
    mail_username = app.config.get('MAIL_USERNAME', 'inkbitdigitalstudio@gmail.com')
    mail_password = app.config.get('MAIL_PASSWORD', '')
    mail_sender = app.config.get('MAIL_DEFAULT_SENDER', 'onboarding@resend.dev')
    
    subject_map = {
        "verification": "Verify your InkBit LMS Account",
        "2fa": "InkBit LMS - 2FA Security Code",
        "reset": "Reset your InkBit LMS Password"
    }
    title_map = {
        "verification": "Confirm Your Email Address",
        "2fa": "Two-Factor Security Code",
        "reset": "Password Reset Request"
    }
    desc_map = {
        "verification": "Thank you for registering at InkBit LMS. Please use the verification code below to activate your account. This code is valid for 15 minutes.",
        "2fa": "A sign-in attempt requires Two-Factor Authentication (2FA). Use the code below to complete your login. This code is valid for 10 minutes.",
        "reset": "We received a request to reset your InkBit LMS account password. Click the button below to reset it directly, or enter the 6-digit code manually. This link and code are valid for 15 minutes."
    }
    
    subject = subject_map.get(purpose, "InkBit LMS Verification Code")
    title = title_map.get(purpose, "Verification Code")
    description = desc_map.get(purpose, "Please use the code below to verify your identity.")
    
    extra_content = ""
    if purpose == "reset" and reset_link:
        extra_content = f"""
                            <div style="margin: 24px 0; text-align: center;">
                                <a href="{reset_link}" style="background-color: #38bdf8; color: #0d1224; padding: 14px 28px; border-radius: 8px; font-weight: 700; text-decoration: none; display: inline-block; font-size: 16px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25);">Reset Password Directly</a>
                            </div>
                            <p style="font-size: 14px; color: #64748b; text-align: center; margin-top: 0; margin-bottom: 24px;">— OR —</p>
        """
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f6f9; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" bgcolor="#f4f6f9" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f4f6f9; margin: 0; padding: 40px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="width: 600px; max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e1e8ed; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.05); text-align: left;">
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e2640 0%, #0d1224 100%); padding: 40px 20px; text-align: center;">
                            <h1 style="font-size: 28px; font-weight: 800; color: #ffffff; text-transform: uppercase; letter-spacing: 2px; margin: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">Ink<span style="color: #38bdf8;">Bit</span> LMS</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px; line-height: 1.6; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #2b3a4a;">
                            <h2 style="font-size: 22px; font-weight: 700; color: #0f172a; margin-top: 0; margin-bottom: 16px;">{title}</h2>
                            <p style="font-size: 15px; color: #475569; margin-bottom: 24px;">{description}</p>
                            {extra_content}
                            <div style="background-color: #f1f5f9; border-radius: 8px; padding: 24px; text-align: center; margin-bottom: 24px; border: 1px dashed #cbd5e1;">
                                <div style="font-size: 36px; font-weight: 800; letter-spacing: 6px; color: #0f172a; margin: 0;">{otp}</div>
                            </div>
                            <p style="font-size: 15px; color: #475569; margin-bottom: 24px;">If you did not make this request, please ignore this email or contact support if you have concerns.</p>
                            <p style="font-size: 12px; color: #94a3b8; margin-top: 16px; font-style: italic;">Security warning: Never share this OTP code with anyone, including LMS staff.</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color: #f8fafc; padding: 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
                            <p style="margin: 4px 0;">&copy; 2026 InkBit LMS Digital Studio. All rights reserved.</p>
                            <p style="margin: 4px 0;">Designed for premium academic experiences.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    
    if brevo_api_key:
        def _send_brevo():
            try:
                url = "https://api.brevo.com/v3/smtp/email"
                headers = {
                    "api-key": brevo_api_key,
                    "Content-Type": "application/json",
                    "accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                payload = json.dumps({
                    "sender": {
                        "name": "InkBit LMS",
                        "email": mail_sender
                    },
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "htmlContent": html_content
                }).encode('utf-8')
                
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as res:
                    res_body = json.loads(res.read().decode('utf-8'))
                    print(f"[BREVO SUCCESS] Sent OTP email to {to_email}. Message ID: {res_body.get('messageId')}")
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, 'read'):
                    try:
                        err_msg += f" - Response: {e.read().decode('utf-8')}"
                    except Exception:
                        pass
                print(f"[BREVO ERROR] Failed to send email to {to_email}: {err_msg}")
                
        threading.Thread(target=_send_brevo).start()
        return True

    if resend_api_key and resend_api_key.startswith('re_'):
        def _send_resend():
            try:
                url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                payload = json.dumps({
                    "from": mail_sender,
                    "to": to_email,
                    "subject": subject,
                    "html": html_content
                }).encode('utf-8')
                
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as res:
                    res_body = json.loads(res.read().decode('utf-8'))
                    print(f"[RESEND SUCCESS] Sent OTP email to {to_email}. Email ID: {res_body.get('id')}")
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, 'read'):
                    try:
                        err_msg += f" - Response: {e.read().decode('utf-8')}"
                    except Exception:
                        pass
                print(f"[RESEND ERROR] Failed to send email to {to_email}: {err_msg}")
                
        threading.Thread(target=_send_resend).start()
        return True
        
    if not mail_password:
        print(f"[MAIL SIMULATOR] (No App Password configured) Sent email to {to_email}. OTP: {otp} for {purpose}")
        return True
        
    def _send_thread():
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = mail_sender
            msg['To'] = to_email
            msg.attach(MIMEText(html_content, 'html'))
            
            if mail_port == 465:
                server = smtplib.SMTP_SSL(mail_server, mail_port, timeout=5)
            else:
                server = smtplib.SMTP(mail_server, mail_port, timeout=5)
                if mail_use_tls:
                    server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(mail_sender, [to_email], msg.as_string())
            server.quit()
            print(f"[MAIL SUCCESS] Successfully sent OTP email to {to_email} for {purpose}")
        except Exception as e:
            print(f"[MAIL ERROR] Failed to send email to {to_email}: {e}")
            
    threading.Thread(target=_send_thread).start()
    return True


def send_login_notification_email(user, is_first_time, ip_address, user_agent, login_time):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import threading
    import urllib.request
    import urllib.parse
    import json
    
    resend_api_key = app.config.get('RESEND_API_KEY')
    brevo_api_key = app.config.get('BREVO_API_KEY')
    mail_server = app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(app.config.get('MAIL_PORT', 465))
    mail_use_tls = app.config.get('MAIL_USE_TLS', 'True') == 'True'
    mail_username = app.config.get('MAIL_USERNAME', 'inkbitdigitalstudio@gmail.com')
    mail_password = app.config.get('MAIL_PASSWORD', '')
    mail_sender = app.config.get('MAIL_DEFAULT_SENDER', 'onboarding@resend.dev')
    
    # Extract details in main thread to avoid session detachment in background thread
    user_name = user.name
    user_email = user.email
    user_role = user.role
    
    if is_first_time:
        subject = f"Welcome to InkBit LMS - Congratulations on your first login!"
        title = f"Congratulations, {user_name}! 🎉"
        description = f"Welcome to InkBit LMS. We are absolutely thrilled to have you join our digital learning studio. Your account is now fully active, and this email confirms your first successful login!"
    else:
        subject = f"InkBit LMS - New Sign-in Detected"
        title = "New Sign-in Detected"
        description = f"Hi {user_name}, this is a security notification to let you know that a new sign-in was detected for your InkBit LMS account."

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f6f9; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" bgcolor="#f4f6f9" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f4f6f9; margin: 0; padding: 40px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="width: 600px; max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e1e8ed; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.05); text-align: left;">
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e2640 0%, #0d1224 100%); padding: 40px 20px; text-align: center;">
                            <h1 style="font-size: 28px; font-weight: 800; color: #ffffff; text-transform: uppercase; letter-spacing: 2px; margin: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">Ink<span style="color: #38bdf8;">Bit</span> LMS</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px; line-height: 1.6; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #2b3a4a;">
                            <h2 style="font-size: 22px; font-weight: 700; color: #0f172a; margin-top: 0; margin-bottom: 16px;">{title}</h2>
                            <p style="font-size: 15px; color: #475569; margin-bottom: 24px;">{description}</p>
                            
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; padding: 20px; margin-bottom: 24px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; border-bottom: 1px solid #f1f5f9; font-size: 14px; width: 35%;">Name</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; border-bottom: 1px solid #f1f5f9; font-size: 14px; word-break: break-all;">{user_name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; border-bottom: 1px solid #f1f5f9; font-size: 14px;">Email</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; border-bottom: 1px solid #f1f5f9; font-size: 14px; word-break: break-all;">{user_email}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; border-bottom: 1px solid #f1f5f9; font-size: 14px;">Role</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; border-bottom: 1px solid #f1f5f9; font-size: 14px; word-break: break-all;">{user_role.capitalize()}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; border-bottom: 1px solid #f1f5f9; font-size: 14px;">Login Time</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; border-bottom: 1px solid #f1f5f9; font-size: 14px; word-break: break-all;">{login_time}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; border-bottom: 1px solid #f1f5f9; font-size: 14px;">IP Address</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; border-bottom: 1px solid #f1f5f9; font-size: 14px; word-break: break-all;">{ip_address}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; font-size: 14px;">Device / Browser</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; font-size: 14px; word-break: break-all;">{user_agent}</td>
                                </tr>
                            </table>

                            {"<p style='font-size: 13px; color: #ef4444; margin-top: 16px; font-weight: 500;'>Security Alert: If this login was not made by you, please change your password immediately in your account settings.</p>" if not is_first_time else "<p style='font-size: 15px; color: #475569;'>We hope you enjoy your time learning and teaching on our platform!</p>"}
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color: #f8fafc; padding: 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
                            <p style="margin: 4px 0;">&copy; 2026 InkBit LMS Digital Studio. All rights reserved.</p>
                            <p style="margin: 4px 0;">Designed for premium academic experiences.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    if brevo_api_key:
        def _send_brevo():
            try:
                url = "https://api.brevo.com/v3/smtp/email"
                headers = {
                    "api-key": brevo_api_key,
                    "Content-Type": "application/json",
                    "accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                payload = json.dumps({
                    "sender": {
                        "name": "InkBit LMS",
                        "email": mail_sender
                    },
                    "to": [{"email": user_email}],
                    "subject": subject,
                    "htmlContent": html_content
                }).encode('utf-8')
                
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as res:
                    res_body = json.loads(res.read().decode('utf-8'))
                    print(f"[BREVO SUCCESS] Sent login notification to {user_email}. Message ID: {res_body.get('messageId')}")
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, 'read'):
                    try:
                        err_msg += f" - Response: {e.read().decode('utf-8')}"
                    except Exception:
                        pass
                print(f"[BREVO ERROR] Failed to send login notification to {user_email}: {err_msg}")
                
        threading.Thread(target=_send_brevo).start()
        return True

    if resend_api_key and resend_api_key.startswith('re_'):
        def _send_resend():
            try:
                url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                payload = json.dumps({
                    "from": mail_sender,
                    "to": user_email,
                    "subject": subject,
                    "html": html_content
                }).encode('utf-8')
                
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as res:
                    res_body = json.loads(res.read().decode('utf-8'))
                    print(f"[RESEND SUCCESS] Sent login notification to {user_email}. Email ID: {res_body.get('id')}")
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, 'read'):
                    try:
                        err_msg += f" - Response: {e.read().decode('utf-8')}"
                    except Exception:
                        pass
                print(f"[RESEND ERROR] Failed to send login notification to {user_email}: {err_msg}")
                
        threading.Thread(target=_send_resend).start()
        return True

    if not mail_password:
        print(f"[MAIL SIMULATOR] (No App Password) Sent login details email to {user_email}. First Login: {is_first_time}")
        return True
        
    def _send_thread():
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = mail_sender
            msg['To'] = user_email
            msg.attach(MIMEText(html_content, 'html'))
            
            if mail_port == 465:
                server = smtplib.SMTP_SSL(mail_server, mail_port, timeout=5)
            else:
                server = smtplib.SMTP(mail_server, mail_port, timeout=5)
                if mail_use_tls:
                    server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(mail_sender, [user_email], msg.as_string())
            server.quit()
            print(f"[MAIL SUCCESS] Sent login notification to {user_email} (First time: {is_first_time})")
        except Exception as e:
            print(f"[MAIL ERROR] Failed to send login notification to {user_email}: {e}")
            
    threading.Thread(target=_send_thread).start()
    return True


def send_welcome_congratulations_email(user):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import threading
    import urllib.request
    import urllib.parse
    import json
    
    resend_api_key = app.config.get('RESEND_API_KEY')
    brevo_api_key = app.config.get('BREVO_API_KEY')
    mail_server = app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(app.config.get('MAIL_PORT', 465))
    mail_use_tls = app.config.get('MAIL_USE_TLS', 'True') == 'True'
    mail_username = app.config.get('MAIL_USERNAME', 'inkbitdigitalstudio@gmail.com')
    mail_password = app.config.get('MAIL_PASSWORD', '')
    mail_sender = app.config.get('MAIL_DEFAULT_SENDER', 'onboarding@resend.dev')
    
    # Extract details in main thread to avoid session detachment in background thread
    user_name = user.name
    user_email = user.email
    user_role = user.role
    
    subject = "Congratulations on Creating Your InkBit LMS Account! 🎉"
    title = f"Welcome to the Studio, {user_name}! 🚀"
    description = "We are absolutely thrilled to welcome you to InkBit LMS. Your email address has been successfully verified, and your account is now fully activated!"
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f6f9; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" bgcolor="#f4f6f9" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f4f6f9; margin: 0; padding: 40px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="width: 600px; max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e1e8ed; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.05); text-align: left;">
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e2640 0%, #0d1224 100%); padding: 40px 20px; text-align: center;">
                            <h1 style="font-size: 28px; font-weight: 800; color: #ffffff; text-transform: uppercase; letter-spacing: 2px; margin: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">Ink<span style="color: #38bdf8;">Bit</span> LMS</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px; line-height: 1.6; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #2b3a4a;">
                            <h2 style="font-size: 22px; font-weight: 700; color: #0f172a; margin-top: 0; margin-bottom: 16px;">{title}</h2>
                            <p style="font-size: 15px; color: #475569; margin-bottom: 24px;">{description}</p>
                            
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; padding: 20px; margin-bottom: 24px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; border-bottom: 1px solid #f1f5f9; font-size: 14px; width: 35%;">Name</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; border-bottom: 1px solid #f1f5f9; font-size: 14px; word-break: break-all;">{user_name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; border-bottom: 1px solid #f1f5f9; font-size: 14px;">Email</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; border-bottom: 1px solid #f1f5f9; font-size: 14px; word-break: break-all;">{user_email}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px 0; font-weight: 600; color: #64748b; font-size: 14px;">Account Role</td>
                                    <td style="padding: 10px 0; color: #0f172a; text-align: right; font-size: 14px; word-break: break-all;">{user_role.capitalize()}</td>
                                </tr>
                            </table>
                            <p style='font-size: 15px; color: #475569;'>You can now log in to access your dashboard, explore your courses, join live lectures, and track your learning achievements.</p>
                            <p style='font-size: 15px; color: #475569;'>Welcome aboard!</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color: #f8fafc; padding: 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
                            <p style="margin: 4px 0;">&copy; 2026 InkBit LMS Digital Studio. All rights reserved.</p>
                            <p style="margin: 4px 0;">Designed for premium academic experiences.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    if brevo_api_key:
        def _send_brevo():
            try:
                url = "https://api.brevo.com/v3/smtp/email"
                headers = {
                    "api-key": brevo_api_key,
                    "Content-Type": "application/json",
                    "accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                payload = json.dumps({
                    "sender": {
                        "name": "InkBit LMS",
                        "email": mail_sender
                    },
                    "to": [{"email": user_email}],
                    "subject": subject,
                    "htmlContent": html_content
                }).encode('utf-8')
                
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as res:
                    res_body = json.loads(res.read().decode('utf-8'))
                    print(f"[BREVO SUCCESS] Sent welcome email to {user_email}. Message ID: {res_body.get('messageId')}")
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, 'read'):
                    try:
                        err_msg += f" - Response: {e.read().decode('utf-8')}"
                    except Exception:
                        pass
                print(f"[BREVO ERROR] Failed to send welcome email to {user_email}: {err_msg}")
                
        threading.Thread(target=_send_brevo).start()
        return True

    if resend_api_key and resend_api_key.startswith('re_'):
        def _send_resend():
            try:
                url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                payload = json.dumps({
                    "from": mail_sender,
                    "to": user_email,
                    "subject": subject,
                    "html": html_content
                }).encode('utf-8')
                
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as res:
                    res_body = json.loads(res.read().decode('utf-8'))
                    print(f"[RESEND SUCCESS] Sent welcome email to {user_email}. Email ID: {res_body.get('id')}")
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, 'read'):
                    try:
                        err_msg += f" - Response: {e.read().decode('utf-8')}"
                    except Exception:
                        pass
                print(f"[RESEND ERROR] Failed to send welcome email to {user_email}: {err_msg}")
                
        threading.Thread(target=_send_resend).start()
        return True

    if not mail_password:
        print(f"[MAIL SIMULATOR] (No App Password) Sent welcome details email to {user_email}.")
        return True
        
    def _send_thread():
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = mail_sender
            msg['To'] = user_email
            msg.attach(MIMEText(html_content, 'html'))
            
            if mail_port == 465:
                server = smtplib.SMTP_SSL(mail_server, mail_port, timeout=5)
            else:
                server = smtplib.SMTP(mail_server, mail_port, timeout=5)
                if mail_use_tls:
                    server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(mail_sender, [user_email], msg.as_string())
            server.quit()
            print(f"[MAIL SUCCESS] Sent welcome notification to {user_email}")
        except Exception as e:
            print(f"[MAIL ERROR] Failed to send welcome notification to {user_email}: {e}")
            
    threading.Thread(target=_send_thread).start()
    return True


def notify_user_login(user):
    # 1. Count existing successful logins
    login_count = AuditLog.query.filter(
        AuditLog.user_id == user.id,
        AuditLog.action.in_(['LOGIN_SUCCESS', '2FA_VERIFIED_SUCCESS', 'GOOGLE_LOGIN_SUCCESS', 'MICROSOFT_LOGIN_SUCCESS'])
    ).count()
    
    # 2. Get login details
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    ua = request.headers.get('User-Agent', '')
    login_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # 3. Check if first successful login
    is_first = (login_count == 0)
    
    # 4. Send email
    send_login_notification_email(user, is_first, ip, ua, login_time)


# --- TELEGRAM HELPER AND SETTINGS ---


def send_telegram_alert(user, text):
    if not user or not user.telegram_notifications or not user.telegram_chat_id:
        return False
    
    token = app.config.get('TELEGRAM_BOT_TOKEN')
    if not token:
        return False
        
    import urllib.request
    import urllib.parse
    try:
        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = urllib.parse.urlencode({
            'chat_id': user.telegram_chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }).encode('utf-8')
        
        req = urllib.request.Request(send_url, data=payload, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode())
            return res_data.get('ok')
    except Exception as e:
        print(f"Error sending custom Telegram notification: {e}")
        return False

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        name = request.form.get('name')
        bio = request.form.get('bio')
        theme = request.form.get('theme', 'dark-glass')
        telegram_notifications = request.form.get('telegram_notifications') == 'on'
        telegram_chat_id = request.form.get('telegram_chat_id', '').strip() or None
        
        # Social media inputs
        whatsapp = request.form.get('whatsapp', '').strip() or None
        instagram = request.form.get('instagram', '').strip() or None
        telegram = request.form.get('telegram', '').strip() or None
        linkedin = request.form.get('linkedin', '').strip() or None
        
        # Handle profile photo upload
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S_')
                    saved_filename = timestamp + filename
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
                    current_user.profile_photo = saved_filename
                else:
                    flash("Unsupported profile photo file extension.", "danger")
        
        # Update user object
        current_user.name = name
        current_user.profile_bio = bio
        current_user.preferred_theme = theme
        current_user.telegram_notifications = telegram_notifications
        current_user.telegram_chat_id = telegram_chat_id
        current_user.social_whatsapp = whatsapp
        current_user.social_instagram = instagram
        current_user.social_telegram = telegram
        current_user.social_linkedin = linkedin
        db.session.commit()
        
        flash("Your settings have been saved successfully!", "success")
        
        # Test telegram connection if enabled
        if telegram_notifications and telegram_chat_id:
            send_telegram_alert(current_user, "🔔 *Telegram notifications linked successfully to INKBIT LMS!*")
            
        return redirect(url_for('settings'))
        
    return render_template('settings.html', active_page='settings')


@app.route('/api/settings/theme', methods=['POST'])
@login_required
def update_theme():
    data = request.get_json() or {}
    theme = data.get('theme')
    if theme in ['dark-glass', 'theme-cyberpunk', 'theme-emerald']:
        current_user.preferred_theme = theme
        db.session.commit()
        return {"success": True, "theme": theme}
    return {"success": False, "error": "Invalid theme"}, 400


@app.route('/api/telegram/discover-chat-id')
@login_required
def discover_chat_id():
    import urllib.request
    token = app.config.get('TELEGRAM_BOT_TOKEN')
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data.get('ok') and data.get('result'):
                # Search for the latest message sender's chat ID
                for update in reversed(data['result']):
                    if 'message' in update:
                        chat_id = str(update['message']['chat']['id'])
                        username = update['message']['chat'].get('username', '')
                        first_name = update['message']['chat'].get('first_name', '')
                        return {'ok': True, 'chat_id': chat_id, 'username': username, 'first_name': first_name}
    except Exception as e:
        print(f"Error in discover_chat_id API: {e}")
    return {'ok': False, 'error': 'No recent messages found. Please message your bot on Telegram first, then try again.'}


@app.route('/api/calendar-events')
@login_required
def calendar_events():
    events = []
    
    # 1. Determine accessible courses based on role
    if current_user.role == 'student':
        enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
        accessible_course_ids = [e.course_id for e in enrollments if not e.course.is_paid or e.payment_status == 'paid']
    elif current_user.role == 'teacher':
        courses = Course.query.filter_by(teacher_id=current_user.id).all()
        accessible_course_ids = [c.id for c in courses]
    elif current_user.role == 'institution':
        courses = Course.query.all()
        accessible_course_ids = [c.id for c in courses]
    else:
        accessible_course_ids = []
        
    if not accessible_course_ids:
        return json.dumps([]), 200, {'Content-Type': 'application/json'}
        
    # 2. Fetch Live Classes
    live_classes = LiveClass.query.filter(LiveClass.course_id.in_(accessible_course_ids)).all()
    for live in live_classes:
        events.append({
            'id': f'live-{live.id}',
            'title': live.title,
            'course_name': live.course.name,
            'start': live.scheduled_time.isoformat(),
            'type': 'class',
            'link': live.meeting_link
        })
        
    # 3. Fetch Assignments
    assignments = Assignment.query.filter(Assignment.course_id.in_(accessible_course_ids)).all()
    for assign in assignments:
        if assign.due_date:
            events.append({
                'id': f'assign-{assign.id}',
                'title': assign.title,
                'course_name': assign.course.name,
                'start': assign.due_date.isoformat(),
                'type': 'assignment',
                'points': assign.points
            })
            
    # 4. Fetch Quizzes
    quizzes = Quiz.query.filter(Quiz.course_id.in_(accessible_course_ids)).all()
    for quiz in quizzes:
        if quiz.due_date:
            events.append({
                'id': f'quiz-{quiz.id}',
                'title': quiz.title,
                'course_name': quiz.course.name,
                'start': quiz.due_date.isoformat(),
                'type': 'quiz'
            })
            
    return json.dumps(events), 200, {'Content-Type': 'application/json'}


def get_student_course_completion(student_id, course):
    prog_rec = Progress.query.filter_by(student_id=student_id, course_id=course.id).first()
    total_mats = len(course.materials)
    total_quizzes = len(course.quizzes)
    total_assigns = len(course.assignments)
    total_tasks = total_mats + total_quizzes + total_assigns
    
    mats_viewed = prog_rec.materials_viewed if prog_rec else 0
    quizzes_taken = QuizResult.query.join(Quiz).filter(
        QuizResult.student_id == student_id,
        Quiz.course_id == course.id
    ).count()
    assigns_submitted = Submission.query.join(Assignment).filter(
        Submission.student_id == student_id,
        Assignment.course_id == course.id
    ).count()
    
    completed = mats_viewed + quizzes_taken + assigns_submitted
    pct = int((completed / total_tasks * 100)) if total_tasks > 0 else 0
    return pct, (completed >= total_tasks if total_tasks > 0 else False)


# --- CONTROLLER ROUTING ---

# Index / Route Handler
@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
        
    if current_user.role == 'teacher':
        courses = Course.query.filter_by(teacher_id=current_user.id).all()
        # Find all student enrollments across teacher's courses
        total_students = 0
        for c in courses:
            total_students += len(c.enrollments)
            
        # Find all pending submissions for teacher's courses
        course_ids = [c.id for c in courses]
        pending_submissions = Submission.query.join(Assignment).filter(
            Assignment.course_id.in_(course_ids), 
            Submission.status == 'submitted'
        ).all()
        
        # Fetch live classes scheduled today or in the future for teacher's courses
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        live_classes = LiveClass.query.filter(
            LiveClass.course_id.in_(course_ids),
            LiveClass.scheduled_time >= today_start
        ).order_by(LiveClass.scheduled_time.asc()).all() if course_ids else []
        
        # Fetch unique students enrolled in the teacher's courses
        students = []
        if course_ids:
            enrollments = Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).all()
            student_map = {}
            for e in enrollments:
                student = e.student
                if student.id not in student_map:
                    student_map[student.id] = {
                        'student': student,
                        'enrollment_details': []
                    }
                
                # Calculate progress and certificate status
                progress_pct, is_finished = get_student_course_completion(student.id, e.course)
                cert = Certificate.query.filter_by(student_id=student.id, course_id=e.course.id).first()
                cert_status = 'none'
                if cert:
                    cert_status = 'approved' if cert.is_approved else 'pending'
                    
                student_map[student.id]['enrollment_details'].append({
                    'course_id': e.course.id,
                    'course_name': e.course.name,
                    'course_code': e.course.code,
                    'progress_pct': progress_pct,
                    'is_finished': is_finished,
                    'cert_status': cert_status,
                    'cert_id': cert.id if cert else None
                })
            students = list(student_map.values())
        
        all_courses = Course.query.all()
        all_students = User.query.filter_by(role='student').all()
        return render_template('dashboard_teacher.html', active_page='dashboard', courses=courses, all_courses=all_courses, total_students=total_students, pending_submissions=pending_submissions, live_classes=live_classes, students=students, all_students=all_students)
    elif current_user.role == 'institution':
        total_teachers = User.query.filter_by(role='teacher').count()
        total_students = User.query.filter_by(role='student').count()
        total_courses = Course.query.count()
        total_enrollments = Enrollment.query.count()
        
        teachers = User.query.filter_by(role='teacher').all()
        students = User.query.filter_by(role='student').all()
        courses = Course.query.all()
        
        recent_submissions = Submission.query.order_by(Submission.submitted_at.desc()).limit(5).all()
        recent_materials = Material.query.order_by(Material.upload_date.desc()).limit(5).all()
        
        # Security logs for Institution Admin
        audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
        
        # Self-Learning Stats
        total_certificates = Certificate.query.count()
        total_ai_queries = db.session.query(db.func.sum(User.ai_queries_count)).scalar() or 0
        
        return render_template('dashboard_institution.html', 
                               active_page='dashboard', 
                               total_teachers=total_teachers, 
                               total_students=total_students, 
                               total_courses=total_courses, 
                               total_enrollments=total_enrollments,
                               teachers=teachers, 
                               students=students, 
                               courses=courses,
                               recent_submissions=recent_submissions,
                               recent_materials=recent_materials,
                               audit_logs=audit_logs,
                               total_certificates=total_certificates,
                               total_ai_queries=total_ai_queries)
    else:
        # Student Dashboard
        enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
        courses = [e.course for e in enrollments]
        
        # Calculate dynamic course progress & average grades
        course_progress = {}
        quizzes_completed = QuizResult.query.filter_by(student_id=current_user.id).count()
        
        # Average grade calculation
        quiz_results = QuizResult.query.filter_by(student_id=current_user.id).all()
        graded_submissions = Submission.query.filter_by(student_id=current_user.id, status='graded').all()
        
        total_scores = 0
        total_items = 0
        for qr in quiz_results:
            total_scores += qr.score
            total_items += 1
        for gs in graded_submissions:
            percentage = (gs.grade / gs.assignment.points) * 100
            total_scores += percentage
            total_items += 1
            
        average_grade = (total_scores / total_items) if total_items > 0 else None
        
        # Dynamic progress tracks
        for course in courses:
            total_mats = len(course.materials)
            total_quizzes = len(course.quizzes)
            total_assigns = len(course.assignments)
            total_tasks = total_mats + total_quizzes + total_assigns
            
            if total_tasks == 0:
                course_progress[course.id] = 100
            else:
                prog_rec = Progress.query.filter_by(student_id=current_user.id, course_id=course.id).first()
                mats_viewed = prog_rec.materials_viewed if prog_rec else 0
                
                # Fetch count of completed quizzes for this course
                quizzes_taken = QuizResult.query.join(Quiz).filter(
                    QuizResult.student_id == current_user.id,
                    Quiz.course_id == course.id
                ).count()
                
                # Fetch count of completed assignments
                assigns_submitted = Submission.query.join(Assignment).filter(
                    Submission.student_id == current_user.id,
                    Assignment.course_id == course.id
                ).count()
                
                completed = mats_viewed + quizzes_taken + assigns_submitted
                percent = int((completed / total_tasks) * 100)
                course_progress[course.id] = min(percent, 100)
        
        # Collect upcoming deadlines ("Perlu Dikerjakan")
        deadlines = []
        # Deadlines from assignments
        for course in courses:
            for assign in course.assignments:
                # Check if already submitted
                sub = Submission.query.filter_by(student_id=current_user.id, assignment_id=assign.id).first()
                if not sub:
                    deadlines.append({
                        'id': f"assign-{assign.id}",
                        'title': assign.title,
                        'due_date': assign.due_date,
                        'course_name': course.name,
                        'course_code': course.code,
                        'type': 'Assignment'
                    })
            for quiz in course.quizzes:
                # Check if already attempted
                res = QuizResult.query.filter_by(student_id=current_user.id, quiz_id=quiz.id).first()
                if not res and quiz.due_date:
                    deadlines.append({
                        'id': f"quiz-{quiz.id}",
                        'title': quiz.title,
                        'due_date': quiz.due_date,
                        'course_name': course.name,
                        'course_code': course.code,
                        'type': 'Quiz'
                    })
        # Sort deadlines chronologically
        deadlines.sort(key=lambda x: x['due_date'])
        
        # Fetch live classes scheduled today or in the future for student's enrolled, paid courses
        accessible_course_ids = [e.course_id for e in enrollments if not e.course.is_paid or e.payment_status == 'paid']
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        live_classes = LiveClass.query.filter(
            LiveClass.course_id.in_(accessible_course_ids),
            LiveClass.scheduled_time >= today_start
        ).order_by(LiveClass.scheduled_time.asc()).all() if accessible_course_ids else []
        
        return render_template('dashboard_student.html', active_page='dashboard', enrollments=enrollments, course_progress=course_progress, quizzes_completed=quizzes_completed, average_grade=average_grade, deadlines=deadlines, live_classes=live_classes)


@app.route('/guest-login')
def guest_login():
    guest_email = 'guest@inkbit.com'
    user = User.query.filter_by(email=guest_email).first()
    if not user:
        import random
        user = User(
            email=guest_email,
            name='Guest Student',
            role='student',
            is_verified=True,
            is_approved_by_admin=True,
            registration_number=f"GUEST-{random.randint(100000, 999999)}"
        )
        user.set_password('guest123')
        db.session.add(user)
        db.session.commit()
    
    # Log in the guest user
    login_user(user)
    
    # Auto-enroll in all available courses
    try:
        from models import Course, Enrollment
        courses = Course.query.all()
        for course in courses:
            existing_enrollment = Enrollment.query.filter_by(student_id=user.id, course_id=course.id).first()
            if not existing_enrollment:
                enrollment = Enrollment(
                    student_id=user.id,
                    course_id=course.id,
                    payment_status='paid'  # Grant full access for testing/free edu demo
                )
                db.session.add(enrollment)
        db.session.commit()
    except Exception as e:
        print(f"Error enrolling guest student: {e}")
        db.session.rollback()

    flash("Welcome to the Free Education Hub! You are logged in as a guest.", "success")
    return redirect(url_for('self_learning'))


# Auth Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        captcha_ans = request.form.get('captcha_answer', '')
        
        # 1. Verify CAPTCHA
        if not verify_captcha(captcha_ans):
            flash("Invalid CAPTCHA answer. Please try again.", "danger")
            captcha_quest = generate_captcha()
            return render_template('login.html', captcha_question=captcha_quest)
            
        user = User.query.filter_by(email=email).first()
        if user:
            # 2. Check Lockout
            if user.lockout_until:
                # If lockout expired
                if user.lockout_until.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                    user.failed_login_attempts = 0
                    user.lockout_until = None
                    db.session.commit()
                else:
                    diff = user.lockout_until.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
                    mins = int(diff.total_seconds() / 60) + 1
                    flash(f"This account is locked. Please try again in {mins} minutes.", "danger")
                    log_security_event(user.id, "LOGIN_BLOCKED_LOCKOUT")
                    captcha_quest = generate_captcha()
                    return render_template('login.html', captcha_question=captcha_quest)

            if user.check_password(password):
                # Password correct - reset failure counter
                user.failed_login_attempts = 0
                user.lockout_until = None
                db.session.commit()

                # 3. Check Email Verification
                if not user.is_verified:
                    from flask import session
                    session['pending_verify_email'] = user.email
                    # Regenerate verification OTP
                    import random
                    otp = f"{random.randint(100000, 999999)}"
                    user.verification_otp = otp
                    user.verification_otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
                    db.session.commit()
                    print(f"[SECURITY VERIFICATION] Generated email verification OTP: {otp} for {user.email}")
                    send_otp_email(user.email, otp, 'verification')
                    
                    flash("Please verify your email address first.", "warning")
                    log_security_event(user.id, "LOGIN_FAILED_UNVERIFIED")
                    return redirect(url_for('verify_email'))

                # 4. Check Teacher Approval
                if user.role == 'teacher' and not user.is_approved_by_admin:
                    flash("Your tutor account is pending administrator approval.", "warning")
                    log_security_event(user.id, "LOGIN_FAILED_UNAPPROVED")
                    captcha_quest = generate_captcha()
                    return render_template('login.html', captcha_question=captcha_quest)

                # 5. Check 2FA requirement (Tutors & Admins)
                if user.role in ['teacher', 'institution'] and (not app.config.get('TESTING') or app.config.get('TEST_2FA')) and user.last_login_date is not None:
                    from flask import session
                    import random
                    otp = f"{random.randint(100000, 999999)}"
                    user.two_factor_otp = otp
                    user.two_factor_otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
                    db.session.commit()
                    
                    session['2fa_user_id'] = user.id
                    print(f"[SECURITY 2FA] Generated 2FA OTP: {otp} for {user.email}")
                    log_security_event(user.id, "2FA_OTP_GENERATED")
                    send_otp_email(user.email, otp, '2fa')
                    
                    flash("Two-Factor Authentication required. Enter the 6-digit OTP code.", "info")
                    return redirect(url_for('login_2fa'))

                # Direct login
                notify_user_login(user)
                user.last_login_date = datetime.now(timezone.utc).date()
                db.session.commit()
                login_user(user)
                log_security_event(user.id, "LOGIN_SUCCESS")
                flash(f"Welcome back, {user.name}!", "success")
                return redirect(url_for('index'))
            else:
                # Password incorrect - increment failed attempts
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.lockout_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                    flash("Your account has been locked for 15 minutes due to multiple failed login attempts.", "danger")
                    log_security_event(user.id, "ACCOUNT_LOCKED")
                else:
                    flash(f"Invalid email or password. Attempt {user.failed_login_attempts} of 5.", "danger")
                    log_security_event(user.id, "LOGIN_FAILED_BAD_PASSWORD")
                db.session.commit()
        else:
            flash("Invalid email or password.", "danger")
            log_security_event(None, "LOGIN_FAILED_UNKNOWN_USER")
            
    captcha_quest = generate_captcha()
    return render_template('login.html', captcha_question=captcha_quest)


@app.route('/register', methods=['GET', 'POST'])
def register():
    is_admin = current_user.is_authenticated and current_user.role == 'institution'
    
    if not is_admin and not app.config.get('TESTING'):
        flash("Public registration is disabled. Accounts can only be created by the institution administrator.", "warning")
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'student')
        captcha_ans = request.form.get('captcha_answer', '')
        registration_number = request.form.get('registration_number', '').strip()
        
        # 1. Verify CAPTCHA
        if not is_admin and not verify_captcha(captcha_ans):
            flash("Invalid CAPTCHA answer. Please try again.", "danger")
            captcha_quest = generate_captcha()
            return render_template('register.html', captcha_question=captcha_quest)

        # 2. Block public teacher or institution admin registration
        if role in ['teacher', 'institution'] and not is_admin:
            flash("Tutor and Institution accounts can only be created by existing administrators.", "danger")
            captcha_quest = generate_captcha()
            return render_template('register.html', captcha_question=captcha_quest)

        # 3. Validate Email Format
        if not validate_email_format(email):
            flash("Invalid email format. E.g. name@domain.com", "danger")
            captcha_quest = generate_captcha()
            return render_template('register.html', captcha_question=captcha_quest)

        # 4. Block Disposable Emails
        if is_disposable_email(email):
            flash("Registration failed: Disposable email services are blocked.", "danger")
            captcha_quest = generate_captcha()
            return render_template('register.html', captcha_question=captcha_quest)

        # 5. Strong Password Policy
        if not validate_password_strength(password):
            flash("Password must be at least 8 characters long and contain at least 1 uppercase letter, 1 lowercase letter, 1 number, and 1 special character (@$!%*?&).", "danger")
            captcha_quest = generate_captcha()
            return render_template('register.html', captcha_question=captcha_quest)
        
        # 6. Validate Registration Number for Students
        if role == 'student' and not registration_number:
            flash("Registration number is required for students.", "danger")
            if is_admin:
                return redirect(url_for('index'))
            captcha_quest = generate_captcha()
            return render_template('register.html', captcha_question=captcha_quest)
            
        if registration_number:
            existing_reg = User.query.filter_by(registration_number=registration_number).first()
            if existing_reg:
                flash(f"Registration number '{registration_number}' is already assigned to another student.", "danger")
                if is_admin:
                    return redirect(url_for('index'))
                captcha_quest = generate_captcha()
                return render_template('register.html', captcha_question=captcha_quest)
        
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            log_security_event(None, f"REGISTRATION_FAILED_EMAIL_TAKEN: {email}")
        else:
            if is_admin:
                # Created by admin -> auto-verified, auto-approved
                user = User(email=email, name=name, role=role, is_verified=True, is_approved_by_admin=True, registration_number=registration_number if role == 'student' else None)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                log_security_event(current_user.id, f"ADMIN_CREATED_USER: {email} ({role})")
                send_welcome_congratulations_email(user)
                flash(f"User {name} registered successfully as {role.capitalize()}.", "success")
                return redirect(url_for('index'))
            else:
                # Public self-registration
                import random
                otp = f"{random.randint(100000, 999999)}"
                user = User(
                    email=email, 
                    name=name, 
                    role=role, 
                    is_verified=False,
                    is_approved_by_admin=True if role == 'student' else False, # student is auto-approved, teacher requires admin approval
                    verification_otp=otp,
                    verification_otp_expiry=datetime.now(timezone.utc) + timedelta(minutes=15),
                    registration_number=registration_number if role == 'student' else None
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                
                from flask import session
                session['pending_verify_email'] = email
                print(f"[SECURITY VERIFICATION] Generated registration OTP: {otp} for {email}")
                log_security_event(user.id, "USER_REGISTERED_PENDING_VERIFY")
                send_otp_email(email, otp, 'verification')
                
                flash("Registration successful! Please verify your email with the OTP code.", "info")
                return redirect(url_for('verify_email'))
            
    captcha_quest = generate_captcha()
    return render_template('register.html', captcha_question=captcha_quest)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for('login'))


@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_pass = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')
    
    if not current_user.check_password(current_pass):
        flash("Incorrect current password.", "danger")
        return redirect(request.referrer or url_for('index'))
        
    if not validate_password_strength(new_pass):
        flash("New password must be at least 8 characters, containing uppercase, lowercase, numbers, and special characters.", "danger")
        return redirect(request.referrer or url_for('index'))
        
    current_user.set_password(new_pass)
    db.session.commit()
    log_security_event(current_user.id, "PASSWORD_CHANGED_BY_USER")
    flash("Your password has been changed successfully.", "success")
    return redirect(request.referrer or url_for('index'))


@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    from flask import session
    email = session.get('pending_verify_email')
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        otp = request.form.get('otp', '').strip()
        
        user = User.query.filter_by(email=email).first()
        if user:
            if user.is_verified:
                flash("Email already verified. Please sign in.", "info")
                return redirect(url_for('login'))
                
            if user.verification_otp == otp:
                if user.verification_otp_expiry and user.verification_otp_expiry.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                    user.is_verified = True
                    user.verification_otp = None
                    user.verification_otp_expiry = None
                    db.session.commit()
                    log_security_event(user.id, "EMAIL_VERIFIED")
                    send_welcome_congratulations_email(user)
                    session.pop('pending_verify_email', None)
                    flash("Email verified successfully! You can now log in.", "success")
                    return redirect(url_for('login'))
                else:
                    flash("Verification OTP has expired. Please log in again to request a new one.", "danger")
            else:
                flash("Invalid verification OTP. Please check the code and try again.", "danger")
        else:
            flash("User not found.", "danger")
            
    return render_template('verify_email.html', email=email)


@app.route('/login-2fa', methods=['GET', 'POST'])
def login_2fa():
    from flask import session
    user_id = session.get('2fa_user_id')
    if not user_id:
        flash("Invalid session. Please sign in first.", "danger")
        return redirect(url_for('login'))
        
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        if user.two_factor_otp == otp:
            if user.two_factor_otp_expiry and user.two_factor_otp_expiry.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                user.two_factor_otp = None
                user.two_factor_otp_expiry = None
                user.last_login_date = datetime.now(timezone.utc).date()
                db.session.commit()
                
                notify_user_login(user)
                login_user(user)
                session.pop('2fa_user_id', None)
                log_security_event(user.id, "2FA_VERIFIED_SUCCESS")
                flash(f"Welcome back, {user.name}!", "success")
                return redirect(url_for('index'))
            else:
                flash("2FA OTP code has expired. Please sign in again.", "danger")
                log_security_event(user.id, "2FA_FAILED_EXPIRED")
                return redirect(url_for('login'))
        else:
            flash("Invalid 2FA OTP code. Please try again.", "danger")
            log_security_event(user.id, "2FA_FAILED_BAD_OTP")
            
    return render_template('login_2fa.html', email=user.email)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()
        if user:
            import random
            from itsdangerous import URLSafeTimedSerializer
            
            otp = f"{random.randint(100000, 999999)}"
            user.verification_otp = otp
            user.verification_otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
            db.session.commit()
            
            # Generate timed token for password reset link
            s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            token = s.dumps(email, salt='password-reset-salt')
            reset_link = url_for('reset_password_link', token=token, _external=True)
            
            from flask import session
            session['pending_reset_email'] = email
            print(f"[SECURITY PASSWORD RESET] Generated reset OTP: {otp} for {email}")
            print(f"[SECURITY PASSWORD RESET] Generated secure link: {reset_link}")
            log_security_event(user.id, "PASSWORD_RESET_REQUESTED")
            
            send_otp_email(email, otp, 'reset', reset_link=reset_link)
            
            flash("If that email address is registered, a password reset link and OTP code have been sent.", "info")
            return redirect(url_for('reset_password'))
        else:
            flash("If that email address is registered, a password reset link and OTP code have been sent.", "info")
            
    return render_template('forgot_password.html')


@app.route('/reset-password-link/<token>', methods=['GET'])
def reset_password_link(token):
    from itsdangerous import URLSafeTimedSerializer
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=900) # 15 minutes expiry
    except Exception:
        flash("The password reset link is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for('forgot_password'))
        
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('forgot_password'))
        
    # Store verification details in session to auto-fill the OTP
    from flask import session
    session['pending_reset_email'] = email
    session['pending_reset_otp'] = user.verification_otp
    
    flash("Secure reset link verified! Your recovery code has been entered automatically. Please set a new password.", "success")
    return redirect(url_for('reset_password'))


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    from flask import session
    email = session.get('pending_reset_email')
    # Retrieve pre-filled OTP if they verified via secure link
    otp = session.get('pending_reset_otp')
    
    if request.method == 'POST':
        submitted_otp = request.form.get('otp', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(email=email).first()
        if user:
            if not validate_password_strength(password):
                flash("Password must be at least 8 characters long and contain at least 1 uppercase letter, 1 lowercase letter, 1 number, and 1 special character (@$!%*?&).", "danger")
                return render_template('reset_password.html', email=email, otp=otp)
                
            if user.verification_otp == submitted_otp:
                if user.verification_otp_expiry and user.verification_otp_expiry.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                    user.set_password(password)
                    user.verification_otp = None
                    user.verification_otp_expiry = None
                    db.session.commit()
                    
                    log_security_event(user.id, "PASSWORD_RESET_SUCCESS")
                    session.pop('pending_reset_email', None)
                    session.pop('pending_reset_otp', None)
                    flash("Password reset successfully! Please sign in with your new password.", "success")
                    return redirect(url_for('login'))
                else:
                    flash("Reset OTP has expired. Please request a new password reset.", "danger")
            else:
                flash("Invalid reset OTP. Please check the code and try again.", "danger")
        else:
            flash("Invalid reset session. Please request password reset again.", "danger")
            return redirect(url_for('forgot_password'))
            
    return render_template('reset_password.html', email=email, otp=otp)


@app.route('/admin/approve-teacher/<int:user_id>', methods=['POST'])
@login_required
def approve_teacher(user_id):
    if current_user.role != 'institution':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    user = db.session.get(User, user_id)
    if user and user.role == 'teacher':
        user.is_approved_by_admin = True
        db.session.commit()
        log_security_event(user.id, "TEACHER_APPROVED_BY_ADMIN")
        flash(f"Tutor {user.name} has been successfully approved and activated.", "success")
    else:
        flash("Invalid tutor or user not found.", "danger")
        
    return redirect(url_for('index') + '#tutors-section')


@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'institution':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    user = db.session.get(User, user_id)
    if user:
        if user.id == current_user.id:
            flash("You cannot delete your own institution account.", "danger")
            return redirect(url_for('index'))
            
        # Clean up database child rows to prevent foreign key errors
        Enrollment.query.filter_by(student_id=user.id).delete()
        Progress.query.filter_by(student_id=user.id).delete()
        Submission.query.filter_by(student_id=user.id).delete()
        QuizResult.query.filter_by(student_id=user.id).delete()
        Certificate.query.filter_by(student_id=user.id).delete()
        
        if user.role == 'teacher':
            courses = Course.query.filter_by(teacher_id=user.id).all()
            for course in courses:
                ForumReply.query.filter_by(user_id=user.id).delete()
                threads = ForumThread.query.filter_by(course_id=course.id).all()
                for thread in threads:
                    ForumReply.query.filter_by(thread_id=thread.id).delete()
                    db.session.delete(thread)
                LiveClass.query.filter_by(course_id=course.id).delete()
                Material.query.filter_by(course_id=course.id).delete()
                assigns = Assignment.query.filter_by(course_id=course.id).all()
                for assign in assigns:
                    Submission.query.filter_by(assignment_id=assign.id).delete()
                    db.session.delete(assign)
                quizzes = Quiz.query.filter_by(course_id=course.id).all()
                for quiz in quizzes:
                    Question.query.filter_by(quiz_id=quiz.id).delete()
                    QuizResult.query.filter_by(quiz_id=quiz.id).delete()
                    db.session.delete(quiz)
                Progress.query.filter_by(course_id=course.id).delete()
                Enrollment.query.filter_by(course_id=course.id).delete()
                Certificate.query.filter_by(course_id=course.id).delete()
                db.session.delete(course)
            db.session.commit()  # Commit course deletions first to clear foreign keys
                
        ForumReply.query.filter_by(user_id=user.id).delete()
        threads = ForumThread.query.filter_by(user_id=user.id).all()
        for thread in threads:
            ForumReply.query.filter_by(thread_id=thread.id).delete()
            db.session.delete(thread)
            
        username = user.name
        role = user.role
        db.session.delete(user)
        db.session.commit()
        log_security_event(current_user.id, f"ADMIN_DELETED_USER: {username} ({role})")
        flash(f"User {username} ({role.capitalize()}) deleted successfully.", "success")
    else:
        flash("User not found.", "danger")
        
    return redirect(url_for('index'))


# --- REAL GOOGLE AND MICROSOFT OAUTH FLOWS ---

@app.route('/login/google')
def google_login():
    from flask import session
    import secrets
    state = secrets.token_hex(16)
    session['oauth_state'] = state
    
    client_id = app.config.get('GOOGLE_CLIENT_ID')
    redirect_uri = url_for('google_callback', _external=True)
    if 'https' in request.headers.get('X-Forwarded-Proto', '') or 'pinggy' in request.host:
        redirect_uri = redirect_uri.replace('http://', 'https://')
        
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account'
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return redirect(auth_url)


@app.route('/login/google/callback')
def google_callback():
    from flask import session
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        flash(f"Google authentication error: {error}", "danger")
        return redirect(url_for('login'))
        
    if not state or state != session.get('oauth_state'):
        flash("OAuth state verification failed. Possible CSRF attack.", "danger")
        return redirect(url_for('login'))
        
    session.pop('oauth_state', None)
    
    if not code:
        flash("No authorization code returned from Google.", "danger")
        return redirect(url_for('login'))
        
    client_id = app.config.get('GOOGLE_CLIENT_ID')
    client_secret = app.config.get('GOOGLE_CLIENT_SECRET')
    
    redirect_uri = url_for('google_callback', _external=True)
    if 'https' in request.headers.get('X-Forwarded-Proto', '') or 'pinggy' in request.host:
        redirect_uri = redirect_uri.replace('http://', 'https://')
        
    token_url = "https://oauth2.googleapis.com/token"
    data = urllib.parse.urlencode({
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(token_url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req) as res:
            res_data = json.loads(res.read().decode('utf-8'))
            access_token = res_data.get('access_token')
            
        if not access_token:
            flash("Failed to obtain access token from Google.", "danger")
            return redirect(url_for('login'))
            
        # Get user details from Google userinfo endpoint
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        req = urllib.request.Request(userinfo_url, headers={'Authorization': f'Bearer {access_token}'})
        with urllib.request.urlopen(req) as res:
            user_data = json.loads(res.read().decode('utf-8'))
            
        email = user_data.get('email')
        name = user_data.get('name') or user_data.get('given_name') or "Google User"
        google_id = user_data.get('sub')
        
        if not email:
            flash("Google account does not provide an email address.", "danger")
            return redirect(url_for('login'))
            
        # Check if user already exists
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, name=name, role='student', google_id=google_id, is_verified=True)
            db.session.add(user)
            db.session.commit()
            flash("Google Account registered successfully!", "success")
        else:
            if not user.google_id:
                user.google_id = google_id
                db.session.commit()
            if not user.is_verified:
                user.is_verified = True
                db.session.commit()
                
        notify_user_login(user)
        login_user(user)
        log_security_event(user.id, "GOOGLE_LOGIN_SUCCESS")
        flash(f"Signed in via Google as {user.name}.", "success")
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"Google OAuth Exception: {e}")
        flash("An error occurred during Google authentication.", "danger")
        return redirect(url_for('login'))


@app.route('/login/microsoft')
def microsoft_login():
    from flask import session
    import secrets
    state = secrets.token_hex(16)
    session['oauth_state'] = state
    
    client_id = app.config.get('MICROSOFT_CLIENT_ID')
    redirect_uri = url_for('microsoft_callback', _external=True)
    if 'https' in request.headers.get('X-Forwarded-Proto', '') or 'pinggy' in request.host:
        redirect_uri = redirect_uri.replace('http://', 'https://')
        
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile User.Read',
        'state': state,
        'response_mode': 'query',
        'prompt': 'select_account'
    }
    auth_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)
    return redirect(auth_url)


@app.route('/login/microsoft/callback')
def microsoft_callback():
    from flask import session
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    
    if error:
        flash(f"Microsoft authentication error: {error_description or error}", "danger")
        return redirect(url_for('login'))
        
    if not state or state != session.get('oauth_state'):
        flash("OAuth state verification failed. Possible CSRF attack.", "danger")
        return redirect(url_for('login'))
        
    session.pop('oauth_state', None)
    
    if not code:
        flash("No authorization code returned from Microsoft.", "danger")
        return redirect(url_for('login'))
        
    client_id = app.config.get('MICROSOFT_CLIENT_ID')
    client_secret = app.config.get('MICROSOFT_CLIENT_SECRET')
    
    redirect_uri = url_for('microsoft_callback', _external=True)
    if 'https' in request.headers.get('X-Forwarded-Proto', '') or 'pinggy' in request.host:
        redirect_uri = redirect_uri.replace('http://', 'https://')
        
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = urllib.parse.urlencode({
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(token_url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req) as res:
            res_data = json.loads(res.read().decode('utf-8'))
            access_token = res_data.get('access_token')
            
        if not access_token:
            flash("Failed to obtain access token from Microsoft.", "danger")
            return redirect(url_for('login'))
            
        # Get user details from Microsoft Graph API
        graph_url = "https://graph.microsoft.com/v1.0/me"
        req = urllib.request.Request(graph_url, headers={'Authorization': f'Bearer {access_token}'})
        with urllib.request.urlopen(req) as res:
            user_data = json.loads(res.read().decode('utf-8'))
            
        email = user_data.get('mail') or user_data.get('userPrincipalName')
        name = user_data.get('displayName') or "Microsoft User"
        microsoft_id = user_data.get('id')
        
        if not email:
            flash("Microsoft account does not provide an email address.", "danger")
            return redirect(url_for('login'))
            
        # Check if user already exists
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, name=name, role='student', microsoft_id=microsoft_id, is_verified=True)
            db.session.add(user)
            db.session.commit()
            flash("Microsoft Account registered successfully!", "success")
        else:
            if not user.microsoft_id:
                user.microsoft_id = microsoft_id
                db.session.commit()
            if not user.is_verified:
                user.is_verified = True
                db.session.commit()
                
        notify_user_login(user)
        login_user(user)
        log_security_event(user.id, "MICROSOFT_LOGIN_SUCCESS")
        flash(f"Signed in via Microsoft as {user.name}.", "success")
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"Microsoft OAuth Exception: {e}")
        flash("An error occurred during Microsoft authentication.", "danger")
        return redirect(url_for('login'))


# --- COURSE AND CLASSROOM DETAILS ---
@app.route('/course/<int:course_id>')
@login_required
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    
    is_enrolled = False
    is_paid_enrolled = False
    cert = None
    
    if current_user.role in ['teacher', 'institution']:
        if current_user.role == 'teacher' and course.teacher_id != current_user.id:
            flash("Unauthorized action. You are not the instructor of this course.", "danger")
            return redirect(url_for('index'))
        is_enrolled = True
        is_paid_enrolled = True
    elif current_user.role == 'student':
        enrolled = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        if enrolled:
            is_enrolled = True
            if not course.is_paid or enrolled.payment_status == 'paid':
                is_paid_enrolled = True
        else:
            if not course.is_paid:
                flash("You are not enrolled in this course.", "danger")
                return redirect(url_for('index'))
                
        # Only process progress and certificates if enrolled and paid/free
        if is_paid_enrolled:
            # Update progress counter: mark materials viewed
            prog_rec = Progress.query.filter_by(student_id=current_user.id, course_id=course.id).first()
            if prog_rec:
                # Award Explorer badge if they just read all materials
                explorer_badge = Badge.query.filter_by(name="Syllabus Explorer").first()
                if explorer_badge and len(course.materials) > 0 and prog_rec.materials_viewed < len(course.materials):
                    if explorer_badge not in current_user.badges:
                        current_user.badges.append(explorer_badge)
                        flash("🏆 New Badge Unlocked: Syllabus Explorer!", "info")
                
                prog_rec.materials_viewed = len(course.materials)
                db.session.commit()
                
                # Check course completion
                total_mats = len(course.materials)
                total_quizzes = len(course.quizzes)
                total_assigns = len(course.assignments)
                total_tasks = total_mats + total_quizzes + total_assigns
                
                mats_viewed = prog_rec.materials_viewed
                quizzes_taken = QuizResult.query.join(Quiz).filter(
                    QuizResult.student_id == current_user.id,
                    Quiz.course_id == course.id
                ).count()
                assigns_submitted = Submission.query.join(Assignment).filter(
                    Submission.student_id == current_user.id,
                    Assignment.course_id == course.id
                ).count()
                
                completed = mats_viewed + quizzes_taken + assigns_submitted
                if total_tasks > 0 and completed >= total_tasks:
                    import uuid
                    existing_cert = Certificate.query.filter_by(student_id=current_user.id, course_id=course.id).first()
                    if not existing_cert:
                        cert_code = f"CERT-{uuid.uuid4().hex[:8].upper()}"
                        cert = Certificate(student_id=current_user.id, course_id=course.id, certificate_code=cert_code, is_approved=False)
                        db.session.add(cert)
                        flash("🎉 Congratulations! You completed all course requirements! Your completion certificate is now pending tutor confirmation.", "success")
                        db.session.commit()
                    else:
                        cert = existing_cert
            
    # Load dashboard stats & variables
    course_progress = {}
    submissions_map = {}
    quiz_results_map = {}
    materials_read_count = 0
    submissions_count = 0
    quizzes_passed = 0
    
    if current_user.role == 'student' and is_paid_enrolled:
        # Get certificate if exists
        cert = Certificate.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        # Get submissions
        subs = Submission.query.filter_by(student_id=current_user.id).all()
        submissions_map = {s.assignment_id: s for s in subs}
        submissions_count = len(submissions_map)
        
        # Get quiz attempts
        results = QuizResult.query.filter_by(student_id=current_user.id).all()
        quiz_results_map = {r.quiz_id: r for r in results}
        quizzes_passed = len(quiz_results_map)
        
        # Load progress track
        prog_rec = Progress.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        materials_read_count = prog_rec.materials_viewed if prog_rec else 0
        
        total_tasks = len(course.materials) + len(course.quizzes) + len(course.assignments)
        if total_tasks == 0:
            course_progress[course.id] = 100
        else:
            completed = materials_read_count + quizzes_passed + submissions_count
            course_progress[course.id] = min(int((completed / total_tasks) * 100), 100)
            
    # Always fetch threads for forum tab
    threads = ForumThread.query.filter_by(course_id=course.id).order_by(ForumThread.created_at.desc()).all()
            
    return render_template('course_detail.html', 
                           course=course, 
                           course_progress=course_progress, 
                           submissions_map=submissions_map, 
                           quiz_results_map=quiz_results_map, 
                           materials_read_count=materials_read_count, 
                           submissions_count=submissions_count, 
                           quizzes_passed=quizzes_passed,
                           is_enrolled=is_enrolled,
                           is_paid_enrolled=is_paid_enrolled,
                           cert=cert,
                           threads=threads)


# --- TEACHER ACTIONS ---
@app.route('/admin/enroll-student', methods=['POST'])
@login_required
def admin_enroll_student():
    if current_user.role not in ['teacher', 'institution']:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    student_id = request.form.get('student_id')
    course_id = request.form.get('course_id')
    
    student = db.session.get(User, student_id)
    if not student or student.role != 'student':
        flash("Student not found.", "danger")
        return redirect(url_for('index'))
        
    course = db.session.get(Course, course_id)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for('index'))
        
    if current_user.role == 'teacher' and course.teacher_id != current_user.id:
        flash("You can only enroll students in your own courses.", "danger")
        return redirect(url_for('index'))
        
    existing = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
    if existing:
        flash(f"Student {student.name} is already enrolled in {course.name}.", "warning")
        return redirect(url_for('index'))
        
    enrollment = Enrollment(student_id=student.id, course_id=course.id, payment_status='paid')
    db.session.add(enrollment)
    prog = Progress(student_id=student.id, course_id=course.id, materials_viewed=0, assignments_completed=0, quizzes_completed=0)
    db.session.add(prog)
    db.session.commit()
    
    log_security_event(current_user.id, f"ADMIN_ENROLLED_STUDENT: {student.email} in course {course.code}")
    flash(f"Successfully enrolled {student.name} in {course.name}!", "success")
    return redirect(url_for('index'))


@app.route('/course/create', methods=['POST'])
@login_required
def create_course():
    if current_user.role not in ['teacher', 'institution']:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    code = (request.form.get('course_code') or request.form.get('code', '')).strip().upper()
    name = request.form.get('course_name') or request.form.get('name')
    description = request.form.get('description')
    department = request.form.get('department')
    schedule = request.form.get('schedule')
    total_sessions_str = request.form.get('total_sessions')
    
    total_sessions = 16
    if total_sessions_str:
        try:
            total_sessions = int(total_sessions_str)
        except ValueError:
            pass
            
    if not name:
        flash("Course title is required.", "danger")
        return redirect(url_for('index'))
        
    if not code:
        flash("Course code is required.", "danger")
        return redirect(url_for('index'))
        
    teacher_id = current_user.id
    if current_user.role == 'institution':
        teacher_id = request.form.get('teacher_id')
        if not teacher_id:
            flash("Please assign a tutor for this course.", "danger")
            return redirect(url_for('index'))
        
    if Course.query.filter_by(code=code).first():
        flash("Course code already exists.", "danger")
    else:
        course = Course(
            code=code, 
            name=name, 
            description=description, 
            teacher_id=int(teacher_id),
            department=department or 'Teknik Informatika',
            schedule=schedule or 'Jumat, 20:55 - 21:45',
            total_sessions=total_sessions
        )
        db.session.add(course)
        db.session.commit()
        flash(f"Classroom {code} created successfully!", "success")
        
    return redirect(url_for('index'))


@app.route('/course/<int:course_id>/upload_material', methods=['POST'])
@login_required
def upload_material(course_id):
    if current_user.role != 'teacher':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
    title = request.form.get('title')
    description = request.form.get('description')
    
    if 'file' not in request.files:
        flash("No file part uploaded.", "danger")
        return redirect(url_for('course_detail', course_id=course.id))
        
    file = request.files['file']
    if file.filename == '':
        flash("No selected file.", "danger")
        return redirect(url_for('course_detail', course_id=course.id))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Unique prefix for filename to avoid collision
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S_')
        saved_filename = timestamp + filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
        
        material = Material(title=title, description=description, file_path=saved_filename, course_id=course.id)
        db.session.add(material)
        db.session.commit()
        
        flash("Lecture notes uploaded successfully!", "success")
    else:
        flash("Unsupported file extension.", "danger")
        
    return redirect(url_for('course_detail', course_id=course.id) + '#materials')


@app.route('/course/<int:course_id>/create_assignment', methods=['POST'])
@login_required
def create_assignment(course_id):
    if current_user.role != 'teacher':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
    title = request.form.get('title')
    description = request.form.get('description')
    points = int(request.form.get('points', 100))
    due_date_str = request.form.get('due_date')
    
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            # Fallback or silent skip
            pass
    
    # Process optional attachment file
    saved_filename = None
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S_')
            saved_filename = timestamp + filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
            
    auto_grade = True if request.form.get('auto_grade') in ['on', 'true', '1'] else False
    
    assignment = Assignment(title=title, description=description, due_date=due_date, points=points, file_path=saved_filename, course_id=course.id, auto_grade=auto_grade)
    db.session.add(assignment)
    db.session.commit()
    
    flash("Assignment published to class feed!", "success")
    return redirect(url_for('course_detail', course_id=course.id) + '#assignments')


@app.route('/assignment/grade/<int:submission_id>', methods=['POST'])
@login_required
def grade_submission(submission_id):
    if current_user.role != 'teacher':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    submission = Submission.query.get_or_404(submission_id)
    if submission.assignment.course.teacher_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
    grade = float(request.form.get('grade'))
    feedback = request.form.get('feedback')
    
    submission.grade = grade
    submission.feedback = feedback
    submission.status = 'graded'
    db.session.commit()
    
    # Notify Student via Telegram
    send_telegram_alert(
        submission.student, 
        f"🎓 *Assignment Graded!*\n\n*Class:* {submission.assignment.course.name}\n*Assignment:* {submission.assignment.title}\n*Grade:* `{grade} / {submission.assignment.points}`\n*Feedback:* {feedback}"
    )
    
    flash(f"Grade submitted for student {submission.student.name}.", "success")
    return redirect(url_for('index'))


@app.route('/course/<int:course_id>/create_quiz_page')
@login_required
def create_quiz_page(course_id):
    if current_user.role != 'teacher':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
    return render_template('quiz_create.html', course=course)


@app.route('/course/<int:course_id>/create_quiz', methods=['POST'])
@login_required
def create_quiz(course_id):
    if current_user.role != 'teacher':
        flash("Unauthorized", "danger")
        return redirect(url_for('index'))
        
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    
    due_date = None
    if due_date_str:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        
    quiz = Quiz(title=title, description=description, due_date=due_date, course_id=course.id)
    db.session.add(quiz)
    db.session.commit()
    
    # Parse questions from dynamic builder form keys
    # Keys will look like: q-1-text, q-1-a, q-1-b, q-1-c, q-1-d, q-1-correct
    question_count = int(request.form.get('question_count', 1))
    for i in range(1, question_count + 1):
        q_text = request.form.get(f'q-{i}-text')
        # Skip if index was deleted in DOM
        if not q_text:
            continue
            
        opt_a = request.form.get(f'q-{i}-a')
        opt_b = request.form.get(f'q-{i}-b')
        opt_c = request.form.get(f'q-{i}-c')
        opt_d = request.form.get(f'q-{i}-d')
        correct = request.form.get(f'q-{i}-correct')
        
        question = Question(quiz_id=quiz.id, question_text=q_text, option_a=opt_a, option_b=opt_b, option_c=opt_c, option_d=opt_d, correct_answer=correct)
        db.session.add(question)
        
    db.session.commit()
    flash("New Quiz successfully created and published!", "success")
    return redirect(url_for('course_detail', course_id=course.id) + '#quizzes')


# --- STUDENT ACTIONS ---
@app.route('/course/enroll', methods=['POST'])
@login_required
def enroll():
    flash("Direct self-enrollment is disabled. Please contact your tutor or institution administrator to enroll you in courses.", "warning")
    return redirect(url_for('index'))


@app.route('/assignment/submit/<int:assignment_id>', methods=['POST'])
@login_required
def submit_assignment(assignment_id):
    if current_user.role != 'student':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    assign = Assignment.query.get_or_404(assignment_id)
    text_content = request.form.get('text_content')
    
    # Process optional file upload
    saved_filename = None
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S_')
            saved_filename = timestamp + filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
            
    # Check if already submitted
    existing = Submission.query.filter_by(student_id=current_user.id, assignment_id=assign.id).first()
    if existing:
        flash("You have already submitted this assignment.", "warning")
    else:
        # Check if this is the student's first submission overall BEFORE adding the new submission to the session
        is_first_submission = Submission.query.filter_by(student_id=current_user.id).count() == 0
        
        submission = Submission(assignment_id=assign.id, student_id=current_user.id, file_path=saved_filename, text_content=text_content, status='submitted')
        db.session.add(submission)
        
        # Update progress record
        prog_rec = Progress.query.filter_by(student_id=current_user.id, course_id=assign.course_id).first()
        if prog_rec:
            prog_rec.assignments_completed += 1
            
        # Award XP for submission
        current_user.xp_points += 50
        
        # Award "First Submission" badge if it's their first assignment submission overall
        first_badge = Badge.query.filter_by(name="First Submission").first()
        if first_badge and is_first_submission:
            if first_badge not in current_user.badges:
                current_user.badges.append(first_badge)
                flash("🏆 New Badge Unlocked: First Submission!", "info")
                
        # Auto-grading integration
        if assign.auto_grade:
            try:
                api_key = app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
                feedback = ""
                grade = 80.0
                if api_key and text_content:
                    import urllib.request
                    import urllib.parse
                    import json
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                    prompt = f"Grade this student assignment out of {assign.points} points. \nAssignment Title: {assign.title}\nAssignment Description: {assign.description}\nStudent Submission: {text_content}\nReturn ONLY a JSON block containing 'grade' (number) and 'feedback' (short text)."
                    payload = json.dumps({
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json"}
                    }).encode('utf-8')
                    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        res_data = json.loads(response.read().decode())
                        text_response = res_data['candidates'][0]['content']['parts'][0]['text']
                        parsed = json.loads(text_response)
                        grade = float(parsed.get('grade', 80.0))
                        feedback = parsed.get('feedback', "Auto-graded successfully.")
                else:
                    words_count = len(text_content.split()) if text_content else 0
                    if words_count > 50:
                        grade = min(assign.points, 90.0)
                        feedback = "Auto-graded based on length: Good submission."
                    else:
                        grade = min(assign.points, 60.0)
                        feedback = "Auto-graded based on length: Submission is too short."
                submission.grade = grade
                submission.feedback = f"[AI Auto-Grader] {feedback}"
                submission.status = 'graded'
                current_user.xp_points += 50
            except Exception as e:
                print(f"Auto-grade error: {e}")
                
        db.session.commit()
        
        # Check course completion for Certificate
        total_mats = len(assign.course.materials)
        total_quizzes = len(assign.course.quizzes)
        total_assigns = len(assign.course.assignments)
        total_tasks = total_mats + total_quizzes + total_assigns
        
        mats_viewed = prog_rec.materials_viewed if prog_rec else 0
        quizzes_taken = QuizResult.query.join(Quiz).filter(
            QuizResult.student_id == current_user.id,
            Quiz.course_id == assign.course_id
        ).count()
        assigns_submitted = Submission.query.join(Assignment).filter(
            Submission.student_id == current_user.id,
            Assignment.course_id == assign.course_id
        ).count()
        
        completed = mats_viewed + quizzes_taken + assigns_submitted
        if total_tasks > 0 and completed >= total_tasks:
            import uuid
            existing_cert = Certificate.query.filter_by(student_id=current_user.id, course_id=assign.course_id).first()
            if not existing_cert:
                cert_code = f"CERT-{uuid.uuid4().hex[:8].upper()}"
                cert = Certificate(student_id=current_user.id, course_id=assign.course_id, certificate_code=cert_code, is_approved=False)
                db.session.add(cert)
                flash("🎉 Congratulations! You completed all course requirements! Your completion certificate is now pending tutor confirmation.", "success")
                db.session.commit()
        
        # Notify student and teacher via Telegram
        send_telegram_alert(
            current_user, 
            f"✅ *Assignment Submitted!*\n\n*Class:* {assign.course.name}\n*Assignment:* {assign.title}\nSubmitted at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        send_telegram_alert(
            assign.course.teacher, 
            f"📩 *New Submission!*\n\n*Student:* {current_user.name}\n*Class:* {assign.course.name}\n*Assignment:* {assign.title}"
        )
        
        flash("Assignment successfully submitted!", "success")
        
    return redirect(url_for('course_detail', course_id=assign.course_id) + '#assignments')


@app.route('/quiz/take/<int:quiz_id>')
@login_required
def take_quiz(quiz_id):
    if current_user.role != 'student':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    quiz = Quiz.query.get_or_404(quiz_id)
    # Check if already completed
    existing = QuizResult.query.filter_by(student_id=current_user.id, quiz_id=quiz.id).first()
    if existing:
        flash("You have already completed this quiz.", "warning")
        return redirect(url_for('course_detail', course_id=quiz.course_id) + '#quizzes')
        
    return render_template('quiz_take.html', quiz=quiz)


@app.route('/quiz/submit/<int:quiz_id>', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    if current_user.role != 'student':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Ensure they haven't submitted yet
    existing = QuizResult.query.filter_by(student_id=current_user.id, quiz_id=quiz.id).first()
    if existing:
        flash("You have already completed this quiz.", "warning")
        return redirect(url_for('course_detail', course_id=quiz.course_id) + '#quizzes')
        
    # Read answers JSON
    answers_str = request.form.get('answers', '{}')
    try:
        user_answers = json.loads(answers_str)
    except json.JSONDecodeError:
        user_answers = {}
        
    # Grade the quiz
    total_questions = len(quiz.questions)
    correct_count = 0
    
    for q in quiz.questions:
        user_choice = user_answers.get(str(q.id))
        if user_choice and user_choice.upper() == q.correct_answer.upper():
            correct_count += 1
            
    score = (correct_count / total_questions * 100) if total_questions > 0 else 100
    
    # Save Quiz Result
    result = QuizResult(quiz_id=quiz.id, student_id=current_user.id, score=score, total_questions=total_questions)
    db.session.add(result)
    
    # Update progress record
    prog_rec = Progress.query.filter_by(student_id=current_user.id, course_id=quiz.course_id).first()
    if prog_rec:
        prog_rec.quizzes_completed += 1
        
    # Award XP for quiz completion
    current_user.xp_points += 100
    
    # Award "Quiz Master" badge if they scored 100%
    if score == 100.0:
        master_badge = Badge.query.filter_by(name="Quiz Master").first()
        if master_badge and master_badge not in current_user.badges:
            current_user.badges.append(master_badge)
            flash("🏆 New Badge Unlocked: Quiz Master!", "info")
            
    # Check if course is 100% complete to issue a Certificate!
    total_mats = len(quiz.course.materials)
    total_quizzes = len(quiz.course.quizzes)
    total_assigns = len(quiz.course.assignments)
    total_tasks = total_mats + total_quizzes + total_assigns
    
    mats_viewed = prog_rec.materials_viewed if prog_rec else 0
    quizzes_taken = QuizResult.query.join(Quiz).filter(
        QuizResult.student_id == current_user.id,
        Quiz.course_id == quiz.course_id
    ).count()
    assigns_submitted = Submission.query.join(Assignment).filter(
        Submission.student_id == current_user.id,
        Assignment.course_id == quiz.course_id
    ).count()
    
    completed = mats_viewed + quizzes_taken + assigns_submitted
    if total_tasks > 0 and completed >= total_tasks:
        import uuid
        existing_cert = Certificate.query.filter_by(student_id=current_user.id, course_id=quiz.course_id).first()
        if not existing_cert:
            cert_code = f"CERT-{uuid.uuid4().hex[:8].upper()}"
            cert = Certificate(student_id=current_user.id, course_id=quiz.course_id, certificate_code=cert_code, is_approved=False)
            db.session.add(cert)
            flash("🎉 Congratulations! You completed all course requirements! Your completion certificate is now pending tutor confirmation.", "success")
            
    db.session.commit()
    
    flash(f"Quiz completed! You scored {correct_count}/{total_questions} ({score:.1f}%).", "success")
    return redirect(url_for('course_detail', course_id=quiz.course_id) + '#quizzes')


# Contact Form Telegram Submission Route
@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    subject = request.form.get('subject')
    message = request.form.get('message')
    
    # Determine Telegram Chat ID
    chat_id = app.config.get('TELEGRAM_CHAT_ID')
    chat_id_file = os.path.join(app.config.get('UPLOAD_FOLDER'), 'telegram_chat_id.txt')
    
    if not chat_id and os.path.exists(chat_id_file):
        with open(chat_id_file, 'r') as f:
            chat_id = f.read().strip()
            if chat_id:
                app.config['TELEGRAM_CHAT_ID'] = chat_id
                
    import urllib.request
    import urllib.parse
    token = app.config.get('TELEGRAM_BOT_TOKEN')
    
    # Try auto-discovery via getUpdates if chat ID is not known
    if not chat_id:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get('ok') and data.get('result'):
                    # Search for the latest message sender's chat ID
                    for update in reversed(data['result']):
                        if 'message' in update:
                            chat_id = str(update['message']['chat']['id'])
                            # Persist it locally
                            with open(chat_id_file, 'w') as f:
                                f.write(chat_id)
                            app.config['TELEGRAM_CHAT_ID'] = chat_id
                            break
        except Exception as e:
            print(f"Error fetching updates from Telegram: {e}")
            
    if chat_id:
        # Construct message payload
        text = f"📩 *New INKBIT Support Request*\n\n👤 *Name:* {name}\n📧 *Email:* {email}\n📋 *Subject:* {subject}\n💬 *Message:* {message}"
        try:
            send_url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = urllib.parse.urlencode({
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }).encode('utf-8')
            
            req = urllib.request.Request(send_url, data=payload, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode())
                if res_data.get('ok'):
                    flash("Your message was sent directly to our support team on Telegram!", "success")
                else:
                    flash("Failed to send message. Telegram API returned an error.", "danger")
        except Exception as e:
            print(f"Error sending message to Telegram: {e}")
            flash("Error sending message. Please try again later.", "danger")
    else:
        # No chat ID could be discovered
        flash("Support Telegram bot has not been initialized. Please message the bot on Telegram first so it can receive messages.", "warning")
        print(f"No active Chat ID could be resolved. Token: {token}")
        
    return redirect(request.referrer or url_for('index'))


# --- LOCALIZATION AND TRANSLATION ---
TRANSLATIONS = {
    'en': {
        'dashboard': 'Dashboard',
        'my_courses': 'My Courses',
        'assignments': 'Assignments',
        'quizzes': 'Quizzes',
        'live_classes': 'Live Classes',
        'calendar': 'Calendar',
        'messages': 'Messages',
        'notifications': 'Notifications',
        'grades': 'Grades',
        'resources': 'Resources',
        'settings': 'Settings',
        'sign_out': 'Sign Out',
        'welcome': 'Welcome Back!',
        'tutor_dashboard': 'Tutor Dashboard',
        'student_dashboard': 'Student Dashboard',
        'institution_dashboard': 'Institution Dashboard',
        'xp_level': 'XP Level',
        'badges': 'Badges',
        'leaderboard': 'Leaderboard',
        'forums': 'Forums',
        'certificate': 'Certificate',
        'price': 'Price',
        'checkout': 'Checkout',
        'submit': 'Submit',
        'auto_grade': 'Auto-Grade',
        'ai_tutor': 'AI Tutor',
        'self_learning': 'Self Learning',
    },
    'id': {
        'dashboard': 'Dasbor',
        'my_courses': 'Kelas Saya',
        'assignments': 'Tugas',
        'quizzes': 'Kuis',
        'live_classes': 'Kelas Langsung',
        'calendar': 'Kalender',
        'messages': 'Pesan',
        'notifications': 'Notifikasi',
        'grades': 'Nilai',
        'resources': 'Sumber Daya',
        'settings': 'Pengaturan',
        'sign_out': 'Keluar',
        'welcome': 'Selamat Datang!',
        'tutor_dashboard': 'Dasbor Pengajar',
        'student_dashboard': 'Dasbor Siswa',
        'institution_dashboard': 'Dasbor Lembaga',
        'xp_level': 'Tingkat XP',
        'badges': 'Lencana',
        'leaderboard': 'Papan Peringkat',
        'forums': 'Forum Diskusi',
        'certificate': 'Sertifikat',
        'price': 'Harga',
        'checkout': 'Pembayaran',
        'submit': 'Kirim',
        'auto_grade': 'Nilai Otomatis',
        'ai_tutor': 'Tutor AI',
        'self_learning': 'Belajar Mandiri',
    }
}

@app.route('/api/toggle-language')
def toggle_language():
    from flask import session
    session['lang'] = 'en'
    return redirect(request.referrer or url_for('index'))

@app.context_processor
def inject_translations():
    lang = 'en'
    def translate(key):
        return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)
    return {'_t': translate, 'current_lang': lang}


# --- MOCK CHECKOUT / PAYMENTS ---
@app.route('/checkout/<int:course_id>', methods=['GET', 'POST'])
@login_required
def checkout(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        # Create enrollment as paid
        existing = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        if not existing:
            enrollment = Enrollment(student_id=current_user.id, course_id=course.id, payment_status='paid')
            db.session.add(enrollment)
            prog = Progress(student_id=current_user.id, course_id=course.id, materials_viewed=0, assignments_completed=0, quizzes_completed=0)
            db.session.add(prog)
        else:
            existing.payment_status = 'paid'
            
        current_user.xp_points += 100
        db.session.commit()
        
        flash(f"Payment successful! Enrolled in {course.name}.", "success")
        return redirect(url_for('course_detail', course_id=course.id))
        
    return render_template('checkout.html', course=course)


# --- GAMIFICATION LEADERBOARD ---
@app.route('/leaderboard')
@login_required
def leaderboard():
    # Get top students sorted by XP
    top_students = User.query.filter_by(role='student').order_by(User.xp_points.desc()).limit(10).all()
    return render_template('leaderboard.html', top_students=top_students, active_page='leaderboard')


# --- CERTIFICATES ---
@app.route('/certificate/<int:course_id>')
@login_required
def download_certificate(course_id):
    course = Course.query.get_or_404(course_id)
    cert = Certificate.query.filter_by(student_id=current_user.id, course_id=course.id).first()
    if not cert:
        flash("You have not earned a certificate for this course yet.", "warning")
        return redirect(url_for('course_detail', course_id=course.id))
    if not cert.is_approved:
        flash("Your certificate is pending tutor confirmation.", "warning")
        return redirect(url_for('course_detail', course_id=course.id))
    return render_template('certificate.html', cert=cert, course=course)


@app.route('/certificate/confirm/<int:cert_id>', methods=['POST'])
@login_required
def confirm_certificate(cert_id):
    if current_user.role not in ['teacher', 'institution']:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    cert = Certificate.query.get_or_404(cert_id)
    # Verify this teacher teaches this course
    if current_user.role == 'teacher' and cert.course.teacher_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
        
    cert.is_approved = True
    db.session.commit()
    
    # Notify student via Telegram
    send_telegram_alert(
        cert.student,
        f"🎓 *Certificate Unlocked!*\n\nYour completion certificate for *{cert.course.name}* has been confirmed by tutor *{current_user.name}*! You can now download it from your student dashboard."
    )
    
    flash(f"Completion confirmed for {cert.student.name} in {cert.course.name}. Certificate issued!", "success")
    return redirect(url_for('index') + '#students-section')


# --- DISCUSSION FORUMS ---
@app.route('/course/<int:course_id>/forum')
@login_required
def course_forum(course_id):
    course = Course.query.get_or_404(course_id)
    if current_user.role == 'student':
        if not Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first():
            flash("You are not enrolled in this course.", "danger")
            return redirect(url_for('index'))
    elif current_user.role == 'teacher':
        if course.teacher_id != current_user.id:
            flash("Unauthorized action.", "danger")
            return redirect(url_for('index'))
    threads = ForumThread.query.filter_by(course_id=course.id).order_by(ForumThread.created_at.desc()).all()
    return render_template('forum.html', course=course, threads=threads, active_page='forum')

@app.route('/course/<int:course_id>/forum/new', methods=['POST'])
@login_required
def create_forum_thread(course_id):
    course = Course.query.get_or_404(course_id)
    if current_user.role == 'student':
        if not Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first():
            flash("You are not enrolled in this course.", "danger")
            return redirect(url_for('index'))
    elif current_user.role == 'teacher':
        if course.teacher_id != current_user.id:
            flash("Unauthorized action.", "danger")
            return redirect(url_for('index'))
    title = request.form.get('title')
    content = request.form.get('content')
    
    if title and content:
        thread = ForumThread(title=title, content=content, course_id=course.id, user_id=current_user.id)
        db.session.add(thread)
        
        # Award badge for community voice
        voice_badge = Badge.query.filter_by(name="Community Voice").first()
        if voice_badge and voice_badge not in current_user.badges:
            current_user.badges.append(voice_badge)
            flash("🏆 New Badge Unlocked: Community Voice!", "info")
            
        current_user.xp_points += 30
        db.session.commit()
        flash("Discussion thread posted successfully!", "success")
    return redirect(url_for('course_forum', course_id=course.id))

@app.route('/forum/thread/<int:thread_id>', methods=['GET', 'POST'])
@login_required
def view_forum_thread(thread_id):
    thread = ForumThread.query.get_or_404(thread_id)
    course = thread.course
    if current_user.role == 'student':
        if not Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first():
            flash("You are not enrolled in this course.", "danger")
            return redirect(url_for('index'))
    elif current_user.role == 'teacher':
        if course.teacher_id != current_user.id:
            flash("Unauthorized action.", "danger")
            return redirect(url_for('index'))
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            reply = ForumReply(content=content, thread_id=thread.id, user_id=current_user.id)
            db.session.add(reply)
            current_user.xp_points += 10
            db.session.commit()
            flash("Reply posted!", "success")
        return redirect(url_for('view_forum_thread', thread_id=thread.id))
    return render_template('forum_thread.html', thread=thread)


# --- LIVE CLASSES ---
@app.route('/course/<int:course_id>/live-classes', methods=['GET', 'POST'])
@login_required
def course_live_classes(course_id):
    course = Course.query.get_or_404(course_id)
    if current_user.role == 'teacher' and course.teacher_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        if current_user.role != 'teacher':
            flash("Unauthorized.", "danger")
            return redirect(url_for('course_detail', course_id=course.id))
        title = request.form.get('title')
        description = request.form.get('description')
        meeting_link = request.form.get('meeting_link')
        time_str = request.form.get('scheduled_time')
        
        if title and meeting_link and time_str:
            sched_time = datetime.strptime(time_str, '%Y-%m-%dT%H:%M')
            live = LiveClass(title=title, description=description, meeting_link=meeting_link, scheduled_time=sched_time, course_id=course.id)
            db.session.add(live)
            db.session.commit()
            flash("Live class scheduled successfully!", "success")
        return redirect(url_for('course_detail', course_id=course.id) + '#live-classes')
    return redirect(url_for('course_detail', course_id=course.id))


# --- QR ATTENDANCE SCANNING ---
@app.route('/course/<int:course_id>/attendance/token')
@login_required
def get_attendance_token(course_id):
    course = Course.query.get_or_404(course_id)
    if current_user.role == 'teacher' and course.teacher_id != current_user.id:
        return {'ok': False, 'error': 'Unauthorized action.'}, 403
    if current_user.role not in ['teacher', 'institution']:
        return {'ok': False, 'error': 'Unauthorized action.'}, 403
        
    date_str = datetime.now().strftime('%Y%m%d')
    token = f"ATT-CODE-{course_id}-{date_str}"
    
    # Read public_url.txt if it exists to get the public tunnel host
    import os
    base_url = request.host_url
    if os.path.exists('public_url.txt'):
        try:
            with open('public_url.txt', 'r', encoding='utf-8') as f:
                public_url = f.read().strip()
                if public_url.startswith('http'):
                    base_url = public_url.rstrip('/') + '/'
        except Exception:
            pass
            
    mark_url = f"{base_url}course/{course_id}/attendance/mark/{token}"
    
    return {'ok': True, 'token': token, 'mark_url': mark_url}


@app.route('/course/<int:course_id>/attendance/mark/<string:token>', methods=['GET', 'POST'])
@login_required
def mark_attendance(course_id, token):
    course = Course.query.get_or_404(course_id)
    
    # Parse and validate the token: expected format ATT-CODE-{course_id}-{date_str}
    parts = token.split('-')
    if len(parts) < 4 or parts[0] != 'ATT' or parts[1] != 'CODE':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
            return {'ok': False, 'error': 'Invalid attendance QR code.'}, 400
        flash("Invalid attendance QR code.", "danger")
        return redirect(url_for('course_detail', course_id=course_id))
        
    try:
        t_course_id = int(parts[2])
        date_str = parts[3]
    except ValueError:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
            return {'ok': False, 'error': 'Invalid attendance QR code format.'}, 400
        flash("Invalid attendance QR code format.", "danger")
        return redirect(url_for('course_detail', course_id=course_id))
        
    if t_course_id != course_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
            return {'ok': False, 'error': 'This QR code is for a different course.'}, 400
        flash("This QR code is for a different course.", "danger")
        return redirect(url_for('course_detail', course_id=course_id))
        
    # Check if the code was generated today
    today_str = datetime.now().strftime('%Y%m%d')
    if date_str != today_str:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
            return {'ok': False, 'error': 'This attendance QR code has expired.'}, 400
        flash("This attendance QR code has expired.", "danger")
        return redirect(url_for('course_detail', course_id=course_id))
        
    # Check student enrollment
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()
    if not enrollment:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
            return {'ok': False, 'error': 'You are not enrolled in this course.'}, 400
        flash("You are not enrolled in this course.", "danger")
        return redirect(url_for('index'))
        
    # Increment attendance count
    enrollment.attendance_count = (enrollment.attendance_count or 0) + 1
    db.session.commit()
    
    # Send Telegram Notification
    telegram_message = (
        f"🔔 *INKBIT Attendance Recorded!*\n\n"
        f"📚 *Course:* {course.name} ({course.code})\n"
        f"👤 *Student:* {current_user.name}\n"
        f"📅 *Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📊 *Total Attendance:* {enrollment.attendance_count} sessions.\n\n"
        f"Keep up the great work! 💪"
    )
    send_telegram_alert(current_user, telegram_message)
    
    msg = f"🎉 Attendance successfully registered for {course.name}! An automated Telegram message confirmation has been sent to your phone."
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
        return {'ok': True, 'message': msg}
        
    flash(msg, "success")
    return redirect(url_for('course_detail', course_id=course_id))


# --- AI TUTOR API ---
@app.route('/api/ai-tutor', methods=['POST'])
@app.route('/api/self-learning/ai-tutor', methods=['POST'])
@login_required
def ai_tutor():
    data = request.json or {}
    message = data.get('message', '').strip()
    course_id = data.get('course_id')
    
    if not message:
        return {'reply': 'Please enter a message.'}
        
    course_info = ""
    if course_id:
        course = db.session.get(Course, course_id)
        if course:
            course_info = f"The student is asking about the course: {course.name} ({course.code}) - {course.description}.\n"
            
    try:
        api_key = app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if api_key:
            import urllib.request
            import urllib.parse
            import json
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            prompt = f"You are a helpful academic tutor. {course_info}Answer the student's question: {message}"
            
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}]
            }).encode('utf-8')
            
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode())
                reply = res_data['candidates'][0]['content']['parts'][0]['text']
                return {'reply': reply}
        else:
            # Educational Mock response fallback
            replies = [
                "That's an interesting question! I recommend checking the Syllabus material uploaded by your teacher for details.",
                "Make sure to submit your assignments on time to earn XP points and unlock Badges!",
                "I'm here to support you 24/7. Tutors can also set meeting links for live classes in the Live Classes tab."
            ]
            import random
            return {'reply': random.choice(replies)}
    except Exception as e:
        return {'reply': f"I ran into an issue connecting to the AI brain. Error: {str(e)}"}



def query_gemini_json(prompt, fallback_data):
    api_key = app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return fallback_data
        
    import urllib.request
    import urllib.parse
    import json
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode())
            text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            # Handle possible markdown blocks
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            return json.loads(text)
    except Exception as e:
        print(f"Error querying Gemini JSON: {e}")
        return fallback_data


# --- AI CONTENT GENERATION ENDPOINTS ---

@app.route('/api/ai-generate-course', methods=['POST'])
@login_required
def ai_generate_course():
    if current_user.role not in ['teacher', 'institution']:
        return {'error': 'Unauthorized'}, 403
        
    data = request.json or {}
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return {'error': 'Prompt is required'}, 400
        
    system_prompt = f"""
    You are a university academic coordinator. Create a new course syllabus based on: '{prompt}'.
    Return ONLY a JSON object:
    {{
      "name": "Course Title (Code)",
      "description": "Detailed description of the course, goals, and syllabus outline.",
      "tags": "Comma-separated list of 3-4 pedagogical tags (e.g. Case Method, Project Based)",
      "schedule": "Weekly schedule pattern (e.g. Monday, 13:00 - 15:30)",
      "department": "Academic Department (e.g. Computer Science)"
    }}
    """
    
    fallback = {
        "name": f"{prompt.title()} Course",
        "description": f"Learn foundations and advanced concepts of {prompt}. Weekly lectures covering theory and practical labs.",
        "tags": "Project Based Learning,Case Method,Interactive Discussion",
        "schedule": "Monday, 10:00 - 12:30",
        "department": "Computer Science"
    }
    
    res = query_gemini_json(system_prompt, fallback)
    return res


@app.route('/api/ai-generate-assignment', methods=['POST'])
@login_required
def ai_generate_assignment():
    if current_user.role not in ['teacher', 'institution']:
        return {'error': 'Unauthorized'}, 403
        
    data = request.json or {}
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return {'error': 'Prompt is required'}, 400
        
    system_prompt = f"""
    You are an academic teacher. Generate a creative homework assignment title and instructions for: '{prompt}'.
    Return ONLY a JSON object:
    {{
      "title": "Assignment Title",
      "description": "Detailed instructions, step-by-step tasks, and grading expectations."
    }}
    """
    
    fallback = {
        "title": f"Assignment: {prompt.title()}",
        "description": f"Write a detailed essay or complete a coding task about {prompt}. Submit your file or text response."
    }
    
    res = query_gemini_json(system_prompt, fallback)
    return res


@app.route('/api/ai-generate-quiz', methods=['POST'])
@login_required
def ai_generate_quiz():
    if current_user.role not in ['teacher', 'institution']:
        return {'error': 'Unauthorized'}, 403
        
    data = request.json or {}
    topic = data.get('topic', '').strip()
    count = int(data.get('count', 5))
    
    # Enforce minimum 5 and maximum 100 questions
    if count < 5:
        count = 5
    elif count > 100:
        count = 100
        
    if not topic:
        return {'error': 'Topic is required'}, 400
        
    system_prompt = f"""
    You are an academic quiz maker. Generate EXACTLY {count} multiple choice questions about the topic '{topic}'.
    IMPORTANT: Provide clear, educational, and concise questions.
    Return ONLY a JSON object matching the following structure:
    {{
      "title": "Quiz Title",
      "description": "Brief description of the quiz.",
      "questions": [
        {{
          "question_text": "Question text?",
          "option_a": "Choice A",
          "option_b": "Choice B",
          "option_c": "Choice C",
          "option_d": "Choice D",
          "correct_answer": "A"
        }}
      ]
    }}
    """
    
    # Dynamic fallback generator scaling up to 100 questions
    fallback_questions = []
    for idx in range(1, count + 1):
        # Rotate correct answer to make fallback quiz more interesting
        ans_key = ['A', 'B', 'C', 'D'][(idx - 1) % 4]
        fallback_questions.append({
            "question_text": f"What is the key principle regarding point #{idx} of {topic}?",
            "option_a": f"Core concept option A for #{idx}" if ans_key == 'A' else "Incorrect choice A",
            "option_b": f"Core concept option B for #{idx}" if ans_key == 'B' else "Incorrect choice B",
            "option_c": f"Core concept option C for #{idx}" if ans_key == 'C' else "Incorrect choice C",
            "option_d": f"Core concept option D for #{idx}" if ans_key == 'D' else "Incorrect choice D",
            "correct_answer": ans_key
        })
        
    fallback = {
        "title": f"AI Generated Quiz: {topic.title()}",
        "description": f"Comprehensive evaluation containing {count} questions about {topic}.",
        "questions": fallback_questions
    }
    
    res = query_gemini_json(system_prompt, fallback)
    return res


@app.route('/api/ai-generate-thread', methods=['POST'])
@login_required
def ai_generate_thread():
    data = request.json or {}
    title = data.get('title', '').strip()
    if not title:
        return {'error': 'Title is required'}, 400
        
    system_prompt = f"""
    You are a student or a teacher participating in a university course classroom forum. Write a detailed, engaging discussion post for the topic titled '{title}'.
    Return ONLY a JSON object:
    {{
      "content": "Full post body content, showing active interest, asking questions, or explaining a core academic concept."
    }}
    """
    
    fallback = {
        "content": f"Hello everyone! I wanted to start a discussion about {title}. What are your thoughts on this topic? Let's share some notes and work together."
    }
    
    res = query_gemini_json(system_prompt, fallback)
    return res


@app.route('/api/ai-generate-reply', methods=['POST'])
@login_required
def ai_generate_reply():
    data = request.json or {}
    thread_title = data.get('thread_title', '').strip()
    thread_content = data.get('thread_content', '').strip()
    if not thread_title:
        return {'error': 'Thread title is required'}, 400
        
    system_prompt = f"""
    You are a helpful academic forum assistant. Write a short, insightful, educational response to the classroom discussion thread titled '{thread_title}' with content '{thread_content}'.
    Return ONLY a JSON object:
    {{
      "reply": "Reply content offering guidance, clarifications, or supportive educational points."
    }}
    """
    
    fallback = {
        "reply": f"Thank you for sharing this! Regarding {thread_title}, we should consider its practical applications in software development and optimization."
    }
    
    res = query_gemini_json(system_prompt, fallback)
    return res


# --- SELF LEARNING ROUTES ---

@app.route('/api/course/<int:course_id>/materials')
@login_required
def get_course_materials(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return {'error': 'Course not found'}, 404
    mats = [{'id': m.id, 'title': m.title, 'description': m.description, 'file_path': m.file_path} for m in course.materials]
    return {'course_id': course.id, 'course_name': course.name, 'materials': mats}

@app.route('/self-learning')
@login_required
def self_learning():
    if current_user.role != 'student':
        flash("Self-Learning Hub is only available for students.", "warning")
        return redirect(url_for('index'))
        
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    courses = [e.course for e in enrollments]
    
    # Calculate completed courses
    completed_courses_count = 0
    completed_courses = []
    for course in courses:
        total_mats = len(course.materials)
        total_quizzes = len(course.quizzes)
        total_assigns = len(course.assignments)
        total_tasks = total_mats + total_quizzes + total_assigns
        
        if total_tasks > 0:
            prog_rec = Progress.query.filter_by(student_id=current_user.id, course_id=course.id).first()
            mats_viewed = prog_rec.materials_viewed if prog_rec else 0
            quizzes_taken = QuizResult.query.join(Quiz).filter(
                QuizResult.student_id == current_user.id,
                Quiz.course_id == course.id
            ).count()
            assigns_submitted = Submission.query.join(Assignment).filter(
                Submission.student_id == current_user.id,
                Assignment.course_id == course.id
            ).count()
            
            completed = mats_viewed + quizzes_taken + assigns_submitted
            if completed >= total_tasks:
                completed_courses_count += 1
                cert = Certificate.query.filter_by(student_id=current_user.id, course_id=course.id).first()
                completed_courses.append({
                    'course': course,
                    'certificate': cert
                })
        else:
            completed_courses_count += 1
            cert = Certificate.query.filter_by(student_id=current_user.id, course_id=course.id).first()
            completed_courses.append({
                'course': course,
                'certificate': cert
            })
            
    # Past classes (have recording urls or scheduled_time < now)
    accessible_course_ids = [e.course_id for e in enrollments if not e.course.is_paid or e.payment_status == 'paid']
    past_classes = LiveClass.query.filter(
        LiveClass.course_id.in_(accessible_course_ids),
        (LiveClass.scheduled_time < datetime.now()) | (LiveClass.recording_url != None)
    ).order_by(LiveClass.scheduled_time.desc()).all() if accessible_course_ids else []

    # Deadlines for reminders
    deadlines = []
    for course in courses:
        for assign in course.assignments:
            sub = Submission.query.filter_by(student_id=current_user.id, assignment_id=assign.id).first()
            if not sub:
                deadlines.append({
                    'title': assign.title,
                    'due_date': assign.due_date,
                    'course_name': course.name,
                    'type': 'Assignment'
                })
        for quiz in course.quizzes:
            res = QuizResult.query.filter_by(student_id=current_user.id, quiz_id=quiz.id).first()
            if not res and quiz.due_date:
                deadlines.append({
                    'title': quiz.title,
                    'due_date': quiz.due_date,
                    'course_name': course.name,
                    'type': 'Quiz'
                })
    deadlines.sort(key=lambda x: x['due_date'])

    # Seed default bookmarks if empty
    if not current_user.bookmarks_json:
        default_bookmarks = [
            {"title": "Python Variables", "url": "#"},
            {"title": "CSS Flexbox", "url": "#"},
            {"title": "Git Commands", "url": "#"},
            {"title": "Machine Learning Notes", "url": "#"}
        ]
        current_user.bookmarks_json = json.dumps(default_bookmarks)
        db.session.commit()
        
    try:
        bookmarks = json.loads(current_user.bookmarks_json)
    except Exception:
        bookmarks = []
        
    # Load roadmap
    roadmap = None
    if current_user.personalized_roadmap:
        try:
            roadmap = json.loads(current_user.personalized_roadmap)
        except Exception:
            pass

    # Skills tracker logic
    skills = [
        {"name": "Python", "level": 85},
        {"name": "SQL", "level": 60},
        {"name": "HTML", "level": 100},
        {"name": "JavaScript", "level": 40}
    ]
    
    cs101_progress = Progress.query.filter_by(student_id=current_user.id).join(Course).filter(Course.code == 'CS-101').first()
    if cs101_progress:
        total_m = len(cs101_progress.course.materials)
        if total_m > 0:
            skills[0]['level'] = int((cs101_progress.materials_viewed / total_m) * 100)
            
    cs203_progress = Progress.query.filter_by(student_id=current_user.id).join(Course).filter(Course.code == 'CS-203').first()
    if cs203_progress:
        total_m = len(cs203_progress.course.materials)
        if total_m > 0:
            skills[1]['level'] = int((cs203_progress.materials_viewed / total_m) * 100)

    # Study stats
    xp = current_user.xp_points or 1450
    level = int(xp // 100)
    if level == 0:
        level = 1
    study_hours = 32 + (current_user.login_streak or 0) // 2
    
    stats = {
        'study_hours': study_hours,
        'courses_finished': completed_courses_count,
        'xp_earned': xp,
        'level': level
    }

    # Achievements / Badges
    user_badges = current_user.badges.all() if hasattr(current_user.badges, 'all') else current_user.badges
    
    if not user_badges:
        b1 = Badge.query.filter_by(name="Python Beginner").first()
        if not b1:
            b1 = Badge(name="Python Beginner", description="Write your first python script", icon_code="🥇")
            db.session.add(b1)
        b2 = Badge.query.filter_by(name="Streak Master").first()
        if not b2:
            b2 = Badge(name="Streak Master", description="Maintain a 7-day streak", icon_code="🔥")
            db.session.add(b2)
        b3 = Badge.query.filter_by(name="AI Trailblazer").first()
        if not b3:
            b3 = Badge(name="AI Trailblazer", description="Ask 5 questions to AI Tutor", icon_code="📖")
            db.session.add(b3)
        b4 = Badge.query.filter_by(name="Quiz Conqueror").first()
        if not b4:
            b4 = Badge(name="Quiz Conqueror", description="Get a perfect score in a quiz", icon_code="🎯")
            db.session.add(b4)
        db.session.commit()
        
        current_user.badges.append(b1)
        current_user.badges.append(b2)
        current_user.badges.append(b3)
        current_user.badges.append(b4)
        db.session.commit()
        user_badges = current_user.badges

    return render_template('self_learning.html', 
                           active_page='self-learning', 
                           enrollments=enrollments,
                           completed_courses=completed_courses,
                           completed_courses_count=completed_courses_count,
                           past_classes=past_classes,
                           deadlines=deadlines,
                           bookmarks=bookmarks,
                           roadmap=roadmap,
                           skills=skills,
                           stats=stats,
                           user_badges=user_badges)


@app.route('/api/self-learning/ai-tutor', methods=['POST'])
@login_required
def self_learning_ai_tutor():
    data = request.json or {}
    message = data.get('message', '').strip()
    course_id = data.get('course_id')
    
    if not message:
        return {'reply': 'Please write your question.'}, 400
        
    course = None
    if course_id:
        course = db.session.get(Course, course_id)
        
    # Read course materials context
    materials_context = ""
    if course:
        materials = Material.query.filter_by(course_id=course.id).all()
        for mat in materials:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], mat.file_path)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                        materials_context += f"\n--- Material: {mat.title} ---\n{text}\n"
                except Exception:
                    pass
                    
    # Cap materials context to avoid token limits (around 8000 chars)
    if len(materials_context) > 8000:
        materials_context = materials_context[:8000] + "\n... [truncated] ..."
        
    prompt = f"""
    You are "{course.name if course else 'General'}" Academic Tutor.
    Use the following course materials context to answer the student's question if relevant.
    If the question is unrelated, answer it based on general knowledge but encourage the student to focus on the course material.
    Be educational, engaging, encouraging, and clear. Use markdown formatting.
    
    ---
    Course Materials Context:
    {materials_context}
    ---
    
    Student Question: {message}
    """
    
    fallback = {
        "reply": f"Hello! As your AI tutor for {course.name if course else 'general study'}, I recommend reading the syllabus and notes. Let's do our best! What specific part of {message} can I clarify?"
    }
    
    res = query_gemini_json(f"Return a JSON object with a single 'reply' key containing the response. Prompt: {prompt}", fallback)
    reply = res.get('reply', fallback['reply'])
    
    # Award XP points & check badges
    current_user.xp_points += 15
    current_user.ai_queries_count = (current_user.ai_queries_count or 0) + 1
    
    tutor_badge = Badge.query.filter_by(name="AI Trailblazer").first()
    badge_unlocked = False
    if tutor_badge and current_user.ai_queries_count >= 5:
        if tutor_badge not in current_user.badges:
            current_user.badges.append(tutor_badge)
            badge_unlocked = True
            
    db.session.commit()
    
    return {'reply': reply, 'xp_earned': 15, 'badge_unlocked': badge_unlocked}


@app.route('/api/self-learning/generate-quiz', methods=['POST'])
@login_required
def self_learning_generate_quiz():
    data = request.json or {}
    material_id = data.get('material_id')
    
    if not material_id:
        return {'error': 'Material ID is required'}, 400
        
    material = db.session.get(Material, material_id)
    if not material:
        return {'error': 'Material not found'}, 404
        
    # Read material content
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], material.file_path)
    content = ""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            pass
            
    if not content:
        content = f"Material title is {material.title}. Description: {material.description or ''}"
        
    if len(content) > 5000:
        content = content[:5000]
        
    prompt = f"""
    Based on the following learning material, generate an interactive practice quiz containing 3 multiple choice questions.
    Return ONLY a JSON object matching this structure:
    {{
      "title": "Quiz Title (from material)",
      "description": "Short explanation",
      "questions": [
        {{
          "question_text": "Question?",
          "option_a": "Choice A",
          "option_b": "Choice B",
          "option_c": "Choice C",
          "option_d": "Choice D",
          "correct_answer": "A" (or B, C, D),
          "explanation": "Detailed explanation of why that choice is correct, citing concepts from the material."
        }}
      ]
    }}
    
    Material Content:
    {content}
    """
    
    fallback = {
      "title": f"Practice Quiz: {material.title}",
      "description": "Evaluate your understanding of the uploaded material.",
      "questions": [
        {
          "question_text": f"What is the main topic covered in {material.title}?",
          "option_a": f"The primary concepts of {material.title}",
          "option_b": "An unrelated secondary concept",
          "option_c": "Experimental side observations",
          "option_d": "Historical background details",
          "correct_answer": "A",
          "explanation": f"The material focuses specifically on explaining the core principles and frameworks of {material.title}."
        },
        {
          "question_text": "How should a student apply the contents of this material?",
          "option_a": "Ignore it entirely",
          "option_b": "Study the lecture notes and answer corresponding AI practice questions",
          "option_c": "Wait until the final exam to read it",
          "option_d": "Memorize without understanding",
          "correct_answer": "B",
          "explanation": "Active self-paced learning combined with practice questions is proven to maximize comprehension and retention."
        },
        {
          "question_text": "Which of the following is true about this course module?",
          "option_a": "It is not covered in assignments",
          "option_b": "It is designed to enhance self-paced student learning",
          "option_c": "It has no practical exercises",
          "option_d": "None of the above",
          "correct_answer": "B",
          "explanation": "This module is a supplementary self-learning tool integrated with AI capabilities to support individual study paces."
        }
      ]
    }
    
    res = query_gemini_json(prompt, fallback)
    return res


@app.route('/api/self-learning/submit-quiz', methods=['POST'])
@login_required
def self_learning_submit_quiz():
    data = request.json or {}
    course_id = data.get('course_id')
    score = float(data.get('score', 0))
    total_questions = int(data.get('total_questions', 3))
    
    # Award XP points
    xp = 50
    if score == 100.0:
        xp += 50
    current_user.xp_points += xp
    
    # Save completion to Progress
    if course_id:
        prog_rec = Progress.query.filter_by(student_id=current_user.id, course_id=course_id).first()
        if prog_rec:
            prog_rec.quizzes_completed = (prog_rec.quizzes_completed or 0) + 1
            
    # Check "Quiz Conqueror" badge
    perfect_badge = Badge.query.filter_by(name="Quiz Conqueror").first()
    badge_unlocked = False
    if perfect_badge and score == 100.0:
        if perfect_badge not in current_user.badges:
            current_user.badges.append(perfect_badge)
            badge_unlocked = True
            
    db.session.commit()
    
    return {'status': 'success', 'xp_earned': xp, 'badge_unlocked': badge_unlocked}


@app.route('/api/self-learning/recommendations')
@login_required
def self_learning_recommendations():
    # Analyze student performance data
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    courses_data = []
    for e in enrollments:
        prog = Progress.query.filter_by(student_id=current_user.id, course_id=e.course.id).first()
        mats_viewed = prog.materials_viewed if prog else 0
        assigns_completed = prog.assignments_completed if prog else 0
        quizzes_completed = prog.quizzes_completed if prog else 0
        courses_data.append({
            'code': e.course.code,
            'name': e.course.name,
            'materials_viewed': mats_viewed,
            'total_materials': len(e.course.materials),
            'assignments_completed': assigns_completed,
            'total_assignments': len(e.course.assignments),
            'quizzes_completed': quizzes_completed,
            'total_quizzes': len(e.course.quizzes)
        })
        
    prompt = f"""
    Analyze the student's learning progress across their courses and provide 3 personalized learning recommendations.
    Return ONLY a JSON object containing a 'recommendations' key with an array of objects.
    Each recommendation object must contain:
      - 'title': short title of action (e.g. "Review Database Normalization")
      - 'description': explanation of why and what to study
      - 'action_label': button label (e.g. "Go to Materials")
      - 'course_code': code of the course this belongs to
      
    Student Data:
    {json.dumps(courses_data)}
    """
    
    fallback = {
        "recommendations": [
            {
                "title": "Start CS-101 Programming Labs",
                "description": "You haven't completed any assignments for Python Programming yet. Complete Session 1 slides to build a solid foundation.",
                "action_label": "Study Slides",
                "course_code": "CS-101"
            },
            {
                "title": "Solve Discrete Mathematics Quiz",
                "description": "Quiz #12 is due soon. Try generating a practice quiz from the Discrete Mathematics syllabus to prepare.",
                "action_label": "Take Practice Quiz",
                "course_code": "CS-103"
            },
            {
                "title": "Read OS CPU Scheduling Notes",
                "description": "Your operating system modules contain detailed workshops. Review CPU scheduling notes to bolster process management concepts.",
                "action_label": "Read Materials",
                "course_code": "CS-202"
            }
        ]
    }
    
    res = query_gemini_json(prompt, fallback)
    return res


@app.route('/api/self-learning/translate', methods=['POST'])
@login_required
def self_learning_translate():
    data = request.json or {}
    text = data.get('text', '').strip()
    target_lang = data.get('target_lang', 'en').strip()
    
    if not text:
        return {'translated_text': ''}
        
    prompt = f"Translate the following text into '{target_lang}'. Return ONLY the exact translated text. Keep all markdown structure intact. Text: {text}"
    
    translations_dict = {
        'id': {
            'Hello!': 'Halo!',
            'AI Academic Tutor': 'Tutor Akademik AI',
            'Syllabus': 'Silabus',
            'Practice Quiz': 'Kuis Latihan'
        }
    }
    
    translated = text
    api_key = app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}]
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=8) as response:
                res_data = json.loads(response.read().decode())
                translated = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception:
            lang_dict = translations_dict.get(target_lang, {})
            for key, val in lang_dict.items():
                if key in text:
                    translated = text.replace(key, val)
    else:
        lang_dict = translations_dict.get(target_lang, {})
        for key, val in lang_dict.items():
            if key in text:
                translated = text.replace(key, val)
                
    return {'translated_text': translated}


@app.route('/api/self-learning/class-summary/<int:class_id>')
@login_required
def self_learning_class_summary(class_id):
    live = db.session.get(LiveClass, class_id)
    if not live:
        return {'error': 'Live class not found'}, 404
        
    if not live.ai_summary:
        prompt = f"""
        Write a structured academic summary of a classroom lecture.
        Lecture Title: {live.title}
        Lecture Description: {live.description or ''}
        Provide 3 bullet points summarizing the core topics and what the students learned.
        Return ONLY a JSON object:
        {{
          "summary": "### Lecture Summary\\n\\n- **Topic 1**: Description\\n- **Topic 2**: Description\\n- **Topic 3**: Description"
        }}
        """
        fallback = {
            "summary": f"### Lecture Summary: {live.title}\n\n- **Core Concept**: Explored fundamentals of {live.title}.\n- **Interactive Discussion**: Tutors answered student questions and provided examples.\n- **Next Steps**: Review assignment notes for corresponding homework assignments."
        }
        res = query_gemini_json(prompt, fallback)
        live.ai_summary = res.get('summary', fallback['summary'])
        db.session.commit()
        
    return {
        'id': live.id,
        'title': live.title,
        'description': live.description,
        'recording_url': live.recording_url or "https://www.w3schools.com/html/mov_bbb.mp4",
        'ai_summary': live.ai_summary
    }


@app.route('/api/self-learning/claim-certificate', methods=['POST'])
@login_required
def claim_self_learning_certificate():
    data = request.json or {}
    course_id = data.get('course_id')
    if not course_id:
        return {'error': 'Course ID is required'}, 400
        
    course = db.session.get(Course, course_id)
    if not course:
        return {'error': 'Course not found'}, 404
        
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
    if not enrollment:
        return {'error': 'Student not enrolled'}, 400
        
    import uuid
    existing = Certificate.query.filter_by(student_id=current_user.id, course_id=course.id).first()
    if not existing:
        cert_code = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        cert = Certificate(
            student_id=current_user.id,
            course_id=course.id,
            certificate_code=cert_code,
            is_approved=True
        )
        db.session.add(cert)
        db.session.commit()
        flash("🎉 Certified! Your completion certificate has been generated and verified.", "success")
        return {'status': 'success', 'code': cert_code}
    else:
        existing.is_approved = True
        db.session.commit()
        return {'status': 'success', 'code': existing.certificate_code}


@app.route('/api/self-learning/generate-roadmap', methods=['POST'])
@login_required
def generate_self_learning_roadmap():
    data = request.json or {}
    topic = data.get('topic', '').strip()
    level = data.get('level', 'Beginner').strip()
    hours = data.get('hours', '5').strip()
    goal = data.get('goal', 'Hobby').strip()
    
    if not topic:
        return {'error': 'Topic is required'}, 400
        
    prompt = f"""
    Generate a personalized week-by-week study roadmap for a student.
    Topic to Learn: {topic}
    Current Level: {level}
    Hours available per week: {hours} hours
    Target Goal: {goal}

    Generate a structured weekly study plan for 6 weeks.
    Return ONLY a JSON object matching this structure:
    {{
      "goal": "Personalized Goal Title (e.g. Become a Frontend Developer)",
      "weeks": [
        {{
          "week": "Week 1",
          "title": "Week Title (e.g. HTML Basics)",
          "status": "in-progress",
          "topics": ["Topic 1", "Topic 2", "Topic 3"]
        }},
        {{
          "week": "Week 2",
          "title": "Week Title (e.g. CSS Layout)",
          "status": "not-started",
          "topics": ["Topic 1", "Topic 2", "Topic 3"]
        }},
        ...
      ]
    }}
    Ensure exactly 6 weeks are generated. Keep it realistic, tailored, and educational.
    """
    
    fallback = {
        "goal": f"Become a {topic} Specialist",
        "weeks": [
            {
                "week": "Week 1",
                "title": f"Introduction to {topic}",
                "status": "in-progress",
                "topics": ["Core concepts", "History & evolution", "Setting up tools"]
            },
            {
                "week": "Week 2",
                "title": f"Basic Fundamentals of {topic}",
                "status": "not-started",
                "topics": ["Syntax & Grammar", "Simple exercises", "Best practices"]
            },
            {
                "week": "Week 3",
                "title": f"Intermediate {topic} structures",
                "status": "not-started",
                "topics": ["Data manipulation", "Common design patterns", "Modular design"]
            },
            {
                "week": "Week 4",
                "title": f"Advanced {topic} techniques",
                "status": "not-started",
                "topics": ["Optimization", "Troubleshooting", "Third-party libraries"]
            },
            {
                "week": "Week 5",
                "title": f"Mini Project construction",
                "status": "not-started",
                "topics": ["Planning project scope", "Implementing logic", "Refactoring code"]
            },
            {
                "week": "Week 6",
                "title": f"Final review and deployment",
                "status": "not-started",
                "topics": ["Testing features", "Publishing work", "Future outlook"]
            }
        ]
    }
    
    res = query_gemini_json(prompt, fallback)
    
    # Save to user profile
    current_user.personalized_roadmap = json.dumps(res)
    db.session.commit()
    
    return res


@app.route('/api/self-learning/update-roadmap-status', methods=['POST'])
@login_required
def update_roadmap_status():
    data = request.json or {}
    week_index = int(data.get('week_index', 0))
    new_status = data.get('status', 'not-started').strip()
    
    if not current_user.personalized_roadmap:
        return {'error': 'No roadmap found'}, 404
        
    try:
        roadmap = json.loads(current_user.personalized_roadmap)
        if 0 <= week_index < len(roadmap['weeks']):
            roadmap['weeks'][week_index]['status'] = new_status
            current_user.personalized_roadmap = json.dumps(roadmap)
            db.session.commit()
            return {'status': 'success', 'roadmap': roadmap}
        else:
            return {'error': 'Invalid week index'}, 400
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/self-learning/reset-roadmap', methods=['POST'])
@login_required
def reset_roadmap():
    current_user.personalized_roadmap = None
    db.session.commit()
    return {'status': 'success'}


@app.route('/api/self-learning/bookmark', methods=['POST'])
@login_required
def bookmark_lesson():
    data = request.json or {}
    title = data.get('title', '').strip()
    url = data.get('url', '#').strip()
    action = data.get('action', 'add').strip()
    
    if not title:
        return {'error': 'Title is required'}, 400
        
    try:
        bookmarks = json.loads(current_user.bookmarks_json) if current_user.bookmarks_json else []
    except Exception:
        bookmarks = []
        
    if action == 'add':
        if not any(b['title'] == title for b in bookmarks):
            bookmarks.append({'title': title, 'url': url})
    elif action == 'remove':
        bookmarks = [b for b in bookmarks if b['title'] != title]
        
    current_user.bookmarks_json = json.dumps(bookmarks)
    db.session.commit()
    
    return {'status': 'success', 'bookmarks': bookmarks}


@app.route('/api/self-learning/generate-flashcards', methods=['POST'])
@login_required
def generate_flashcards():
    data = request.json or {}
    material_id = data.get('material_id')
    
    material = None
    if material_id:
        material = db.session.get(Material, material_id)
        
    content = ""
    if material:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], material.file_path)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                pass
    if not content and material:
        content = f"Title: {material.title}. Description: {material.description or ''}"
    if not content:
        content = "General CS principles, coding syntax, algorithms, database operations, and software engineering."
        
    if len(content) > 5000:
        content = content[:5000]
        
    prompt = f"""
    Based on the following course material, generate 4 interactive study flashcards (Question/Answer pairs).
    Return ONLY a JSON object matching this structure:
    {{
      "flashcards": [
        {{
          "question": "Question text?",
          "answer": "Answer text."
        }},
        ...
      ]
    }}
    
    Content:
    {content}
    """
    
    fallback = {
        "flashcards": [
            {
                "question": f"What is the main theme of {material.title if material else 'this course'}?",
                "answer": "Covers essential terms, core paradigms, and foundational rules of the field."
            },
            {
                "question": "Why is regular practice critical for this module?",
                "answer": "It builds cognitive muscle memory and lets you troubleshoot syntax errors or logical bottlenecks."
            },
            {
                "question": "How does this lesson connect to advanced topics?",
                "answer": "It acts as a building block for system design, normalization, and optimization."
            },
            {
                "question": "What is the recommended next step after reading?",
                "answer": "Generate practice quizzes, take notes, and build calculator or weather projects."
            }
        ]
    }
    
    res = query_gemini_json(prompt, fallback)
    return res


@app.route('/api/self-learning/generate-open-questions', methods=['POST'])
@login_required
def generate_open_questions():
    data = request.json or {}
    material_id = data.get('material_id')
    
    material = None
    if material_id:
        material = db.session.get(Material, material_id)
        
    content = ""
    if material:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], material.file_path)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                pass
    if not content and material:
        content = f"Title: {material.title}. Description: {material.description or ''}"
    if not content:
        content = "General programming concepts, SQL syntax, or CSS styling."
        
    if len(content) > 5000:
        content = content[:5000]
        
    prompt = f"""
    Based on the following content, write 2 deep, open-ended conceptual questions to test the student's understanding.
    Return ONLY a JSON object matching this structure:
    {{
      "questions": [
        {{
          "id": 1,
          "question_text": "Detailed question prompt..."
        }},
        {{
          "id": 2,
          "question_text": "Detailed question prompt..."
        }}
      ]
    }}
    
    Content:
    {content}
    """
    
    fallback = {
        "questions": [
            {
                "id": 1,
                "question_text": f"In your own words, explain the core challenge described in the module '{material.title if material else 'study slides'}' and how to solve it."
            },
            {
                "id": 2,
                "question_text": f"How do the concepts in '{material.title if material else 'this syllabus'}' apply to building real-world enterprise applications?"
            }
        ]
    }
    
    res = query_gemini_json(prompt, fallback)
    return res


@app.route('/api/self-learning/submit-ai-question', methods=['POST'])
@login_required
def submit_ai_question():
    data = request.json or {}
    question = data.get('question', '').strip()
    answer = data.get('answer', '').strip()
    
    if not question or not answer:
        return {'evaluation': 'Please write your response.'}, 400
        
    prompt = f"""
    Evaluate the student's answer to the study question.
    Provide constructive feedback.
    
    Question: {question}
    Student Answer: {answer}
    
    Return ONLY a JSON object with a single 'evaluation' key containing your review formatted in markdown. Include a score (e.g. Score: 8/10), Strengths, and Areas for Improvement.
    """
    
    fallback = {
        "evaluation": f"### Evaluation Feedback\n\n- **Score**: 8/10\n- **Strengths**: Your response addresses the question.\n- **Improvement**: Try incorporating specific definitions from the slides."
    }
    
    res = query_gemini_json(prompt, fallback)
    return res


@app.route('/api/self-learning/generate-notes', methods=['POST'])
@login_required
def generate_notes():
    data = request.json or {}
    material_id = data.get('material_id')
    
    material = None
    if material_id:
        material = db.session.get(Material, material_id)
        
    content = ""
    if material:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], material.file_path)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                pass
    if not content and material:
        content = f"Title: {material.title}. Description: {material.description or ''}"
    if not content:
        content = "Core principles of computer science, SQL tables, and algorithms."
        
    if len(content) > 5000:
        content = content[:5000]
        
    prompt = f"""
    Based on the following content, write a structured study revision notes block.
    Return ONLY a JSON object matching this structure:
    {{
      "notes": "### Revision Notes for {material.title if material else 'Topic'}\\n\\n- **Key Point 1**: Description\\n- **Key Point 2**: Description\\n- **Cheat Sheet**: Quick summary details"
    }}
    
    Content:
    {content}
    """
    
    fallback = {
        "notes": f"### Revision Notes: {material.title if material else 'Course Material'}\n\n- **Core Summary**: Focuses on key workflows, definitions, and implementation guides.\n- **Key Terminology**: Covers basic attributes and syntax methods.\n- **Cheat Sheet**: Remember to always write test assertions and clean functions."
    }
    
    res = query_gemini_json(prompt, fallback)
    return res


@app.route('/verify-certificate/<string:code>')
def verify_certificate(code):
    cert = Certificate.query.filter_by(certificate_code=code).first()
    return render_template('verify_certificate.html', cert=cert, code=code)


# Serve Uploaded files
@app.route('/uploads/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Main Entry Point
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
