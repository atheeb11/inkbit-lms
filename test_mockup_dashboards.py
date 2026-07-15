import unittest
from app import app, db
from models import User

class TestMockupDashboards(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        from app import seed_database
        seed_database(seed_courses=True)

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def test_login_page_renders(self):
        print("\nTesting login page rendering...")
        res = self.client.get('/login')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Welcome Back!', res.data)
        self.assertIn(b'InkBit', res.data)
        print("Login page rendered successfully.")

    def test_register_page_renders(self):
        print("\nTesting register page rendering...")
        res = self.client.get('/register')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Create Account', res.data)
        print("Register page rendered successfully.")

    def test_student_dashboard(self):
        print("\nTesting Student Dashboard...")
        # Login
        self.client.post('/login', data={
            'email': 'student@inkbit.com',
            'password': 'inkbit123'
        })
        # Access index
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Steve Student', res.data)
        self.assertIn(b'Enrolled Courses', res.data)
        self.assertIn(b'Assignments Due', res.data)
        print("Student dashboard verified successfully.")

    def test_self_learning_dashboard(self):
        print("\nTesting Student Self-Learning Dashboard...")
        # Login
        self.client.post('/login', data={
            'email': 'student@inkbit.com',
            'password': 'inkbit123'
        })
        # Access self-learning page
        res = self.client.get('/self-learning')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Self-Learning Hub', res.data)
        self.assertIn(b'Learning Streak', res.data)
        self.assertIn(b'Your Skills', res.data)
        self.assertIn(b'Mini Projects', res.data)
        print("Self-Learning Dashboard verified successfully.")


    def test_teacher_dashboard(self):
        print("\nTesting Teacher Dashboard...")
        # Login
        self.client.post('/login', data={
            'email': 'teacher@inkbit.com',
            'password': 'inkbit123'
        })
        # Access index
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Turing Teacher', res.data)
        self.assertIn(b'All Subjects & Tutors Directory', res.data)
        self.assertIn(b'My Courses', res.data)
        print("Teacher dashboard verified successfully.")

    def test_institution_dashboard(self):
        print("\nTesting Institution Dashboard...")
        # Login
        self.client.post('/login', data={
            'email': 'institution@inkbit.com',
            'password': 'inkbit123'
        })
        # Access index
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'InkBit Institute', res.data)
        self.assertIn(b'Tutors Registry', res.data)
        self.assertIn(b'Students Registry', res.data)
        print("Institution dashboard verified successfully.")

    def test_tutor_course_authorization(self):
        print("\nTesting Tutor Course Authorization...")
        with app.app_context():
            from models import Course
            course = Course.query.first()
            if not course:
                from app import seed_database
                seed_database(seed_courses=True)
                course = Course.query.first()
            course_id = course.id
            db.session.remove()
            
        # 1. Login as teacher2 (who is not the instructor of the first course)
        self.client.post('/login', data={
            'email': 'teacher2@inkbit.com',
            'password': 'inkbit123'
        })
        
        # 2. Attempt to access other course details
        res = self.client.get(f'/course/{course_id}')
        self.assertEqual(res.status_code, 302)
        
        # 3. Attempt to upload material to other course
        res = self.client.post(f'/course/{course_id}/upload_material', data={
            'title': 'Test Material',
            'description': 'Description'
        })
        self.assertEqual(res.status_code, 302)
        
        print("Tutor course authorization verified successfully.")

    def test_admin_user_management(self):
        print("\nTesting Admin User Management...")
        # 1. Attempt public registration (should succeed with 200 OK since public registration is now enabled)
        from app import app, db
        from models import User
        original_testing = app.config['TESTING']
        app.config['TESTING'] = False
        try:
            res = self.client.get('/register')
            self.assertEqual(res.status_code, 200) # Should render register page successfully
        finally:
            app.config['TESTING'] = original_testing
            
        # 2. Login as Admin/Institution
        self.client.post('/login', data={
            'email': 'institution@inkbit.com',
            'password': 'inkbit123'
        })
        
        # 3. Attempt to create a student without a registration number (should fail validation)
        res = self.client.post('/register', data={
            'name': 'Temp Student Fail',
            'email': 'temp_fail@inkbit.com',
            'password': 'Password123!',
            'role': 'student',
            'registration_number': ''
        })
        with app.app_context():
            user_fail = User.query.filter_by(email='temp_fail@inkbit.com').first()
            self.assertIsNone(user_fail)
        
        # Create a temporary student via admin (with registration number - should succeed)
        res = self.client.post('/register', data={
            'name': 'Temp Student',
            'email': 'temp_student@inkbit.com',
            'password': 'Password123!',
            'role': 'student',
            'registration_number': 'REG-TEST-0001'
        })
        self.assertEqual(res.status_code, 302) # Redirect back after creation
        
        with app.app_context():
            temp_user = User.query.filter_by(email='temp_student@inkbit.com').first()
            self.assertIsNotNone(temp_user)
            self.assertEqual(temp_user.registration_number, 'REG-TEST-0001')
            temp_user_id = temp_user.id
            
        # Attempt to create another student with duplicate registration number (should fail)
        res = self.client.post('/register', data={
            'name': 'Temp Student Duplicate',
            'email': 'temp_dup@inkbit.com',
            'password': 'Password123!',
            'role': 'student',
            'registration_number': 'REG-TEST-0001'
        })
        with app.app_context():
            user_dup = User.query.filter_by(email='temp_dup@inkbit.com').first()
            self.assertIsNone(user_dup)
            
        # 4. Delete the temporary user via admin delete route
        res = self.client.post(f'/admin/delete-user/{temp_user_id}')
        self.assertEqual(res.status_code, 302)
        
        with app.app_context():
            deleted_user = User.query.filter_by(email='temp_student@inkbit.com').first()
            self.assertIsNone(deleted_user)
            
        print("Admin user management verified successfully.")

    def test_first_login_password_change(self):
        print("\nTesting First Login Password Change & 2FA Bypass...")
        from app import app, db
        from models import User
        
        # Clean up any leftover tutor from previous runs
        with app.app_context():
            User.query.filter_by(email='new_tutor@inkbit.com').delete()
            db.session.commit()
            
        # 1. Login as Admin/Institution to create a tutor
        self.client.post('/login', data={
            'email': 'institution@inkbit.com',
            'password': 'inkbit123'
        })
        
        # 2. Register a new teacher/tutor
        self.client.post('/register', data={
            'name': 'New Tutor',
            'email': 'new_tutor@inkbit.com',
            'password': 'Password123!',
            'role': 'teacher'
        })
        
        # Verify that tutor was created with last_login_date = None
        with app.app_context():
            tutor = User.query.filter_by(email='new_tutor@inkbit.com').first()
            self.assertIsNotNone(tutor)
            self.assertIsNone(tutor.last_login_date)
            tutor_id = tutor.id
            
        # Log out admin
        self.client.get('/logout')
        
        # 3. First login as new tutor (should bypass 2FA and login directly, return 302 redirect to index)
        app.config['TEST_2FA'] = True
        try:
            res = self.client.post('/login', data={
                'email': 'new_tutor@inkbit.com',
                'password': 'Password123!'
            })
            # Verify direct login redirect instead of /login-2fa
            self.assertEqual(res.status_code, 302)
            self.assertNotIn('login-2fa', res.headers.get('Location', ''))
        finally:
            app.config['TEST_2FA'] = False
            
        # 4. Change Password via /change-password endpoint
        res = self.client.post('/change-password', data={
            'current_password': 'Password123!',
            'new_password': 'NewPassword123!'
        })
        self.assertEqual(res.status_code, 302) # Redirects back
        
        # Log out tutor
        self.client.get('/logout')
        
        # 5. Subsequent login with new password (should require 2FA since last_login_date is no longer None)
        app.config['TEST_2FA'] = True
        try:
            res = self.client.post('/login', data={
                'email': 'new_tutor@inkbit.com',
                'password': 'NewPassword123!'
            })
            self.assertEqual(res.status_code, 302)
            self.assertIn('login-2fa', res.headers.get('Location', ''))
        finally:
            app.config['TEST_2FA'] = False
            
        # Clean up tutor
        self.client.post('/login', data={
            'email': 'institution@inkbit.com',
            'password': 'inkbit123'
        })
        self.client.post(f'/admin/delete-user/{tutor_id}')
        
        print("First login password change verified successfully.")

    def test_quiz_system_upgrades(self):
        # Test Quiz System Upgrades (New Stats, Review, Explain routes)
        print("\nTesting Quiz System Upgrades...")
        from app import app, db
        from models import Quiz, QuizResult, Question
        
        # 1. Login as tutor and view stats of a quiz
        self.client.post('/login', data={
            'email': 'teacher@inkbit.com',
            'password': 'inkbit123'
        })
        with app.app_context():
            quiz = Quiz.query.first()
            self.assertIsNotNone(quiz)
            quiz_id = quiz.id
            
        res = self.client.get(f'/quiz/stats/{quiz_id}')
        self.assertEqual(res.status_code, 200)
        self.client.get('/logout')
        
        # 2. Login as student, take a quiz, submit it, review it
        self.client.post('/login', data={
            'email': 'student@inkbit.com',
            'password': 'inkbit123'
        })
        
        with app.app_context():
            student = User.query.filter_by(email='student@inkbit.com').first()
            self.assertIsNotNone(student)
            student_id = student.id
            
        # Create a mock result
        with app.app_context():
            # Delete any existing results for this student and quiz
            QuizResult.query.filter_by(student_id=student_id, quiz_id=quiz_id).delete()
            db.session.commit()
            
        # Post answer
        answers = {}
        with app.app_context():
            questions = Question.query.filter_by(quiz_id=quiz_id).all()
            for q in questions:
                answers[str(q.id)] = q.correct_answer
                
        import json
        res = self.client.post(f'/quiz/submit/{quiz_id}', data={
            'answers': json.dumps(answers)
        })
        # Should redirect to review page
        self.assertEqual(res.status_code, 302)
        
        with app.app_context():
            result = QuizResult.query.filter_by(student_id=student_id, quiz_id=quiz_id).first()
            self.assertIsNotNone(result)
            result_id = result.id
            
        # Access review page
        res = self.client.get(f'/quiz/review/{result_id}')
        self.assertEqual(res.status_code, 200)
        
        # Test AI explain api endpoint
        if questions:
            res = self.client.post('/api/ai-explain-question', json={
                'question_id': questions[0].id,
                'selected_choice': 'A'
            })
            self.assertEqual(res.status_code, 200)
            
        # Clean up result
        with app.app_context():
            QuizResult.query.filter_by(id=result_id).delete()
            db.session.commit()
            
        self.client.get('/logout')
        print("Quiz system upgrades verified successfully.")

if __name__ == '__main__':
    unittest.main()
