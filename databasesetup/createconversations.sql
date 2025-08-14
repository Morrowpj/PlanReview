DROP TABLE conversations;
CREATE TABLE conversations (
    conversation_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    conversation_history JSONB NOT NULL DEFAULT '[]',
    user_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_archived BOOLEAN DEFAULT FALSE,
    is_favorite BOOLEAN DEFAULT FALSE,
    model_used VARCHAR(50) DEFAULT 'gpt-4.1',
    total_tokens INTEGER DEFAULT 0,
    total_cost DECIMAL(10,4) DEFAULT 0.0000,
    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversation_type VARCHAR(20) CHECK (conversation_type IN ('chat', 'completion', 'assistant', 'analysis')) DEFAULT 'chat',
    FOREIGN KEY (user_id) REFERENCES userData(user_id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_active ON conversations(user_id, is_active);
CREATE INDEX idx_conversations_recent ON conversations(user_id, last_message_at);
CREATE INDEX idx_conversations_archived ON conversations(user_id, is_archived);
CREATE INDEX idx_conversations_favorites ON conversations(user_id, is_favorite);
CREATE INDEX idx_conversation_history ON conversations USING GIN(conversation_history);