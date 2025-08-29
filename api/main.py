import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils import engine
from utils.models import Base
from routers import auth, conversations, chat, reviewrooms

# Create database tables (only in production, not during testing)
if not os.environ.get('TESTING', False):
    Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="PlanReview API",
    description="FastAPI backend for PlanReview application",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(chat.router)
app.include_router(reviewrooms.router)

@app.get("/")
async def root():
    """API root endpoint"""
    return {"message": "PlanReview API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)