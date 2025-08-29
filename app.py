from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.utils import secure_filename
from functools import wraps
import httpx
import os
import datetime
import json

# FastAPI service configuration
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:8000/api')

def get_api_headers():
    """Get headers for API requests including auth token if available"""
    headers = {'Content-Type': 'application/json'}
    if 'access_token' in session:
        headers['Authorization'] = f"Bearer {session['access_token']}"
    return headers

def make_api_request(method, endpoint, data=None, files=None):
    """Make a request to the FastAPI service"""
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        with httpx.Client() as client:
            if files:
                # For file uploads, don't set Content-Type header
                headers = {}
                if 'access_token' in session:
                    headers['Authorization'] = f"Bearer {session['access_token']}"
                response = client.request(method, url, headers=headers, data=data, files=files)
            else:
                headers = get_api_headers()
                response = client.request(method, url, headers=headers, json=data)
            
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        print(f"API request failed: {e}")
        return {"ok": False, "error": "API request failed"}
    except httpx.HTTPStatusError as e:
        print(f"API request failed with status {e.response.status_code}: {e}")
        try:
            return e.response.json()
        except:
            return {"ok": False, "error": f"API request failed with status {e.response.status_code}"}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session or 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/sign-up')
def signup_page():
    return render_template('signup.html')

@app.route('/c')
@login_required
def chat_interface():
    return render_template('chat.html')

@app.route('/review-room')
@login_required
def review_room():
    return render_template('reviewroom.html')

@app.post("/api/signup")
def signup():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "error": "username and password required for signup"}), 400

    # Make API request to FastAPI service
    api_data = {"username": username, "password": password}
    result = make_api_request('POST', '/signup', api_data)
    
    if result.get('ok'):
        # If signup successful, automatically log in to get token
        login_result = make_api_request('POST', '/login', api_data)
        if login_result.get('access_token'):
            session['access_token'] = login_result['access_token']
            session['user_id'] = login_result['user_id']
            session['username'] = login_result['username']
            return jsonify({"ok": True, "user_id": login_result['user_id'], "message": "Signup successful"}), 201
    
    return jsonify(result), 409 if 'already registered' in str(result.get('error', '')) else 400

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "error": "username and password required for signin"}), 400

    # Make API request to FastAPI service
    api_data = {"username": username, "password": password}
    result = make_api_request('POST', '/login', api_data)
    
    if result.get('access_token'):
        # Store token and user info in session
        session['access_token'] = result['access_token']
        session['user_id'] = result['user_id']
        session['username'] = result['username']
        return jsonify({"ok": True, "message": "Login successful"}), 200
    
    # Handle error responses
    status_code = 401
    if 'locked' in str(result.get('detail', '')):
        status_code = 423
    elif 'Server error' in str(result.get('detail', '')):
        status_code = 500
    
    return jsonify({"ok": False, "error": result.get('detail', 'Login failed')}), status_code

@app.route('/api/logout', methods=['POST'])
def logout():
    # Call FastAPI logout endpoint if needed
    if 'access_token' in session:
        make_api_request('POST', '/logout')
    
    session.clear()
    return jsonify({"ok": True, "message": "Logged out successfully"}), 200

@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    result = make_api_request('GET', '/conversations')
    if result.get('ok'):
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
@login_required
def get_conversation_messages(conversation_id):
    result = make_api_request('GET', f'/conversations/{conversation_id}')
    if result.get('ok'):
        return jsonify(result), 200
    else:
        status_code = 404 if 'not found' in str(result.get('detail', '')) else 500
        return jsonify(result), status_code

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    
    if not data.get('message'):
        return jsonify({"error": "Message is required"}), 400
    
    # Forward request to FastAPI service
    result = make_api_request('POST', '/chat', data)
    
    if result.get('status') == 'success' or result.get('ok'):
        return jsonify(result), 200
    else:
        return jsonify(result), 500

# Conversation saving is now handled by the FastAPI service

@app.route('/api/upload-pdf', methods=['POST'])
@login_required
def upload_pdf():
    try:
        # Check if file is present in request
        if 'file' not in request.files:
            return jsonify({"ok": False, "error": "No file provided"}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"ok": False, "error": "No file selected"}), 400
            
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({"ok": False, "error": "Only PDF files are allowed"}), 400
        
        # Get additional data from request
        title = request.form.get('title', secure_filename(file.filename))
        municipality = request.form.get('municipality', '')
        
        # Prepare files and data for FastAPI request
        files = {'file': (file.filename, file.stream, file.mimetype)}
        data = {
            'title': title,
            'municipality': municipality
        }
        
        # Forward request to FastAPI service
        result = make_api_request('POST', '/upload-pdf', data=data, files=files)
        
        if result.get('ok'):
            return jsonify(result), 201
        else:
            status_code = 413 if 'size' in str(result.get('detail', '')) else 400
            return jsonify(result), status_code
            
    except Exception as e:
        print(f"Error uploading PDF: {e}")
        return jsonify({"ok": False, "error": "Upload failed"}), 500

# PDF saving is now handled by the FastAPI service

@app.route('/api/reviewrooms/<int:review_room_id>/pdf', methods=['GET'])
@login_required
def get_reviewroom_pdf(review_room_id):
    # Forward request to FastAPI service and return the response
    try:
        url = f"{API_BASE_URL}/reviewrooms/{review_room_id}/pdf"
        headers = {}
        if 'access_token' in session:
            headers['Authorization'] = f"Bearer {session['access_token']}"
        
        # Forward any caching headers from the original request
        if request.headers.get('If-None-Match'):
            headers['If-None-Match'] = request.headers.get('If-None-Match')
        
        with httpx.Client() as client:
            response = client.get(url, headers=headers)
            
            if response.status_code == 304:
                from flask import Response
                return Response(status=304)  # Not Modified
            
            if response.status_code == 200:
                from flask import Response
                return Response(
                    response.content,
                    mimetype=response.headers.get('content-type', 'application/pdf'),
                    headers=dict(response.headers)
                )
            else:
                try:
                    return jsonify(response.json()), response.status_code
                except:
                    return jsonify({"ok": False, "error": "Failed to fetch PDF"}), response.status_code
    except Exception as e:
        print(f"Error fetching review room PDF: {e}")
        return jsonify({"ok": False, "error": "Failed to fetch PDF"}), 500

@app.route('/api/reviewrooms/<int:review_room_id>/pdf/info', methods=['GET'])
@login_required
def get_reviewroom_pdf_info(review_room_id):
    """Get PDF metadata without loading the actual PDF data"""
    result = make_api_request('GET', f'/reviewrooms/{review_room_id}/pdf/info')
    if result.get('ok'):
        return jsonify(result), 200
    else:
        status_code = 404 if 'not found' in str(result.get('detail', '')) else 500
        return jsonify(result), status_code

@app.route('/api/reviewrooms', methods=['GET'])
@login_required
def get_reviewrooms():
    result = make_api_request('GET', '/reviewrooms')
    if result.get('ok'):
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@app.route('/api/reviewers', methods=['GET'])
@login_required
def get_available_reviewers():
    """Get list of available reviewers"""
    result = make_api_request('GET', '/reviewers')
    if result.get('ok'):
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@app.route('/api/reviewrooms/<int:review_room_id>/submit-plan', methods=['POST'])
@login_required
def submit_plan_for_review(review_room_id):
    """Submit the first sheet of a plan set to OpenAI Assistants API for review"""
    data = request.get_json() or {}
    result = make_api_request('POST', f'/reviewrooms/{review_room_id}/submit-plan', data)
    
    if result.get('ok'):
        return jsonify(result), 200
    else:
        status_code = 404 if 'not found' in str(result.get('detail', '')) else 500
        return jsonify(result), status_code

@app.route('/api/reviewrooms/<int:review_room_id>/comments', methods=['GET'])
@login_required
def get_review_comments(review_room_id):
    """Get review comments for a specific review room"""
    result = make_api_request('GET', f'/reviewrooms/{review_room_id}/comments')
    if result.get('ok'):
        return jsonify(result), 200
    else:
        status_code = 404 if 'not found' in str(result.get('detail', '')) else 500
        return jsonify(result), status_code

# OCR functions have been moved to planreview.py module

@app.route('/api/reviewrooms/<int:review_room_id>/ocr', methods=['POST'])
@login_required
def extract_ocr_from_review_room(review_room_id):
    """Extract OCR data from a review room's PDF"""
    result = make_api_request('POST', f'/reviewrooms/{review_room_id}/ocr')
    if result.get('ok'):
        return jsonify(result), 200
    else:
        status_code = 404 if 'not found' in str(result.get('detail', '')) else 500
        return jsonify(result), status_code

@app.route('/api/reviewrooms/<int:review_room_id>/ocr-blocks', methods=['POST'])
@login_required
def extract_ocr_blocks_from_review_room(review_room_id):
    """Extract OCR data as text blocks from a review room's PDF"""
    result = make_api_request('POST', f'/reviewrooms/{review_room_id}/ocr-blocks')
    if result.get('ok'):
        return jsonify(result), 200
    else:
        status_code = 404 if 'not found' in str(result.get('detail', '')) else 500
        return jsonify(result), status_code

if __name__ == '__main__':
    app.run(debug=True)