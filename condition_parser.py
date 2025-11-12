import re
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class Condition:
    task_id: str
    description: str
    indicator: str
    operator: str
    value: float
    completed: bool = False
    current_value: float = None

class ConditionParser:
    def __init__(self):
        self.indicators = {
            'rsi': 'RSI',
            'moving average': 'SMA',
            'sma': 'SMA',
            'vol': 'Volume',
            'volume': 'Volume',
            'price': 'Price',
            'macd': 'MACD',
            'bollinger': 'Bollinger Bands',
            'ema': 'EMA'
        }
        
        self.operators = {
            '<': '<',
            '>': '>',
            '<=': '<=',
            '>=': '>=',
            'above': '>',
            'below': '<',
            'over': '>',
            'under': '<',
            'spike': '>',
            'drop': '<'
        }
    
    def parse_task_list(self, input_text: str) -> List[Condition]:
        """Parse user's 'Condition Task List' input into structured conditions"""
        conditions = []
        
        # Look for trigger phrases
        if not self._is_condition_task_list(input_text):
            return conditions
        
        # Extract conditions using regex matching
        pattern = r'(?:(?:check if|when|if)\s+)?([^,.?!]+?)(?:\s*(?:$|[,.?!]))'
        matches = re.findall(pattern, input_text, re.IGNORECASE)
        
        for i, match in enumerate(matches):
            condition = self._parse_single_condition(match.strip(), f"task_{i+1}")
            if condition:
                conditions.append(condition)
        
        return conditions
    
    def _is_condition_task_list(self, text: str) -> bool:
        """Check if input is a Condition Task List"""
        triggers = ['condition task list', 'task list', 'conditions', 'check if', 'trade conditions']
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in triggers)
    
    def _parse_single_condition(self, condition_text: str, task_id: str) -> Condition:
        """Parse individual condition text into structured format"""
        # Extract indicator
        indicator = self._extract_indicator(condition_text)
        if not indicator:
            return None
        
        # Extract operator and value
        operator, value = self._extract_operator_and_value(condition_text)
        if not operator or value is None:
            return None
        
        return Condition(
            task_id=task_id,
            description=condition_text,
            indicator=indicator,
            operator=operator,
            value=value
        )
    
    def _extract_indicator(self, text: str) -> str:
        """Extract technical indicator from condition text"""
        text_lower = text.lower()
        for key, value in self.indicators.items():
            if key in text_lower:
                return value
        return None
    
    def _extract_operator_and_value(self, text: str) -> tuple:
        """Extract comparison operator and value from condition text"""
        # Look for patterns like "< 30", "above 50", "2x average", etc.
        
        # Direct comparison operators
        match = re.search(r'([<>=]+)\s*([\d.]+)', text)
        if match:
            return match.group(1), float(match.group(2))
        
        # Text-based operators
        for key, op in self.operators.items():
            if key in text.lower():
                # Extract number after the operator
                pattern = rf'{re.escape(key)}\s*([\d.]+)'
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return op, float(match.group(1))
        
        # Handle special cases like "2x average"
        match = re.search(r'(\d+)x\s*(?:average|avg)', text, re.IGNORECASE)
        if match:
            multiplier = float(match.group(1))
            return '>', multiplier
        
        return None, None
