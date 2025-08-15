from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.utils import secure_filename
from functools import wraps
import udochat
import planreview
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from werkzeug.security import check_password_hash, generate_password_hash
import os
import datetime
import json
import base64
import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image

MAX_LOGIN_ATTEMPTS = 5

def is_azure_deployment():
    """Detect if running in Azure App Service"""
    return (
        os.environ.get('WEBSITE_SITE_NAME') is not None or 
        os.environ.get('AZURE_CLIENT_ID') is not None or
        os.environ.get('WEBSITE_RESOURCE_GROUP') is not None
    )

def get_db_config():
    """Get database configuration based on environment"""
    if is_azure_deployment():
        # Azure production database
        return {
            'user': os.environ.get('DB_USER', 'hpkrhbkroa'),
            'password': os.environ.get('DB_PASSWORD', 'Resident20!)'),
            'host': os.environ.get('DB_HOST', 'planreview-server.postgres.database.azure.com'),
            'port': int(os.environ.get('DB_PORT', '5432')),
            'database': os.environ.get('DB_NAME', 'postgres')
        }
    else:
        # Local development database
        return {
            'user': os.environ.get('DB_USER', 'admin'),
            'password': os.environ.get('DB_PASSWORD', 'admin'),
            'host': os.environ.get('DB_HOST', '127.0.0.1'),
            'port': int(os.environ.get('DB_PORT', '54612')),
            'database': os.environ.get('DB_NAME', 'postgres')
        }

def create_db_pool():
    """Create database connection pool"""
    config = get_db_config()
    if is_azure_deployment():
        # Larger pool for Azure
        return psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=20,
            **config
        )
    else:
        # Smaller pool for local dev
        return psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            **config
        )

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Create connection pool instead of single connection
db_pool = create_db_pool()

def get_db_connection():
    """Get a connection from the pool"""
    return db_pool.getconn()

def return_db_connection(conn):
    """Return a connection to the pool"""
    db_pool.putconn(conn)

from contextlib import contextmanager

@contextmanager
def db_connection():
    """Context manager for database connections"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        return_db_connection(conn)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
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
    pwd_hash = generate_password_hash(password)

    if not username or not password:
        return jsonify({"ok": False, "error": "username and password required for signup"}), 400

    with db_connection() as cnx:
        with cnx.cursor() as cur:
            login_time = datetime.datetime.now()
            # 1) insert login credentials into database
            cur.execute(
                """
                INSERT INTO userdata (username, email, password_hash, login_attempts, last_login)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                RETURNING user_id
                """,
                (username, username, pwd_hash, 0, login_time)
            )

            row = cur.fetchone()
            cnx.commit()

            if row is None:
                # Email already exists (unique violation handled by ON CONFLICT)
                return jsonify({"ok": False, "error": "Email is already registered"}), 409

            user_id = row[0]
            session['user_id'] = user_id
            session['username'] = username
            return jsonify({"ok": True, "user_id": user_id, "message": "Signup successful"}), 201

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    pwd_hash = generate_password_hash(password)

    if not username or not password:
        return jsonify({"ok": False, "error": "username and password required for signin"}), 400

    with db_connection() as cnx:
        try:
            with cnx.cursor() as cur:
                # 1) Lock the row to prevent race conditions on attempts
                cur.execute(
                    f"""
                    SELECT user_id, password_hash, login_attempts
                    FROM userdata
                    WHERE username = %s
                    FOR UPDATE
                    """,
                    (username,)
                )
                row = cur.fetchone()

                if row is None:
                    # Unknown user: don't reveal that; same message as bad password
                    return jsonify({"ok": False, "error": "Invalid credentials"}), 401

                user_id, password_hash, attempts = row

                # 2) Check lockout
                if attempts >= MAX_LOGIN_ATTEMPTS:
                    return jsonify({"ok": False, "error": "Account locked due to too many attempts"}), 423

                # 3) Verify password
                if check_password_hash(password_hash, password):
                    # Success: reset attempts and update last_login atomically
                    cur.execute(
                        f"""
                        UPDATE userdata
                        SET login_attempts = 0,
                            last_login = NOW()
                        WHERE user_id = %s
                        """,
                        (user_id,)
                    )
                    cnx.commit()
                    session['user_id'] = user_id
                    session['username'] = username
                    return jsonify({"ok": True, "message": "Login successful"}), 200
                else:
                    # Failure: increment attempts and return status
                    cur.execute(
                        """
                        UPDATE userdata
                        SET login_attempts = COALESCE(login_attempts, 0) + 1
                        WHERE user_id = %s
                        RETURNING login_attempts
                        """,
                        (user_id,)
                    )
                    new_attempts = cur.fetchone()[0]
                    cnx.commit()

                    if new_attempts >= MAX_LOGIN_ATTEMPTS:
                        return jsonify({"ok": False, "error": "Account locked due to too many attempts"}), 423
                    return jsonify({"ok": False, "error": "Invalid credentials"}), 401

        except Exception as e:
            # Roll back on any error
            cnx.rollback()
            print(e)
            # Avoid leaking internals in prod; log e server-side instead
            return jsonify({"ok": False, "error": "Server error"}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"ok": True, "message": "Logged out successfully"}), 200

@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    """
                    SELECT conversation_id, title, last_message_at, conversation_type, is_favorite
                    FROM conversations 
                    WHERE user_id = %s AND is_active = TRUE
                    ORDER BY last_message_at DESC
                    """,
                    (session['user_id'],)
                )
                
                conversations = []
                for row in cur.fetchall():
                    conversations.append({
                        'conversation_id': row[0],
                        'title': row[1],
                        'last_message_at': row[2].isoformat() if row[2] else None,
                        'conversation_type': row[3],
                        'is_favorite': row[4]
                    })
                
                return jsonify({"ok": True, "conversations": conversations}), 200
                
    except Exception as e:
        print(f"Error fetching conversations: {e}")
        return jsonify({"ok": False, "error": "Failed to fetch conversations"}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
@login_required
def get_conversation_messages(conversation_id):
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    """
                    SELECT conversation_history, title 
                    FROM conversations 
                    WHERE conversation_id = %s AND user_id = %s AND is_active = TRUE
                    """,
                    (conversation_id, session['user_id'])
                )
                
                row = cur.fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "Conversation not found"}), 404
                
                conversation_history, title = row
                
                return jsonify({
                    "ok": True, 
                    "conversation_id": conversation_id,
                    "title": title,
                    "messages": conversation_history or []
                }), 200
                
    except Exception as e:
        print(f"Error fetching conversation messages: {e}")
        return jsonify({"ok": False, "error": "Failed to fetch conversation messages"}), 500

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    message = data.get('message', '')
    assistant_id = data.get('assistant_id')
    thread_id = data.get('thread_id')
    conversation_id = data.get('conversation_id')
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    try:
        # Get AI response - Note: For regular chat, you'll need to provide a prompt_id
        # This might need to be updated based on your chat implementation
        result = udochat.create_flask_response(message, prompt_id=assistant_id, conversation_id=thread_id)
        
        if result.get('status') == 'success':
            # Save conversation to database
            conversation_id = save_conversation_to_db(
                conversation_id, 
                message, 
                result.get('response', ''), 
                session['user_id'],
                result.get('prompt_id'),
                result.get('conversation_id')
            )
            result['conversation_id'] = conversation_id
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def save_conversation_to_db(conversation_id, user_message, ai_response, user_id, prompt_id, conversation_api_id):
    """Save or update conversation in the database"""
    try:
        with db_connection as cnx:
            with cnx.cursor() as cur:
                if conversation_id:
                    # Update existing conversation
                    cur.execute(
                        """
                        SELECT conversation_history FROM conversations 
                        WHERE conversation_id = %s AND user_id = %s
                        """,
                        (conversation_id, user_id)
                    )
                    
                    row = cur.fetchone()
                    if row:
                        # Append new messages to existing history
                        current_history = row[0] if row[0] else []
                        current_history.extend([
                            {"role": "user", "content": user_message, "timestamp": datetime.datetime.now().isoformat()},
                            {"role": "assistant", "content": ai_response, "timestamp": datetime.datetime.now().isoformat()}
                        ])
                        
                        cur.execute(
                            """
                            UPDATE conversations 
                            SET conversation_history = %s, 
                                last_message_at = CURRENT_TIMESTAMP,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE conversation_id = %s AND user_id = %s
                            """,
                            (psycopg2.extras.Json(current_history), conversation_id, user_id)
                        )
                        cnx.commit()
                        return conversation_id
                
                # Create new conversation
                # Generate title from first user message (truncate if too long)
                title = user_message[:50] + "..." if len(user_message) > 50 else user_message
                
                conversation_history = [
                    {"role": "user", "content": user_message, "timestamp": datetime.datetime.now().isoformat()},
                    {"role": "assistant", "content": ai_response, "timestamp": datetime.datetime.now().isoformat()}
                ]
                
                cur.execute(
                    """
                    INSERT INTO conversations (title, conversation_history, user_id, last_message_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    RETURNING conversation_id
                    """,
                    (title, psycopg2.extras.Json(conversation_history), user_id)
                )
                
                new_conversation_id = cur.fetchone()[0]
                cnx.commit()
                return new_conversation_id
                
    except Exception as e:
        print(f"Error saving conversation: {e}")
        cnx.rollback()
        return conversation_id  # Return original ID if update fails

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
            
        # Read file content
        file_content = file.read()
        
        # Validate file size (10MB limit)
        if len(file_content) > 10 * 1024 * 1024:
            return jsonify({"ok": False, "error": "File size must be less than 10MB"}), 413
            
        # Get additional data from request
        title = request.form.get('title', secure_filename(file.filename))
        municipality = request.form.get('municipality', '')
        
        # Save to database
        review_room_id = save_pdf_to_reviewroom(
            title=title,
            pdf_content=file_content,
            user_id=session['user_id'],
            filename=secure_filename(file.filename)
        )
        
        if review_room_id:
            return jsonify({
                "ok": True, 
                "review_room_id": review_room_id,
                "message": "PDF uploaded successfully"
            }), 201
        else:
            return jsonify({"ok": False, "error": "Failed to save PDF"}), 500
            
    except Exception as e:
        print(f"Error uploading PDF: {e}")
        return jsonify({"ok": False, "error": "Upload failed"}), 500

def save_pdf_to_reviewroom(title, pdf_content, user_id, filename=""):
    """Save PDF file to reviewrooms database"""
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                # Create new review room with PDF
                cur.execute(
                    """
                    INSERT INTO reviewrooms (title, user_id, pdf_files, last_message_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    RETURNING review_room_id
                    """,
                    (
                        title,
                        user_id,
                        [pdf_content]  # Store as array of BYTEA
                    )
                )
                
                review_room_id = cur.fetchone()[0]
                cnx.commit()
                return review_room_id
                
    except Exception as e:
        print(f"Error saving PDF to database: {e}")
        cnx.rollback()
        return None

@app.route('/api/reviewrooms/<int:review_room_id>/pdf', methods=['GET'])
@login_required
def get_reviewroom_pdf(review_room_id):
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                # First, check if PDF exists and get metadata for caching
                cur.execute(
                    """
                    SELECT title, updated_at
                    FROM reviewrooms 
                    WHERE review_room_id = %s AND user_id = %s AND is_active = TRUE
                    """,
                    (review_room_id, session['user_id'])
                )
                
                metadata_row = cur.fetchone()
                if not metadata_row:
                    return jsonify({"ok": False, "error": "Review room not found"}), 404
                
                title, updated_at = metadata_row
                
                # Create ETag based on review_room_id and updated_at for caching
                import hashlib
                etag = hashlib.md5(f"{review_room_id}-{updated_at}".encode()).hexdigest()
                
                # Check if client has cached version
                if request.headers.get('If-None-Match') == f'"{etag}"':
                    from flask import Response
                    return Response(status=304)  # Not Modified
                
                # Now get the actual PDF data
                cur.execute(
                    """
                    SELECT pdf_files
                    FROM reviewrooms 
                    WHERE review_room_id = %s AND user_id = %s AND is_active = TRUE
                    """,
                    (review_room_id, session['user_id'])
                )
                
                row = cur.fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "Review room not found"}), 404
                
                pdf_files = row[0]
                if not pdf_files or len(pdf_files) == 0:
                    return jsonify({"ok": False, "error": "No PDF found in this review room"}), 404
                
                # Get the first PDF file
                pdf_data = pdf_files[0]
                
                # Create response with PDF data and caching headers
                from flask import Response
                response = Response(
                    pdf_data,
                    mimetype='application/pdf',
                    headers={
                        'Content-Disposition': f'inline; filename="{title}.pdf"',
                        'Content-Type': 'application/pdf',
                        'Content-Length': str(len(pdf_data)),
                        'ETag': f'"{etag}"',
                        'Cache-Control': 'private, max-age=3600',  # Cache for 1 hour
                        'Last-Modified': updated_at.strftime('%a, %d %b %Y %H:%M:%S GMT') if updated_at else ''
                    }
                )
                return response
                
    except Exception as e:
        print(f"Error fetching review room PDF: {e}")
        return jsonify({"ok": False, "error": "Failed to fetch PDF"}), 500

@app.route('/api/reviewrooms/<int:review_room_id>/pdf/info', methods=['GET'])
@login_required
def get_reviewroom_pdf_info(review_room_id):
    """Get PDF metadata without loading the actual PDF data"""
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    """
                    SELECT title, updated_at, 
                           CASE WHEN pdf_files IS NOT NULL AND array_length(pdf_files, 1) > 0 
                                THEN TRUE ELSE FALSE END as has_pdf
                    FROM reviewrooms 
                    WHERE review_room_id = %s AND user_id = %s AND is_active = TRUE
                    """,
                    (review_room_id, session['user_id'])
                )
                
                row = cur.fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "Review room not found"}), 404
                
                title, updated_at, has_pdf = row
                
                if not has_pdf:
                    return jsonify({"ok": False, "error": "No PDF found in this review room"}), 404
                
                # Create ETag for caching consistency
                import hashlib
                etag = hashlib.md5(f"{review_room_id}-{updated_at}".encode()).hexdigest()
                
                return jsonify({
                    "ok": True,
                    "review_room_id": review_room_id,
                    "title": title,
                    "has_pdf": has_pdf,
                    "etag": etag,
                    "last_modified": updated_at.isoformat() if updated_at else None,
                    "pdf_url": f"/api/reviewrooms/{review_room_id}/pdf"
                }), 200
                
    except Exception as e:
        print(f"Error fetching PDF info: {e}")
        return jsonify({"ok": False, "error": "Failed to fetch PDF info"}), 500

@app.route('/api/reviewrooms', methods=['GET'])
@login_required
def get_reviewrooms():
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    """
                    SELECT review_room_id, title, last_message_at, is_favorite
                    FROM reviewrooms 
                    WHERE user_id = %s AND is_active = TRUE
                    ORDER BY last_message_at DESC
                    """,
                    (session['user_id'],)
                )
                
                reviewrooms = []
                for row in cur.fetchall():
                    reviewrooms.append({
                        'review_room_id': row[0],
                        'title': row[1],
                        'last_message_at': row[2].isoformat() if row[2] else None,
                        'is_favorite': row[3]
                    })
                
                return jsonify({"ok": True, "reviewrooms": reviewrooms}), 200
                
    except Exception as e:
        print(f"Error fetching review rooms: {e}")
        return jsonify({"ok": False, "error": "Failed to fetch review rooms"}), 500

@app.route('/api/reviewers', methods=['GET'])
@login_required
def get_available_reviewers():
    """Get list of available reviewers"""
    try:
        reviewers = planreview.load_reviewers()
        return jsonify({
            "ok": True,
            "reviewers": reviewers['reviewers']
        }), 200
    except Exception as e:
        print(f"Error loading reviewers: {e}")
        return jsonify({"ok": False, "error": "Failed to load reviewers"}), 500

@app.route('/api/reviewrooms/<int:review_room_id>/submit-plan', methods=['POST'])
@login_required
def submit_plan_for_review(review_room_id):
    """Submit the first sheet of a plan set to OpenAI Assistants API for review"""
    try:
        # Get reviewer from request body
        data = request.get_json() or {}
        reviewer_name = data.get('reviewer_name', 'Stormwater Reviewer')  # Default to Stormwater
        
        # Get the review room and PDF
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    """
                    SELECT pdf_files, title
                    FROM reviewrooms 
                    WHERE review_room_id = %s AND user_id = %s AND is_active = TRUE
                    """,
                    (review_room_id, session['user_id'])
                )
                
                row = cur.fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "Review room not found"}), 404
                
                pdf_files, title = row
                if not pdf_files or len(pdf_files) == 0:
                    return jsonify({"ok": False, "error": "No PDF found in this review room"}), 404
                
                # Get the first PDF (first sheet)
                first_pdf = pdf_files[0]
                
                # Submit to selected reviewer
                if reviewer_name == 'Stormwater Reviewer':
                    result = planreview.submit_plan_to_stormwater_reviewer(first_pdf, title)
                else:
                    result = planreview.submit_plan_to_reviewer(first_pdf, title, reviewer_name)
                
                if result.get('status') == 'success':
                    comments_data = result.get('comments_data')
                    
                    # Store the review comments in the database
                    cur.execute(
                        """
                        UPDATE reviewrooms 
                        SET review_comments = %s,
                            last_message_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE review_room_id = %s AND user_id = %s
                        """,
                        (psycopg2.extras.Json(comments_data), review_room_id, session['user_id'])
                    )
                    cnx.commit()
                    
                    return jsonify({
                        "ok": True,
                        "message": "Plan submitted for review successfully",
                        "review_comments": comments_data,
                        "prompt_id": result.get('prompt_id'),
                        "conversation_id": result.get('conversation_id')
                    }), 200
                
                else:
                    return jsonify({
                        "ok": False, 
                        "error": result.get('error', 'Unknown error'),
                        "details": result.get('details', '')
                    }), 500
                    
    except Exception as e:
        print(f"Error submitting plan for review: {e}")
        return jsonify({"ok": False, "error": "Failed to submit plan for review"}), 500

@app.route('/api/reviewrooms/<int:review_room_id>/comments', methods=['GET'])
@login_required
def get_review_comments(review_room_id):
    """Get review comments for a specific review room"""
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    """
                    SELECT review_comments, title
                    FROM reviewrooms 
                    WHERE review_room_id = %s AND user_id = %s AND is_active = TRUE
                    """,
                    (review_room_id, session['user_id'])
                )
                
                row = cur.fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "Review room not found"}), 404
                
                review_comments, title = row
                
                return jsonify({
                    "ok": True,
                    "review_room_id": review_room_id,
                    "title": title,
                    "review_comments": review_comments or {"comments": []}
                }), 200
                
    except Exception as e:
        print(f"Error fetching review comments: {e}")
        return jsonify({"ok": False, "error": "Failed to fetch review comments"}), 500

# OCR functions have been moved to planreview.py module

@app.route('/api/reviewrooms/<int:review_room_id>/ocr', methods=['POST'])
@login_required
def extract_ocr_from_review_room(review_room_id):
    """Extract OCR data from a review room's PDF"""
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                # Get the PDF from the review room
                cur.execute(
                    """
                    SELECT pdf_files, title
                    FROM reviewrooms 
                    WHERE review_room_id = %s AND user_id = %s AND is_active = TRUE
                    """,
                    (review_room_id, session['user_id'])
                )
                
                row = cur.fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "Review room not found"}), 404
                
                pdf_files, title = row
                if not pdf_files or len(pdf_files) == 0:
                    return jsonify({"ok": False, "error": "No PDF found in this review room"}), 404
                
                # Get the first PDF (you could modify this to process all PDFs)
                pdf_data = pdf_files[0]
                
                # Extract OCR data (need to add word-level function to planreview module)
                ocr_results = planreview.extract_text_with_ocr_blocks(pdf_data)
                
                return jsonify({
                    "ok": True,
                    "review_room_id": review_room_id,
                    "title": title,
                    "ocr_data": ocr_results,
                    "total_elements": len(ocr_results)
                }), 200
                
    except Exception as e:
        print(f"Error extracting OCR from review room: {e}")
        return jsonify({"ok": False, "error": "Failed to extract OCR data"}), 500

@app.route('/api/reviewrooms/<int:review_room_id>/ocr-blocks', methods=['POST'])
@login_required
def extract_ocr_blocks_from_review_room(review_room_id):
    """Extract OCR data as text blocks from a review room's PDF"""
    try:
        with db_connection() as cnx:
            with cnx.cursor() as cur:
                # Get the PDF from the review room
                cur.execute(
                    """
                    SELECT pdf_files, title
                    FROM reviewrooms 
                    WHERE review_room_id = %s AND user_id = %s AND is_active = TRUE
                    """,
                    (review_room_id, session['user_id'])
                )
                
                row = cur.fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "Review room not found"}), 404
                
                pdf_files, title = row
                if not pdf_files or len(pdf_files) == 0:
                    return jsonify({"ok": False, "error": "No PDF found in this review room"}), 404
                
                # Get the first PDF
                pdf_data = pdf_files[0]
                
                # Extract OCR data as blocks
                ocr_results = planreview.extract_text_with_ocr_blocks(pdf_data)
                
                return jsonify({
                    "ok": True,
                    "review_room_id": review_room_id,
                    "title": title,
                    "ocr_data": ocr_results,
                    "total_blocks": len(ocr_results)
                }), 200
                
    except Exception as e:
        print(f"Error extracting OCR blocks from review room: {e}")
        return jsonify({"ok": False, "error": "Failed to extract OCR data"}), 500

if __name__ == '__main__':
    app.run(debug=True)