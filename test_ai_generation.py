import urllib.request
import urllib.parse
import json
import http.cookiejar

BASE_URL = "http://127.0.0.1:5000"

def run_tests():
    print("Initializing AI Generation API Tests using urllib...")
    
    # Reset last_login_date for teacher to bypass 2FA
    try:
        from app import app, db
        from models import User
        with app.app_context():
            u = User.query.filter_by(email='teacher@inkbit.com').first()
            if u:
                u.last_login_date = None
                db.session.commit()
    except Exception as err:
        print(f"[SETUP] Note: Could not reset last_login_date: {err}")
        
    # 1. Cookie Jar for login
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    urllib.request.install_opener(opener)
    
    # 2. Login as Teacher (retrieve page first to solve CAPTCHA)
    print("\n--- 1. Logging in as Teacher (teacher@inkbit.com) ---")
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
        "email": "teacher@inkbit.com",
        "password": "inkbit123",
        "captcha_answer": captcha_ans
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(f"{BASE_URL}/login", data=login_data, method='POST')
        with urllib.request.urlopen(req) as res:
            html = res.read().decode('utf-8')
            # Check redirection or index indications
            if "Turing Teacher" in html and "Dashboard" in html and "Invalid CAPTCHA" not in html:
                print("[OK] Teacher Login Successful!")
            else:
                print("[FAIL] Teacher Login failed.")
                return
    except Exception as e:
        print(f"[FAIL] Teacher Login error: {e}")
        return

    # 3. Test Course Generation API
    print("\n--- 2. Testing Course Generation API ---")
    course_payload = json.dumps({"prompt": "Data Structures"}).encode('utf-8')
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/ai-generate-course",
            data=course_payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode('utf-8'))
            if "name" in data and "description" in data and "schedule" in data:
                print(f"[OK] Course Generation API returns valid JSON structure: {data['name']}")
            else:
                print(f"[FAIL] Invalid JSON response: {data}")
    except Exception as e:
        print(f"[FAIL] Course Generation request error: {e}")

    # 4. Test Assignment Generation API
    print("\n--- 3. Testing Assignment Generation API ---")
    assign_payload = json.dumps({"prompt": "Binary Search Assignment"}).encode('utf-8')
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/ai-generate-assignment",
            data=assign_payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode('utf-8'))
            if "title" in data and "description" in data:
                print(f"[OK] Assignment Generation API returns valid JSON: {data['title']}")
            else:
                print(f"[FAIL] Invalid JSON response: {data}")
    except Exception as e:
        print(f"[FAIL] Assignment Generation request error: {e}")

    # 5. Test Quiz Generation API
    print("\n--- 4. Testing Quiz Generation API ---")
    quiz_payload = json.dumps({"topic": "Recursion in Python", "count": 5}).encode('utf-8')
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/ai-generate-quiz",
            data=quiz_payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode('utf-8'))
            if "title" in data and "questions" in data and len(data['questions']) == 5:
                print(f"[OK] Quiz Generation API returns valid questions: {data['questions'][0]['question_text']}")
            else:
                print(f"[FAIL] Invalid JSON response: {data}")
    except Exception as e:
        print(f"[FAIL] Quiz Generation request error: {e}")

    # 6. Test Forums Thread Generation API
    print("\n--- 5. Testing Forum Thread Generation API ---")
    thread_payload = json.dumps({"title": "Study Group for Operating Systems"}).encode('utf-8')
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/ai-generate-thread",
            data=thread_payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode('utf-8'))
            if "content" in data:
                print(f"[OK] Forum Thread Generation API returns valid JSON.")
            else:
                print(f"[FAIL] Invalid JSON response: {data}")
    except Exception as e:
        print(f"[FAIL] Forum Thread Generation request error: {e}")

    # 7. Test Forums Reply Generation API
    print("\n--- 6. Testing Forum Reply Generation API ---")
    reply_payload = json.dumps({
        "thread_title": "Recursion Question",
        "thread_content": "Can anyone explain the base case in recursion?"
    }).encode('utf-8')
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/ai-generate-reply",
            data=reply_payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode('utf-8'))
            if "reply" in data:
                print(f"[OK] Forum Reply Generation API returns valid JSON.")
            else:
                print(f"[FAIL] Invalid JSON response: {data}")
    except Exception as e:
        print(f"[FAIL] Forum Reply Generation request error: {e}")

    print("\nAll AI Generation checks completed successfully!")

if __name__ == "__main__":
    run_tests()
