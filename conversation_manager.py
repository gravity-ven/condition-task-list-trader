"""
Conversation manager for the trading system
Integrates PostgreSQL archiving with real-time learning and context enhancement
"""

import os
import time
import json
from typing import Dict, List, Optional
from datetime import datetime
from conversation_db import ConversationDatabase, Conversation, ConversationTurn
import threading
import queue

class ConversationManager:
    """Manages conversation archiving and learning for the trading system"""
    
    def __init__(self):
        self.db = None
        self.current_session_id = None
        self.turn_count = 0
        self.learning_enabled = True
        
        # Background processing for learning
        self.learning_queue = queue.Queue()
        self.learning_thread = None
        
        self._initialize_database()
        self._start_background_learning()
    
    def _initialize_database(self):
        """Initialize database connection"""
        try:
            self.db = ConversationDatabase()
            print("🗄️ Conversation database connected")
        except Exception as e:
            print(f"⚠️ Conversation database unavailable: {e}")
            print("💭 Conversations will not be archived")
    
    def _start_background_learning(self):
        """Start background thread for processing learning tasks"""
        if self.db:
            self.learning_thread = threading.Thread(
                target=self._background_learning_loop,
                daemon=True
            )
            self.learning_thread.start()
    
    def start_conversation(self, topic: str = "Trading System Interaction") -> str:
        """Start a new conversation session"""
        if self.db:
            self.current_session_id = self.db.start_conversation(
                topic_summary=topic,
                tags=['trading', 'condition_tasks', 'automation']
            )
        else:
            self.current_session_id = f"local_{int(time.time())}"
        
        self.turn_count = 0
        print(f"💬 Conversation session started: {self.current_session_id[:8]}...")
        return self.current_session_id
    
    def add_conversation_turn(self, user_input: str, ai_response: str, 
                            context: Dict = None, metadata: Dict = None):
        """Add a conversation turn to the current session"""
        self.turn_count += 1
        
        if self.db and self.current_session_id:
            # Determine context for this turn
            turn_context = self._extract_context(user_input, context)
            
            self.db.add_turn(
                session_id=self.current_session_id,
                user_input=user_input,
                ai_response=ai_response,
                turn_number=self.turn_count,
                context=turn_context,
                metadata=metadata or {}
            )
            
            # Queue for background learning
            if self.learning_enabled:
                self.learning_queue.put(('turn', self.current_session_id, user_input, ai_response))
    
    def _extract_context(self, user_input: str, additional_context: Dict = None) -> Dict:
        """Extract relevant context from user input and additional context"""
        context = {
            'timestamp': datetime.now().isoformat(),
            'turn_number': self.turn_count,
            'is_condition_task': False,
            'is_trade_related': False,
            'extracted_entities': {}
        }
        
        # Check for condition task list
        if 'condition task list' in user_input.lower():
            context['is_condition_task'] = True
            context['task_type'] = 'condition_task_list'
        
        # Check for trading-related terms
        trading_keywords = ['trade', 'market', 'stock', 'price', 'rsi', 'volume', 'broker']
        if any(keyword in user_input.lower() for keyword in trading_keywords):
            context['is_trade_related'] = True
        
        # Extract technical indicators mentioned
        indicators = ['rsi', 'sma', 'ema', 'macd', 'bollinger', 'volume']
        mentioned_indicators = [ind for ind in indicators if ind in user_input.lower()]
        if mentioned_indicators:
            context['extracted_entities']['indicators'] = mentioned_indicators
        
        # Extract values (numbers)
        import re
        numbers = re.findall(r'\d+\.?\d*', user_input)
        if numbers:
            context['extracted_entities']['values'] = [float(n) for n in numbers]
        
        # Merge additional context
        if additional_context:
            context.update(additional_context)
        
        return context
    
    def get_relevant_context(self, query: str) -> Dict:
        """Get relevant context from previous conversations"""
        if not self.db:
            return {}
        
        context = {
            'similar_conversations': [],
            'recent_patterns': [],
            'suggested_responses': []
        }
        
        try:
            # Find similar past conversations
            similar = self.db.find_similar_conversations(query, limit=3)
            context['similar_conversations'] = similar
            
            # Get relevant patterns
            context = self.db.get_context_for_query(query)
            
            # Generate suggested responses based on patterns
            for pattern in context.get('recent_patterns', []):
                if pattern['pattern_type'] == 'condition_task_list':
                    context['suggested_responses'].append(
                        "I can parse your Condition Task List and set up automated trading when all conditions are met"
                    )
            
        except Exception as e:
            print(f"⚠️ Error retrieving context: {e}")
        
        return context
    
    def end_conversation(self, outcomes: Dict = None):
        """End current conversation session"""
        if self.db and self.current_session_id:
            self.db.end_conversation(
                session_id=self.current_session_id,
                outcomes=outcomes or {'turn_count': self.turn_count}
            )
            
            # Queue for final learning analysis
            if self.learning_enabled:
                self.learning_queue.put(('analyze', self.current_session_id))
        
        print(f"🔚 Conversation session ended ({} turns)".format(self.turn_count))
        self.current_session_id = None
        self.turn_count = 0
    
    def _background_learning_loop(self):
        """Background thread for processing learning queue"""
        while True:
            try:
                task_type, *args = self.learning_queue.get(timeout=1)
                
                if task_type == 'turn':
                    session_id, user_input, ai_response = args
                    self._process_turn_learning(session_id, user_input, ai_response)
                
                elif task_type == 'analyze':
                    session_id = args[0]
                    self.db.learn_patterns(session_id)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ Background learning error: {e}")
    
    def _process_turn_learning(self, session_id: str, user_input: str, ai_response: str):
        """Process learning from a single conversation turn"""
        # Extract immediate insights
        insights = {
            'user_intent': self._classify_intent(user_input),
            'response_type': self._classify_response(ai_response),
            'interaction_success': self._assess_interaction_quality(user_input, ai_response)
        }
        
        # Log insights (would store in database for more sophisticated learning)
        if insights['user_intent'] == 'condition_task' and insights['interaction_success'] > 0.8:
            print(f"✍️ Learned effective condition task handling pattern")
    
    def _classify_intent(self, user_input: str) -> str:
        """Classify user intent from input"""
        user_lower = user_input.lower()
        
        if 'condition task list' in user_lower:
            return 'condition_task'
        elif 'demo' in user_lower:
            return 'demo_request'
        elif 'broker' in user_lower:
            return 'broker_configuration'
        elif any(word in user_lower for word in ['how', 'what', 'why']):
            return 'question'
        elif any(word in user_lower for word in ['help', 'install', 'setup']):
            return 'setup_help'
        else:
            return 'general_inquiry'
    
    def _classify_response(self, ai_response: str) -> str:
        """Classify AI response type"""
        if '✅' in ai_response or 'completed' in ai_response.lower():
            return 'confirmation'
        elif '❌' in ai_response or 'error' in ai_response.lower():
            return 'error_handling'
        elif '🎯' in ai_response or 'trade' in ai_response.lower():
            return 'trade_execution'
        elif '📋' in ai_response or 'task' in ai_response.lower():
            return 'task_management'
        else:
            return 'information'
    
    def _assess_interaction_quality(self, user_input: str, ai_response: str) -> float:
        """Assess quality of interaction (0.0 to 1.0)"""
        score = 0.5  # base score
        
        # Check if response addresses user intent
        if 'condition task list' in user_input.lower() and 'condition' in ai_response.lower():
            score += 0.3
        
        # Check for actionable outcomes
        if any(emoji in ai_response for emoji in ['✅', '🎯', '📋']):
            score += 0.2
        
        return min(score, 1.0)
    
    def get_conversation_insights(self) -> Dict:
        """Get insights from all archived conversations"""
        if not self.db:
            return {}
        
        return self.db.get_learning_insights()
    
    def export_conversations(self, filepath: str = None):
        """Export conversation data for analysis"""
        if not self.db:
            print("❌ No database connection - cannot export")
            return
        
        if not filepath:
            filepath = f"conversation_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        self.db.export_data(filepath)
    
    def shutdown(self):
        """Clean shutdown of conversation manager"""
        # End current conversation if active
        if self.current_session_id:
            self.end_conversation({'reason': 'system_shutdown'})
        
        # Close database connection
        if self.db:
            self.db.close()
        
        print("👋 Conversation manager shut down")

# Global instance for the application
conversation_manager = ConversationManager()
