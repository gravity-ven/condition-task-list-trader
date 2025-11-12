import time
from typing import List, Dict
from dataclasses import dataclass, field
import threading
import queue
from condition_parser import Condition

@dataclass
class MarketData:
    symbol: str
    price: float
    volume: float
    indicators: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class ConditionsMatcher:
    def __init__(self):
        self.conditions: List[Condition] = []
        self.market_data: Dict[str, MarketData] = {}
        self.task_queue = queue.Queue()
        self.update_callbacks = []
        self.trade_executed_callbacks = []
        self.running = False
        self.matcher_thread = None
    
    def add_conditions(self, conditions: List[Condition]):
        """Add new conditions to track"""
        self.conditions.extend(conditions)
        self._notify_update()
    
    def update_market_data(self, symbol: str, data: MarketData):
        """Update market data for a symbol"""
        self.market_data[symbol] = data
        self.task_queue.put(('update', symbol, data))
    
    def start_matching(self):
        """Start the background matching process"""
        if not self.running:
            self.running = True
            self.matcher_thread = threading.Thread(target=self._matching_loop, daemon=True)
            self.matcher_thread.start()
    
    def stop_matching(self):
        """Stop the matching process"""
        self.running = False
        if self.matcher_thread:
            self.matcher_thread.join()
    
    def register_update_callback(self, callback):
        """Register callback for condition updates"""
        self.update_callbacks.append(callback)
    
    def register_trade_callback(self, callback):
        """Register callback for when all conditions are met"""
        self.trade_executed_callbacks.append(callback)
    
    def _matching_loop(self):
        """Main loop for evaluating conditions"""
        while self.running:
            try:
                # Process any pending updates
                while not self.task_queue.empty():
                    action, symbol, data = self.task_queue.get_nowait()
                    if action == 'update':
                        self._evaluate_conditions_for_symbol(symbol, data)
                
                time.sleep(0.1)  # Check 10 times per second
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in matching loop: {e}")
    
    def _evaluate_conditions_for_symbol(self, symbol: str, data: MarketData):
        """Evaluate all conditions for a given symbol"""
        conditions_updated = False
        all_completed = True
        
        for condition in self.conditions:
            if self._condition_applies_to_symbol(condition, symbol):
                was_completed = condition.completed
                condition.completed = self._evaluate_condition(condition, data)
                
                if condition.completed != was_completed:
                    conditions_updated = True
                
                if not condition.completed:
                    all_completed = False
        
        # Notify handlers
        if conditions_updated:
            self._notify_update()
        
        if all_completed and self.conditions:
            self._execute_trade(symbol)
    
    def _condition_applies_to_symbol(self, condition: Condition, symbol: str) -> bool:
        """Check if condition applies to given symbol (for now, all apply)"""
        return True  # Could be extended to symbol-specific conditions
    
    def _evaluate_condition(self, condition: Condition, data: MarketData) -> bool:
        """Evaluate if a single condition is met"""
        current_value = None
        
        # Get the current value based on indicator type
        if condition.indicator == 'Price':
            current_value = data.price
        elif condition.indicator == 'Volume':
            current_value = data.volume
        elif condition.indicator in data.indicators:
            current_value = data.indicators[condition.indicator]
        else:
            return False  # Indicator not available
        
        condition.current_value = current_value
        
        # Evaluate the condition
        try:
            if condition.operator == '<':
                return current_value < condition.value
            elif condition.operator == '>':
                return current_value > condition.value
            elif condition.operator == '<=':
                return current_value <= condition.value
            elif condition.operator == '>=':
                return current_value >= condition.value
            else:
                return False
        except Exception as e:
            print(f"Error evaluating condition: {e}")
            return False
    
    def _notify_update(self):
        """Notify all registered callbacks of updates"""
        for callback in self.update_callbacks:
            try:
                callback(self.conditions)
            except Exception as e:
                print(f"Error in update callback: {e}")
    
    def _execute_trade(self, symbol: str):
        """Execute trade when all conditions are met"""
        print(f"🚀 ALL CONDITIONS MET! Executing trade on {symbol}")
        
        for callback in self.trade_executed_callbacks:
            try:
                callback(symbol, self.conditions)
            except Exception as e:
                print(f"Error in trade callback: {e}")
    
    def get_conditions_status(self) -> List[Dict]:
        """Get current status of all conditions"""
        return [
            {
                'task_id': c.task_id,
                'description': c.description,
                'indicator': c.indicator,
                'operator': c.operator,
                'target_value': c.value,
                'current_value': c.current_value,
                'completed': c.completed,
                'status': '✅' if c.completed else '⏳'
            }
            for c in self.conditions
        ]
    
    def reset_conditions(self):
        """Reset all conditions to incomplete"""
        for condition in self.conditions:
            condition.completed = False
            condition.current_value = None
        self._notify_update()
