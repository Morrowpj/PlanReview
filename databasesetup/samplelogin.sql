DROP TABLE userData;
CREATE TABLE userData (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    openai_api_key VARCHAR(255),
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    profile_picture_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    role VARCHAR(20) CHECK (role IN ('user', 'admin', 'moderator')) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMP NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',
    preferences JSONB,
    subscription_plan VARCHAR(20) CHECK (subscription_plan IN ('free', 'basic', 'premium')) DEFAULT 'free',
    api_usage_quota INTEGER DEFAULT 1000,
    api_calls_used INTEGER DEFAULT 0
);

CREATE INDEX idx_username ON userData(username);
CREATE INDEX idx_email ON userData(email);
CREATE INDEX idx_active_users ON userData(is_active);
CREATE INDEX idx_last_login ON userData(last_login);