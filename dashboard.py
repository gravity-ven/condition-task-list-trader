import curses
import threading
import time
from typing import List, Dict, Callable, Optional
from condition_parser import Condition
from conditions_matcher import ConditionsMatcher, MarketData

class TaskDashboard:
    def __init__(self):
        self.matcher = ConditionsMatcher()
        self.screen = None
        self.running = False
        self.current_symbol = ""
        self.setup_matcher_callbacks()
    
    def setup_matcher_callbacks(self):
        """Setup callbacks for condition updates and trade execution"""
        self.matcher.register_update_callback(self.update_display)
        self.matcher.register_trade_callback(self.on_trade_executed)
    
    def start(self):
        """Start the dashboard"""
        self.running = True
        curses.wrapper(self._main_loop)
    
    def stop(self):
        """Stop the dashboard"""
        self.running = False
        self.matcher.stop_matching()
    
    def _main_loop(self, stdscr):
        """Main dashboard loop"""
        self.screen = stdscr
        curses.curs_set(0)  # Hide cursor
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Normal
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Completed
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # In Progress
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)      # Alert
        
        # Clear screen
        stdscr.clear()
        
        # Start matcher
        self.matcher.start_matching()
        
        try:
            self._display_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_matching()
    
    def _display_loop(self):
        """Main display refresh loop"""
        while self.running:
            self._render_screen()
            time.sleep(0.1)
    
    def _render_screen(self):
        """Render the dashboard screen"""
        if not self.screen:
            return
        
        h, w = self.screen.getmaxyx()
        self.screen.border()
        
        # Title
        title = "📊 CONDITION TASK LIST TRADER"
        self.screen.addstr(1, (w - len(title)) // 2, title, curses.A_BOLD)
        
        # Current symbol
        if self.current_symbol:
            symbol_text = f"Symbol: {self.current_symbol}"
            self.screen.addstr(3, 2, symbol_text)
        
        # Conditions section
        self.screen.addstr(5, 2, "TASK CONDITIONS:", curses.A_BOLD)
        
        conditions = self.matcher.get_conditions_status()
        y_offset = 7
        
        for i, condition in enumerate(conditions):
            if y_offset >= h - 5:  # Prevent overflow
                break
            
            # Task status icon
            status_icon = condition['status']
            color = 2 if condition['completed'] else 3
            self.screen.addstr(y_offset, 4, f"[{status_icon}]", curses.color_pair(color))
            
            # Task description
            task_text = f"{condition['task_id']}: {condition['description']}"
            self.screen.addstr(y_offset, 10, task_text)
            
            # Current value if available
            if condition['current_value'] is not None:
                current_val_text = f"Current: {condition['current_value']:.2f}"
                self.screen.addstr(y_offset + 1, 14, current_val_text)
                
                target_text = f"Target: {condition['operator']} {condition['target_value']}"
                self.screen.addstr(y_offset + 2, 14, target_text)
                y_offset += 3
            else:
                y_offset += 2
        
        # Progress bar
        if conditions:
            self._render_progress_bar(conditions, h - 8, w)
        
        # Status line
        completed_count = sum(1 for c in conditions if c['completed'])
        status_text = f"Completed: {completed_count}/{len(conditions)}"
        self.screen.addstr(h - 3, 2, status_text, curses.A_BOLD)
        
        # Instructions
        help_text = "Press 'q' to quit | 'r' to reset | 'i' to input new conditions"
        self.screen.addstr(h - 2, 2, help_text)
        
        self.screen.refresh()
    
    def _render_progress_bar(self, conditions: List[Dict], y: int, w: int):
        """Render a progress bar showing task completion"""
        completed = sum(1 for c in conditions if c['completed'])
        total = len(conditions)
        
        if total == 0:
            return
        
        progress = completed / total
        bar_width = w - 20
        
        # Progress bar
        filled_width = int(bar_width * progress)
        bar = "━" * filled_width + "─" * (bar_width - filled_width)
        
        self.screen.addstr(y, 2, f"[{bar}]")
        progress_text = f"{progress * 100:.0f}%"
        self.screen.addstr(y + 1, (w - len(progress_text)) // 2, progress_text)
    
    def update_display(self, conditions: List[Condition]):
        """Callback for condition updates"""
        # Display will refresh automatically in the render loop
        pass
    
    def on_trade_executed(self, symbol: str, conditions: List[Condition]):
        """Callback when trade is executed"""
        # Flash alert (would need to implement alert display)
        pass
    
    def handle_input(self, conditions_text: str):
        """Handle user input for new conditions"""
        parser = self.matcher.condition_parser or __import__('condition_parser').ConditionParser()
        new_conditions = parser.parse_task_list(conditions_text)
        
        if new_conditions:
            # Clear existing conditions and add new ones
            self.matcher.conditions.clear()
            self.matcher.add_conditions(new_conditions)
            return True
        
        return False
    
    def update_symbol(self, symbol: str, market_data: MarketData):
        """Update market data for tracking"""
        self.current_symbol = symbol
        self.matcher.update_market_data(symbol, market_data)
