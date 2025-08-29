from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class ReviewRoomResponse(BaseModel):
    review_room_id: int
    title: str
    last_message_at: Optional[datetime] = None
    is_favorite: bool = False

class ReviewRoomsListResponse(BaseModel):
    ok: bool
    reviewrooms: List[ReviewRoomResponse] = []

class PDFUploadResponse(BaseModel):
    ok: bool
    review_room_id: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None

class PDFInfoResponse(BaseModel):
    ok: bool
    review_room_id: int
    title: str
    has_pdf: bool
    etag: str
    last_modified: Optional[str] = None
    pdf_url: str

class ReviewSubmissionRequest(BaseModel):
    reviewer_name: Optional[str] = "Stormwater Reviewer"

class ReviewCommentsResponse(BaseModel):
    ok: bool
    review_room_id: int
    title: str
    review_comments: Dict[str, Any]

class OCRResponse(BaseModel):
    ok: bool
    review_room_id: int
    title: str
    ocr_data: List[Dict[str, Any]]
    total_elements: Optional[int] = None
    total_blocks: Optional[int] = None

class ReviewerResponse(BaseModel):
    ok: bool
    reviewers: List[Dict[str, Any]]