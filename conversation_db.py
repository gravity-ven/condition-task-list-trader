"""
PostgreSQL conversation archiving and learning system
Stores, analyzes, and learns from all user interactions
"""

import os
import psycopg2
from psycopg2.extras import Json, DictCursor
import json
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import hashlib
from datetime import datetime

@dataclass
class ConversationTurn:
    """Single turn in a conversation"""
    user_input: str
    ai_response: str
    timestamp: datetime
    turn_number: int
    context: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

@dataclass
class Conversation:
    """Complete conversation session"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    topic_summary: Optional[str] = None
    tags: List[str] = None
    turns: List[ConversationTurn] = None
    outcomes: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.turns is None:
            self.turns = []
        if self.outcomes is None:
            self.outcomes = {}

class ConversationDatabase:
    """PostgreSQL database for conversation archiving and learning"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or self._get_default_db_url()
        self.connection = None
        self._initialize_database()
    
    def _get_default_db_url(self) -> str:
        """Get default PostgreSQL connection string"""
        # Check for environment variable first
        if 'DATABASE_URL' in os.environ:
            return os.environ['DATABASE_URL']
        
        # Default to local PostgreSQL
        return "postgresql://localhost:5432/conversation_db"
    
    def _initialize_database(self):
        """Connect to database and create tables if needed"""
        try:
            self.connection = psycopg2.connect(self.database_url)
            self.connection.autocommit = True
            
            with self.connection.cursor() as cursor:
                # Enable uuid-ossp for session IDs
                cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
                
                # Create conversations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        end_time TIMESTAMP WITH TIME ZONE,
                        topic_summary TEXT,
                        tags JSONB DEFAULT '[]',
                        outcomes JSONB DEFAULT '{}',
                        embedding VECTOR(1536),  -- For semantic search
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)
                
                # Create conversation turns table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        session_id UUID REFERENCES conversations(session_id),
                        user_input TEXT NOT NULL,
                        ai_response TEXT NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        turn_number INTEGER NOT NULL,
                        context JSONB DEFAULT '{}',
                        metadata JSONB DEFAULT '{}',
                        user_input_embedding VECTOR(1536),
                        ai_response_embedding VECTOR(1536),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)
                
                # Create learning patterns table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS learning_patterns (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        pattern_type VARCHAR(50) NOT NULL,
                        pattern_data JSONB NOT NULL,
                        frequency INTEGER DEFAULT 1,
                        effectiveness_score FLOAT DEFAULT 0.0,
                        last_used TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_start_time ON conversations(start_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_tags ON conversations USING GIN(tags)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_turns_session_id ON conversation_turns(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON conversation_turns(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON learning_patterns(pattern_type)")
                
            print("✅ PostgreSQL database initialized successfully")
            
        except psycopg2.OperationalError as e:
            print(f"❌ Database connection failed: {e}")
            print("📋 Please ensure PostgreSQL is running and:")
            print("   1. Create database: createdb conversation_db")
            print("   2. Or set DATABASE_URL environment variable")
            raise
    
    def start_conversation(self, topic_summary: str = None, tags: List[str] = None) -> str:
        """Start a new conversation session"""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO conversations (topic_summary, tags)
                VALUES (%s, %s)
                RETURNING session_id
            """, (topic_summary, Json(tags or [])))
            
            session_id = cursor.fetchone()[0]
            print(f"🗃️ Started conversation session: {session_id}")
            return str(session_id)
    
    def add_turn(self, session_id: str, user_input: str, ai_response: str, 
                 turn_number: int = 1, context: Dict = None, metadata: Dict = None):
        """Add a conversation turn to the database"""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO conversation_turns 
                (session_id, user_input, ai_response, turn_number, context, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session_id, user_input, ai_response, turn_number, 
                  Json(context or {}), Json(metadata or {})))
    
    def end_conversation(self, session_id: str, outcomes: Dict = None):
        """Mark conversation as ended with outcomes"""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                UPDATE conversations 
                SET end_time = NOW(), outcomes = %s, updated_at = NOW()
                WHERE session_id = %s
            """, (Json(outcomes or {}), session_id))
    
    def get_conversation_history(self, limit: int = 10, 
                               topic_filter: str = None,
                               tag_filter: str = None) -> List[Dict]:
        """Retrieve recent conversation history with filtering"""
        with self.connection.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT c.session_id, c.start_time, c.topic_summary, c.tags, c.outcomes,
                       COUNT(t.id) as turn_count
                FROM conversations c
                LEFT JOIN conversation_turns t ON c.session_id = t.session_id
                WHERE 1=1
            """
            
            params = []
            if topic_filter:
                query += " AND c.topic_summary ILIKE %s"
                params.append(f"%{topic_filter}%")
            
            if tag_filter:
                query += " AND %s = ANY(c.tags)"
                params.append(tag_filter)
            
            query += " GROUP BY c.session_id ORDER BY c.start_time DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def find_similar_conversations(self, query_text: str, limit: int = 5) -> List[Dict]:
        """Find conversations with similar content (using text similarity for now)"""
        with self.connection.cursor(cursor_factory=DictCursor) as cursor:
            # Using text search for similarity (would be better with embeddings)
            cursor.execute("""
                SELECT DISTINCT c.session_id, c.topic_summary, c.start_time,
                       ts_rank_cd(to_tsvector(text), query) as similarity
                FROM conversations c
                JOIN conversation_turns t ON c.session_id = t.session_id,
                     plainto_tsquery(%s) query
                WHERE to_tsvector(t.user_input || ' ' || t.ai_response) @@ query
                ORDER BY similarity DESC
                LIMIT %s
            """, (query_text, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def learn_patterns(self, session_id: str):
        """Analyze conversation to extract learning patterns"""
        with self.connection.cursor(cursor_factory=DictCursor) as cursor:
            # Get conversation turns
            cursor.execute("""
                SELECT user_input, ai_response, context, metadata
                FROM conversation_turns
                WHERE session_id = %s
                ORDER BY turn_number
            """, (session_id,))
            
            turns = cursor.fetchall()
            patterns_found = []
            
            # Pattern 1: Task requests
            for turn in turns:
                if 'task' in turn['user_input'].lower() or 'condition' in turn['user_input'].lower():
                    patterns_found.append({
                        'type': 'task_request',
                        'user_pattern': turn['user_input'][:200],
                        'ai_response_pattern': turn['ai_response'][:200]
                    })
            
            # Pattern 2: Condition Task List usage
            for turn in turns:
                if 'condition task list' in turn['user_input'].lower():
                    patterns_found.append({
                        'type': 'condition_task_list',
                        'example': turn['user_input'],
                        'context': turn.get('context', {})
                    })
            
            # Store learned patterns
            for pattern in patterns_found:
            cursor.execute("""
                INSERT INTO learning_patterns (pattern_type, pattern_data, frequency)
                VALUES (%s, %s, 1)
                ON CONFLICT (pattern_type, pattern_data) 
                DO UPDATE SET frequency = learning_patterns.frequency + 1,
                            updated_at = NOW(),
                            effectiveness_score = GREATEST(learning_patterns.effectiveness_score, 0.5)
            """, (pattern['type'], Json(pattern)))
            
            print(f"🧠 Learned {len(patterns_found)} patterns from conversation")
    
    def get_learning_insights(self) -> Dict:
        """Get insights from learned patterns"""
        with self.connection.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT pattern_type, COUNT(*) as frequency, 
                       AVG(effectiveness_score) as avg_effectiveness
                FROM learning_patterns
                GROUP BY pattern_type
                ORDER BY frequency DESC
            """)
            
            pattern_stats = cursor.fetchall()
            
            cursor.execute("""
                SELECT COUNT(DISTINCT session_id) as total_conversations,
                       COUNT(*) as total_turns,
                       AVG(CAST(turn_count AS INTEGER)) as avg_turns_per_conversation
                FROM conversations
                LEFT JOIN (
                    SELECT session_id, COUNT(*) as turn_count
                    FROM conversation_turns
                    GROUP BY session_id
                ) t ON conversations.session_id = t.session_id
            """)
            
            stats = cursor.fetchone()
            
            return {
                'conversation_stats': dict(stats),
                'pattern_insights': [dict(row) for row in pattern_stats]
            }
    
    def get_context_for_query(self, query: str) -> Dict:
        """Get relevant context from previous conversations for new query"""
        similar = self.find_similar_conversations(query, limit=3)
        
        context = {
            'similar_conversations': similar,
            'recent_patterns': [],
            'suggested_approaches': []
        }
        
        # Get recent relevant patterns
        with self.connection.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT pattern_type, pattern_data, frequency
                FROM learning_patterns
                WHERE pattern_data::text ILIKE %s
                ORDER BY frequency DESC, effectiveness_score DESC
                LIMIT 5
            """, (f"%{query}%",))
            
            context['recent_patterns'] = [dict(row) for row in cursor.fetchall()]
            
        return context
    
    def export_data(self, filepath: str):
        """Export conversation data to JSON file"""
        with self.connection.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT c.*, 
                       JSON_AGG(
                           JSON_BUILD_OBJECT(
                               'turn_number', t.turn_number,
                               'user_input', t.user_input,
                               'ai_response', t.ai_response,
                               'timestamp', t.timestamp,
                               'context', t.context,
                               'metadata', t.metadata
                           ) ORDER BY t.turn_number
                       ) as turns
                FROM conversations c
                LEFT JOIN conversation_turns t ON c.session_id = t.session_id
                GROUP BY c.session_id
                ORDER BY c.start_time DESC
            """)
            
            data = cursor.fetchall()
            
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"📁 Exported {len(data)} conversations to {filepath}")
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
