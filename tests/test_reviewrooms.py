import pytest
from fastapi import status
from datetime import datetime
import io

class TestGetReviewRooms:
    """Test getting user review rooms"""

    def test_get_empty_reviewrooms(self, client, auth_headers):
        """Test user with no review rooms"""
        response = client.get("/api/reviewrooms", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["reviewrooms"] == []

    def test_get_user_reviewrooms(self, client, auth_headers, test_review_room):
        """Test user with review rooms"""
        response = client.get("/api/reviewrooms", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert len(data["reviewrooms"]) == 1
        
        room = data["reviewrooms"][0]
        assert room["review_room_id"] == test_review_room.review_room_id
        assert room["title"] == test_review_room.title
        assert room["is_favorite"] is False

    def test_reviewrooms_ordering(self, client, auth_headers, created_user, db_session):
        """Test review rooms ordered by last_message_at"""
        from api.utils.models import ReviewRooms
        
        older_room = ReviewRooms(
            title="Older Room",
            user_id=created_user.user_id,
            pdf_files=[],
            last_message_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        newer_room = ReviewRooms(
            title="Newer Room",
            user_id=created_user.user_id,
            pdf_files=[],
            last_message_at=datetime(2023, 1, 2, 12, 0, 0)
        )
        
        db_session.add(older_room)
        db_session.add(newer_room)
        db_session.commit()
        
        response = client.get("/api/reviewrooms", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data["reviewrooms"]) == 2
        assert data["reviewrooms"][0]["title"] == "Newer Room"
        assert data["reviewrooms"][1]["title"] == "Older Room"

    def test_get_reviewrooms_unauthorized(self, client):
        """Test getting review rooms without authentication"""
        response = client.get("/api/reviewrooms")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reviewrooms_user_isolation(self, client, auth_headers, second_user, db_session):
        """Test users only see their own review rooms"""
        from api.utils.models import ReviewRooms
        
        other_user, _ = second_user
        other_room = ReviewRooms(
            title="Other User's Room",
            user_id=other_user.user_id,
            pdf_files=[],
            last_message_at=datetime.utcnow()
        )
        db_session.add(other_room)
        db_session.commit()
        
        response = client.get("/api/reviewrooms", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["reviewrooms"]) == 0


class TestPDFUpload:
    """Test PDF upload functionality"""

    def test_upload_pdf_success(self, client, auth_headers, test_pdf_content):
        """Test successful PDF upload"""
        files = {"file": ("test.pdf", io.BytesIO(test_pdf_content), "application/pdf")}
        data = {"title": "Test Upload", "municipality": "Test City"}
        
        response = client.post("/api/upload-pdf", files=files, data=data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        
        assert response_data["ok"] is True
        assert "review_room_id" in response_data
        assert response_data["message"] == "PDF uploaded successfully"

    def test_upload_non_pdf_file(self, client, auth_headers):
        """Test uploading non-PDF file"""
        files = {"file": ("test.txt", io.BytesIO(b"Not a PDF"), "text/plain")}
        data = {"title": "Test Upload"}
        
        response = client.post("/api/upload-pdf", files=files, data=data, headers=auth_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Only PDF files are allowed" in data["detail"]

    def test_upload_oversized_file(self, client, auth_headers):
        """Test uploading file larger than 10MB"""
        # Create a file larger than 10MB
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}
        data = {"title": "Large File"}
        
        response = client.post("/api/upload-pdf", files=files, data=data, headers=auth_headers)
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        data = response.json()
        assert "File size must be less than 10MB" in data["detail"]

    def test_upload_no_file(self, client, auth_headers):
        """Test upload request without file"""
        data = {"title": "No File"}
        
        response = client.post("/api/upload-pdf", data=data, headers=auth_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_upload_with_custom_title(self, client, auth_headers, test_pdf_content, db_session):
        """Test upload with custom title"""
        files = {"file": ("original.pdf", io.BytesIO(test_pdf_content), "application/pdf")}
        data = {"title": "Custom Title", "municipality": "Test City"}
        
        response = client.post("/api/upload-pdf", files=files, data=data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        
        # Check title in database
        from api.utils.models import ReviewRooms
        room = db_session.query(ReviewRooms).filter(
            ReviewRooms.review_room_id == response_data["review_room_id"]
        ).first()
        assert room.title == "Custom Title"

    def test_upload_filename_sanitization(self, client, auth_headers, test_pdf_content, db_session):
        """Test secure filename handling"""
        unsafe_filename = "../../../dangerous.pdf"
        files = {"file": (unsafe_filename, io.BytesIO(test_pdf_content), "application/pdf")}
        
        response = client.post("/api/upload-pdf", files=files, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        
        # Check sanitized filename was used
        from api.utils.models import ReviewRooms
        room = db_session.query(ReviewRooms).filter(
            ReviewRooms.review_room_id == response_data["review_room_id"]
        ).first()
        # Title should be sanitized (secure_filename removes dangerous parts)
        assert "../" not in room.title


class TestPDFRetrieval:
    """Test PDF file retrieval"""

    def test_get_pdf_success(self, client, auth_headers, test_review_room):
        """Test successful PDF download"""
        room_id = test_review_room.review_room_id
        response = client.get(f"/api/reviewrooms/{room_id}/pdf", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/pdf"
        assert "Content-Disposition" in response.headers
        assert test_review_room.title in response.headers["Content-Disposition"]

    def test_get_nonexistent_pdf(self, client, auth_headers):
        """Test getting PDF from non-existent review room"""
        response = client.get("/api/reviewrooms/99999/pdf", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"]

    def test_get_pdf_no_file(self, client, auth_headers, created_user, db_session):
        """Test getting PDF from review room without file"""
        from api.utils.models import ReviewRooms
        
        empty_room = ReviewRooms(
            title="Empty Room",
            user_id=created_user.user_id,
            pdf_files=[],
            last_message_at=datetime.utcnow()
        )
        db_session.add(empty_room)
        db_session.commit()
        db_session.refresh(empty_room)
        
        response = client.get(f"/api/reviewrooms/{empty_room.review_room_id}/pdf", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "No PDF found" in data["detail"]

    def test_get_other_user_pdf(self, client, auth_headers, second_user, db_session, test_pdf_content):
        """Test accessing another user's PDF"""
        from api.utils.models import ReviewRooms
        
        other_user, _ = second_user
        other_room = ReviewRooms(
            title="Other User's Room",
            user_id=other_user.user_id,
            pdf_files=[test_pdf_content],
            last_message_at=datetime.utcnow()
        )
        db_session.add(other_room)
        db_session.commit()
        db_session.refresh(other_room)
        
        response = client.get(f"/api/reviewrooms/{other_room.review_room_id}/pdf", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_pdf_caching_headers(self, client, auth_headers, test_review_room):
        """Test proper cache headers on PDF response"""
        room_id = test_review_room.review_room_id
        response = client.get(f"/api/reviewrooms/{room_id}/pdf", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        assert "ETag" in response.headers
        assert "Cache-Control" in response.headers
        assert "private" in response.headers["Cache-Control"]
        assert "max-age=3600" in response.headers["Cache-Control"]

    def test_pdf_etag_generation(self, client, auth_headers, test_review_room):
        """Test ETag generation for PDF caching"""
        room_id = test_review_room.review_room_id
        
        # Make two requests
        response1 = client.get(f"/api/reviewrooms/{room_id}/pdf", headers=auth_headers)
        response2 = client.get(f"/api/reviewrooms/{room_id}/pdf", headers=auth_headers)
        
        # ETags should be identical for same content
        assert response1.headers["ETag"] == response2.headers["ETag"]


class TestPDFInfo:
    """Test PDF metadata endpoints"""

    def test_get_pdf_info_success(self, client, auth_headers, test_review_room):
        """Test getting PDF metadata"""
        room_id = test_review_room.review_room_id
        response = client.get(f"/api/reviewrooms/{room_id}/pdf/info", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["review_room_id"] == room_id
        assert data["title"] == test_review_room.title
        assert data["has_pdf"] is True
        assert "etag" in data
        assert data["pdf_url"] == f"/api/reviewrooms/{room_id}/pdf"

    def test_get_pdf_info_not_found(self, client, auth_headers):
        """Test getting info for non-existent review room"""
        response = client.get("/api/reviewrooms/99999/pdf/info", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_pdf_info_structure(self, client, auth_headers, test_review_room):
        """Test proper PDF info response structure"""
        room_id = test_review_room.review_room_id
        response = client.get(f"/api/reviewrooms/{room_id}/pdf/info", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        required_fields = ["ok", "review_room_id", "title", "has_pdf", "etag", "pdf_url"]
        for field in required_fields:
            assert field in data


class TestPlanReview:
    """Test plan review submission"""

    def test_submit_plan_stormwater_reviewer(self, client, auth_headers, test_review_room, mock_planreview):
        """Test submitting plan to stormwater reviewer"""
        room_id = test_review_room.review_room_id
        submission_data = {"reviewer_name": "Stormwater Reviewer"}
        
        response = client.post(
            f"/api/reviewrooms/{room_id}/submit-plan",
            json=submission_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["message"] == "Plan submitted for review successfully"
        assert "review_comments" in data
        assert "prompt_id" in data

    def test_submit_plan_custom_reviewer(self, client, auth_headers, test_review_room, mock_planreview):
        """Test submitting plan to specific reviewer"""
        room_id = test_review_room.review_room_id
        submission_data = {"reviewer_name": "Building Reviewer"}
        
        response = client.post(
            f"/api/reviewrooms/{room_id}/submit-plan",
            json=submission_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        
        # Verify correct method was called
        mock_planreview.submit_plan_to_reviewer.assert_called_once()

    def test_submit_plan_no_pdf(self, client, auth_headers, created_user, db_session, mock_planreview):
        """Test submitting plan from room without PDF"""
        from api.utils.models import ReviewRooms
        
        empty_room = ReviewRooms(
            title="Empty Room",
            user_id=created_user.user_id,
            pdf_files=[],
            last_message_at=datetime.utcnow()
        )
        db_session.add(empty_room)
        db_session.commit()
        db_session.refresh(empty_room)
        
        submission_data = {"reviewer_name": "Stormwater Reviewer"}
        response = client.post(
            f"/api/reviewrooms/{empty_room.review_room_id}/submit-plan",
            json=submission_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "No PDF found" in data["detail"]

    def test_submit_plan_unauthorized(self, client, test_review_room):
        """Test submitting plan without authentication"""
        room_id = test_review_room.review_room_id
        submission_data = {"reviewer_name": "Stormwater Reviewer"}
        
        response = client.post(f"/api/reviewrooms/{room_id}/submit-plan", json=submission_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_submit_plan_service_unavailable(self, client, auth_headers, test_review_room, mocker):
        """Test when planreview service is unavailable"""
        mocker.patch('api.routers.reviewrooms.planreview', None)
        
        room_id = test_review_room.review_room_id
        submission_data = {"reviewer_name": "Stormwater Reviewer"}
        
        response = client.post(
            f"/api/reviewrooms/{room_id}/submit-plan",
            json=submission_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Plan review service not available" in data["detail"]

    def test_review_comments_saved(self, client, auth_headers, test_review_room, mock_planreview, db_session):
        """Test that review comments are saved to database"""
        room_id = test_review_room.review_room_id
        submission_data = {"reviewer_name": "Stormwater Reviewer"}
        
        response = client.post(
            f"/api/reviewrooms/{room_id}/submit-plan",
            json=submission_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check comments were saved
        db_session.refresh(test_review_room)
        assert test_review_room.review_comments is not None
        assert "comments" in test_review_room.review_comments


class TestReviewComments:
    """Test review comments retrieval"""

    def test_get_review_comments(self, client, auth_headers, test_review_room, db_session):
        """Test getting saved review comments"""
        # Add comments to review room
        test_review_room.review_comments = {
            "comments": [
                {"type": "info", "message": "Test comment"}
            ]
        }
        db_session.commit()
        
        room_id = test_review_room.review_room_id
        response = client.get(f"/api/reviewrooms/{room_id}/comments", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["review_room_id"] == room_id
        assert data["title"] == test_review_room.title
        assert len(data["review_comments"]["comments"]) == 1

    def test_get_comments_not_found(self, client, auth_headers):
        """Test getting comments for non-existent review room"""
        response = client.get("/api/reviewrooms/99999/comments", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_empty_comments(self, client, auth_headers, test_review_room):
        """Test getting comments from room without review comments"""
        room_id = test_review_room.review_room_id
        response = client.get(f"/api/reviewrooms/{room_id}/comments", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["review_comments"] == {"comments": []}


class TestReviewerManagement:
    """Test reviewer management endpoints"""

    def test_get_available_reviewers(self, client, auth_headers, mock_planreview):
        """Test getting list of available reviewers"""
        response = client.get("/api/reviewers", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert "reviewers" in data
        assert len(data["reviewers"]) == 2
        
        reviewer_names = [r["name"] for r in data["reviewers"]]
        assert "Stormwater Reviewer" in reviewer_names
        assert "Building Reviewer" in reviewer_names

    def test_get_reviewers_service_unavailable(self, client, auth_headers, mocker):
        """Test when reviewer service is not available"""
        mocker.patch('api.routers.reviewrooms.planreview', None)
        
        response = client.get("/api/reviewers", headers=auth_headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Reviewer service not available" in data["detail"]