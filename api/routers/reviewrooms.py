from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename
import hashlib

from api.utils import get_db, ReviewRooms
from api.schemas.reviewrooms import (
    ReviewRoomsListResponse, ReviewRoomResponse, PDFUploadResponse, 
    PDFInfoResponse, ReviewSubmissionRequest, ReviewCommentsResponse, 
    ReviewerResponse
)
from api.schemas.auth import UserResponse
from api.dependencies.auth import get_current_user

# Import the review modules (these would need to be available in your environment)
try:
    import planreview
except ImportError:
    planreview = None

router = APIRouter(prefix="/api", tags=["reviewrooms"])

@router.get("/reviewrooms", response_model=ReviewRoomsListResponse)
async def get_reviewrooms(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get all review rooms for the current user"""
    try:
        reviewrooms = db.query(ReviewRooms).filter(
            ReviewRooms.user_id == current_user.user_id,
            ReviewRooms.is_active == True
        ).order_by(ReviewRooms.last_message_at.desc()).all()
        
        reviewroom_responses = []
        for room in reviewrooms:
            reviewroom_responses.append(ReviewRoomResponse(
                review_room_id=room.review_room_id,
                title=room.title,
                last_message_at=room.last_message_at,
                is_favorite=room.is_favorite
            ))
        
        return ReviewRoomsListResponse(ok=True, reviewrooms=reviewroom_responses)
        
    except Exception as e:
        print(f"Error fetching review rooms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch review rooms"
        )

@router.post("/upload-pdf", response_model=PDFUploadResponse)
async def upload_pdf(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    title: str = Form(None),
    municipality: str = Form("")
):
    """Upload a PDF file to create a new review room"""
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed"
            )
            
        # Read file content
        file_content = await file.read()
        
        # Validate file size (10MB limit)
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size must be less than 10MB"
            )
            
        # Use provided title or filename
        room_title = title or secure_filename(file.filename)
        
        # Create new review room with PDF
        new_room = ReviewRooms(
            title=room_title,
            user_id=current_user.user_id,
            pdf_files=[file_content],  # Store as array of bytes
            last_message_at=datetime.utcnow()
        )
        
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        
        return PDFUploadResponse(
            ok=True,
            review_room_id=new_room.review_room_id,
            message="PDF uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed"
        )

@router.get("/reviewrooms/{review_room_id}/pdf")
async def get_reviewroom_pdf(
    review_room_id: int,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get PDF file from review room"""
    try:
        # Get the review room
        room = db.query(ReviewRooms).filter(
            ReviewRooms.review_room_id == review_room_id,
            ReviewRooms.user_id == current_user.user_id,
            ReviewRooms.is_active == True
        ).first()
        
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review room not found"
            )
        
        if not room.pdf_files or len(room.pdf_files) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No PDF found in this review room"
            )
        
        # Get the first PDF file
        pdf_data = room.pdf_files[0]
        
        # Create ETag based on review_room_id and updated_at for caching
        etag = hashlib.md5(f"{review_room_id}-{room.updated_at}".encode()).hexdigest()
        
        # Create response with PDF data and caching headers
        return Response(
            content=pdf_data,
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="{room.title}.pdf"',
                'Content-Type': 'application/pdf',
                'Content-Length': str(len(pdf_data)),
                'ETag': f'"{etag}"',
                'Cache-Control': 'private, max-age=3600',  # Cache for 1 hour
                'Last-Modified': room.updated_at.strftime('%a, %d %b %Y %H:%M:%S GMT') if room.updated_at else ''
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching review room PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch PDF"
        )

@router.get("/reviewrooms/{review_room_id}/pdf/info", response_model=PDFInfoResponse)
async def get_reviewroom_pdf_info(
    review_room_id: int,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get PDF metadata without loading the actual PDF data"""
    try:
        room = db.query(ReviewRooms).filter(
            ReviewRooms.review_room_id == review_room_id,
            ReviewRooms.user_id == current_user.user_id,
            ReviewRooms.is_active == True
        ).first()
        
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review room not found"
            )
        
        has_pdf = room.pdf_files is not None and len(room.pdf_files) > 0
        
        if not has_pdf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No PDF found in this review room"
            )
        
        # Create ETag for caching consistency
        etag = hashlib.md5(f"{review_room_id}-{room.updated_at}".encode()).hexdigest()
        
        return PDFInfoResponse(
            ok=True,
            review_room_id=review_room_id,
            title=room.title,
            has_pdf=has_pdf,
            etag=etag,
            last_modified=room.updated_at.isoformat() if room.updated_at else None,
            pdf_url=f"/api/reviewrooms/{review_room_id}/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching PDF info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch PDF info"
        )

@router.post("/reviewrooms/{review_room_id}/submit-plan")
async def submit_plan_for_review(
    review_room_id: int,
    request: ReviewSubmissionRequest,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Submit the first sheet of a plan set to OpenAI Assistants API for review"""
    if planreview is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Plan review service not available"
        )
    
    try:
        # Get the review room and PDF
        room = db.query(ReviewRooms).filter(
            ReviewRooms.review_room_id == review_room_id,
            ReviewRooms.user_id == current_user.user_id,
            ReviewRooms.is_active == True
        ).first()
        
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review room not found"
            )
        
        if not room.pdf_files or len(room.pdf_files) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No PDF found in this review room"
            )
        
        # Get the first PDF (first sheet)
        first_pdf = room.pdf_files[0]
        
        # Submit to selected reviewer
        if request.reviewer_name == 'Stormwater Reviewer':
            result = planreview.submit_plan_to_stormwater_reviewer(first_pdf, room.title)
        else:
            result = planreview.submit_plan_to_reviewer(first_pdf, room.title, request.reviewer_name)
        
        if result.get('status') == 'success':
            comments_data = result.get('comments_data')
            
            # Store the review comments in the database
            room.review_comments = comments_data
            room.last_message_at = datetime.utcnow()
            room.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                "ok": True,
                "message": "Plan submitted for review successfully",
                "review_comments": comments_data,
                "prompt_id": result.get('prompt_id'),
                "conversation_id": result.get('conversation_id')
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Unknown error')
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error submitting plan for review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit plan for review"
        )

@router.get("/reviewrooms/{review_room_id}/comments", response_model=ReviewCommentsResponse)
async def get_review_comments(
    review_room_id: int,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get review comments for a specific review room"""
    try:
        room = db.query(ReviewRooms).filter(
            ReviewRooms.review_room_id == review_room_id,
            ReviewRooms.user_id == current_user.user_id,
            ReviewRooms.is_active == True
        ).first()
        
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review room not found"
            )
        
        return ReviewCommentsResponse(
            ok=True,
            review_room_id=review_room_id,
            title=room.title,
            review_comments=room.review_comments or {"comments": []}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching review comments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch review comments"
        )

@router.get("/reviewers", response_model=ReviewerResponse)
async def get_available_reviewers(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
):
    """Get list of available reviewers"""
    if planreview is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reviewer service not available"
        )
    
    try:
        reviewers = planreview.load_reviewers()
        return ReviewerResponse(
            ok=True,
            reviewers=reviewers['reviewers']
        )
    except Exception as e:
        print(f"Error loading reviewers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load reviewers"
        )