-- PostgreSQL initialization script for Condition Task List Trader
-- This script runs when the database container starts

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text similarity search

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_conversations_start_time_desc ON conversations(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_tags_gin ON conversations USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_turns_session_id_created ON conversation_turns(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_patterns_type_updated ON learning_patterns(pattern_type, updated_at DESC);

-- Create text search indexes for conversation search
CREATE INDEX IF NOT EXISTS idx_turns_search ON conversation_turns USING GIN(to_tsvector('english', user_input || ' ' || ai_response));

-- Create monitoring tables
CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_type VARCHAR(50) NOT NULL,
    component VARCHAR(100) NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(20),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_system_metrics_type ON system_metrics(metric_type, component);

-- Create audit table for compliance
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL,
    component VARCHAR(100) NOT NULL,
    user_id UUID,
    session_id UUID,
    details JSONB NOT NULL,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    severity VARCHAR(20) DEFAULT 'info'
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_session_id ON audit_log(session_id);

-- Create performance monitoring tables
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation VARCHAR(100) NOT NULL,
    duration_ms FLOAT NOT NULL,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_operation ON performance_metrics(operation);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp DESC);

-- Grant permissions to the application user
-- Note: In production, create a specific application user instead of using postgres
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Function to clean up old data (for maintenance)
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
BEGIN
    -- Delete old conversation turns (keep 90 days)
    DELETE FROM conversation_turns 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    -- Delete old audit logs (keep 1 year)
    DELETE FROM audit_log 
    WHERE timestamp < NOW() - INTERVAL '1 year';
    
    -- Delete old system metrics (keep 7 days)
    DELETE FROM system_metrics 
    WHERE timestamp < NOW() - INTERVAL '7 days';
    
    -- Delete old performance metrics (keep 30 days)
    DELETE FROM performance_metrics 
    WHERE timestamp < NOW() - INTERVAL '30 days';
    
    RAISE NOTICE 'Old data cleanup completed';
END;
$$ LANGUAGE plpgsql;

-- Create scheduled job for cleanup (requires pg_cron extension)
-- Note: This will only work if pg_cron is installed
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        SELECT cron.schedule('cleanup-old-data', '0 2 * * *', 'SELECT cleanup_old_data();');
        RAISE NOTICE 'Scheduled cleanup job created';
    END IF;
END
$$;
