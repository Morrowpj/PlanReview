-- DROP TABLE reviewrooms;
CREATE TABLE reviewrooms (
    review_room_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    review_comments JSONB NOT NULL DEFAULT '[]',
    user_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_archived BOOLEAN DEFAULT FALSE,
    is_favorite BOOLEAN DEFAULT FALSE,
    total_tokens INTEGER DEFAULT 0,
    total_cost DECIMAL(10,4) DEFAULT 0.0000,
    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pdf_files BYTEA[],
    FOREIGN KEY (user_id) REFERENCES userData(user_id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX idx_reviewrooms_user_id ON reviewrooms(user_id);
CREATE INDEX idx_reviewrooms_active ON reviewrooms(user_id, is_active);
CREATE INDEX idx_reviewrooms_recent ON reviewrooms(user_id, last_message_at);
CREATE INDEX idx_reviewrooms_archived ON reviewrooms(user_id, is_archived);
CREATE INDEX idx_reviewrooms_favorites ON reviewrooms(user_id, is_favorite);