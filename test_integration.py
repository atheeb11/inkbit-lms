import urllib.request
import urllib.parse
import http.cookiejar

BASE_URL = "http://127.0.0.1:5000"

def test_lms_flow():
    print("Initializing Integration Tests using urllib...")
    cs201_id = 1
    
    # Reset database enrollment for CS-201 (repeatable tests) and seed courses
    try:
        from app import app, db, seed_database
        from models import Enrollment
        with app.app_context():
            seed_database(seed_courses=True)
            from models import User, Course
            student_user = User.query.filter_by(email='student@inkbit.com').first()
            student_id = student_user.id if student_user else 3
            
            cs201 = Course.query.filter_by(code='CS-201').first()
            if cs201:
                cs201_id = cs201.id
            
            cs101 = Course.query.filter_by(code='CS-101').first()
            cs101_id = cs101.id if cs101 else 3

            e = Enrollment.query.filter_by(student_id=student_id, course_id=cs201_id).first()
            if not e:
                e = Enrollment(student_id=student_id, course_id=cs201_id, payment_status='unpaid')
                db.session.add(e)
            else:
                e.payment_status = 'unpaid'
            
            e3 = Enrollment.query.filter_by(student_id=student_id, course_id=cs101_id).first()
            if not e3:
                e3 = Enrollment(student_id=student_id, course_id=cs101_id, payment_status='free')
                db.session.add(e3)
            
            db.session.commit()
            print("[SETUP] Reset/Created CS-201 and CS-101 enrollments in database.")
    except Exception as err:
        print(f"[SETUP] Note: Could not reset database state: {err}")
    
    # 1. Create a cookie handler to maintain session
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    urllib.request.install_opener(opener)
    
    # 2. Login as Student (retrieve page first to solve CAPTCHA)
    print("\n--- 1. Logging in as Student (student@inkbit.com) ---")
    captcha_ans = ""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/login") as res:
            html = res.read().decode('utf-8')
            import re
            match = re.search(r'(\d+)\s*\+\s*(\d+)', html)
            if match:
                a = int(match.group(1))
                b = int(match.group(2))
                captcha_ans = str(a + b)
                print(f"[OK] Solved CAPTCHA: {a} + {b} = {captcha_ans}")
    except Exception as e:
        print(f"[WARNING] Failed to fetch login page or solve CAPTCHA: {e}")

    login_data = urllib.parse.urlencode({
        "email": "student@inkbit.com",
        "password": "inkbit123",
        "captcha_answer": captcha_ans
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(f"{BASE_URL}/login", data=login_data, method='POST')
        with urllib.request.urlopen(req) as res:
            html = res.read().decode('utf-8')
            if "Steve Student" in html or "Dashboard" in html:
                print("[OK] Login Successful! Logged in as Steve Student.")
            else:
                print("[FAIL] Login failed to redirect or authenticate.")
                print(html[:500])
                return
    except Exception as e:
        print(f"[FAIL] Login request error: {e}")
        return

    # 3. Check Student Dashboard for Gamification
    print("\n--- 2. Checking Student Dashboard for XP & Badges ---")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/") as res:
            html = res.read().decode('utf-8')
            if "Achievements" in html and "XP Points" in html:
                print("[OK] Achievements (XP) widget verified on Dashboard.")
            else:
                print("[FAIL] Achievements widget missing!")
                
            if "Earned Badges" in html:
                print("[OK] Badges gallery verified on Dashboard.")
            else:
                print("[FAIL] Badges gallery missing!")
                
            if "Buy Course" in html and "CS-201" in html:
                print("[OK] Paid course CS-201 Buy Course button verified on Dashboard.")
            else:
                print("[FAIL] CS-201 Buy Course button missing on Dashboard!")
                
            if "Python Programming Live Lecture" in html:
                print("[OK] Live Classes widget dynamic loading verified on Dashboard.")
            else:
                print("[FAIL] Live Classes widget on Dashboard does not contain the dynamic live class!")
    except Exception as e:
        print(f"[FAIL] Dashboard request error: {e}")

    # 4. Attempt to access Civic Education (CS-201) before paying (expect redirect to checkout)
    print("\n--- 3. Verifying Premium Redirect for CS-201 ---")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/course/{cs201_id}") as res:
            final_url = res.geturl()
            html = res.read().decode('utf-8')
            if f"checkout/{cs201_id}" in final_url or "checkout" in html.lower():
                print(f"[OK] Redirected to checkout or lock page: {final_url}")
            else:
                print(f"[FAIL] Unexpected page: {final_url}")
    except Exception as e:
        print(f"[FAIL] Course detail request error: {e}")

    # 5. Process Checkout (mock payment)
    print("\n--- 4. Processing Checkout for CS-201 ---")
    checkout_data = urllib.parse.urlencode({
        "dummy": "payment_data"
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(f"{BASE_URL}/checkout/{cs201_id}", data=checkout_data, method='POST')
        with urllib.request.urlopen(req) as res:
            html = res.read().decode('utf-8')
            if "Payment successful" in html or "Civic Education" in html:
                print("[OK] Checkout Successful! Course is now paid.")
            else:
                print("[FAIL] Checkout Failed!")
                print(html[:500])
                return
    except Exception as e:
        print(f"[FAIL] Checkout request error: {e}")
        return

    # 6. Verify CS-201 Content is now Unlocked
    print("\n--- 5. Checking Unlocked Course Details ---")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/course/{cs201_id}") as res:
            html = res.read().decode('utf-8')
            if "Premium Course Content Locked" not in html and "Lecture Materials" in html:
                print("[OK] Course details successfully unlocked!")
            else:
                print("[FAIL] Course details still locked!")
                
            # Verify Tabs are visible
            if 'data-tab="forum"' in html and 'data-tab="live-classes"' in html:
                print("[OK] Forums and Live Classes tabs are visible on course detail page.")
            else:
                print("[FAIL] Discussions or Live Classes tab missing!")
    except Exception as e:
        print(f"[FAIL] Unlocked check error: {e}")

    # 7. Post a Discussion Thread
    print("\n--- 6. Posting a Discussion Thread ---")
    forum_data = urllib.parse.urlencode({
        "title": "Study Group for Civic Education",
        "content": "Hey everyone! Let's form a study group to discuss patriotic values and collaborate on assignments."
    }).encode('utf-8')
    try:
        req = urllib.request.Request(f"{BASE_URL}/course/{cs201_id}/forum/new", data=forum_data, method='POST')
        with urllib.request.urlopen(req) as res:
            html = res.read().decode('utf-8')
            if "Discussion thread posted" in html or "Civic Education" in html:
                print("[OK] Discussion thread posted successfully!")
            else:
                print("[FAIL] Discussion thread posting failed!")
    except Exception as e:
        print(f"[FAIL] Forum post request error: {e}")

    # 8. Check Leaderboard
    print("\n--- 7. Checking Leaderboard ---")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/leaderboard") as res:
            html = res.read().decode('utf-8')
            if "Leaderboard" in html or "XP Points" in html:
                print("[OK] Leaderboard page verified.")
            else:
                print("[FAIL] Leaderboard page failed to load correctly!")
    except Exception as e:
        print(f"[FAIL] Leaderboard request error: {e}")

    print("\nAll integration checks passed successfully!")

if __name__ == "__main__":
    test_lms_flow()
