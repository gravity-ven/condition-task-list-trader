import random
import time
import math
from conditions_matcher import MarketData
from typing import Dict

class MarketDataSimulator:
    """Simulates real-time market data for testing purposes"""
    
    def __init__(self, symbol: str = "AAPL"):
        self.symbol = symbol
        self.base_price = 150.0
        self.current_price = self.base_price
        self.base_volume = 1000000
        self.rsi_history = []
        self.price_history = []
        self.running = False
    
    def generate_market_data(self) -> MarketData:
        """Generate realistic market data"""
        # Simulate price movement with some randomness
        price_change = random.gauss(0, 0.02)  # 2% standard deviation
        self.current_price *= (1 + price_change)
        
        # Keep price within reasonable bounds
        self.current_price = max(50, min(250, self.current_price))
        
        # Update price history for indicators
        self.price_history.append(self.current_price)
        if len(self.price_history) > 200:  # Keep last 200 values
            self.price_history.pop(0)
        
        # Generate volume
        volume_multiplier = random.uniform(0.5, 2.5)
        current_volume = self.base_volume * volume_multiplier
        
        # Calculate technical indicators
        indicators = self._calculate_indicators()
        
        return MarketData(
            symbol=self.symbol,
            price=self.current_price,
            volume=current_volume,
            indicators=indicators,
            timestamp=time.time()
        )
    
    def _calculate_indicators(self) -> Dict[str, float]:
        """Calculate technical indicators"""
        indicators = {}
        
        if len(self.price_history) >= 14:
            # RSI (simplified calculation)
            rsi = self._calculate_rsi()
            indicators['RSI'] = rsi
            
            # Moving Averages
            if len(self.price_history) >= 20:
                indicators['SMA 20'] = sum(self.price_history[-20:]) / 20
            if len(self.price_history) >= 50:
                indicators['SMA 50'] = sum(self.price_history[-50:]) / 50
            if len(self.price_history) >= 10:
                indicators['EMA 10'] = self._calculate_ema(10)
            
            # MACD (simplified)
            if len(self.price_history) >= 26:
                ema_12 = self._calculate_ema(12)
                ema_26 = self._calculate_ema(26)
                indicators['MACD'] = ema_12 - ema_26
        
        return indicators
    
    def _calculate_rsi(self, periods: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(self.price_history) < periods + 1:
            return 50.0  # Neutral RSI
        
        gains = []
        losses = []
        
        for i in range(1, len(self.price_history)):
            change = self.price_history[i] - self.price_history[i-1]
            if change >= 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-periods:]) / periods
        avg_loss = sum(losses[-periods:]) / periods
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_ema(self, periods: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(self.price_history) < periods:
            return sum(self.price_history) / len(self.price_history)
        
        # Calculate SMA for initial EMA
        initial_sma = sum(self.price_history[:periods]) / periods
        ema = initial_sma
        multiplier = 2 / (periods + 1)
        
        # Calculate EMA
        for price in self.price_history[periods:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def simulate_data_stream(self, callback, interval: float = 0.5):
        """Simulate continuous market data stream"""
        self.running = True
        
        while self.running:
            data = self.generate_market_data()
            callback(self.symbol, data)
            time.sleep(interval)
    
    def stop_simulation(self):
        """Stop the simulation"""
        self.running = False
    
    def create_custom_scenario(self, scenario: str) -> MarketData:
        """Create specific market scenarios for testing"""
        if scenario == "oversold":
            return MarketData(
                symbol=self.symbol,
                price=120.0,
                volume=2000000,
                indicators={'RSI': 25.0, 'SMA 20': 140.0, 'SMA 50': 145.0},
                timestamp=time.time()
            )
        elif scenario == "overbought":
            return MarketData(
                symbol=self.symbol,
                price=180.0,
                volume=5000000,
                indicators={'RSI': 75.0, 'SMA 20': 160.0, 'SMA 50': 155.0},
                timestamp=time.time()
            )
        elif scenario == "volume_spike":
            return MarketData(
                symbol=self.symbol,
                price=150.0,
                volume=5000000,  # 5x normal volume
                indicators={'RSI': 50.0, 'SMA 20': 150.0, 'SMA 50': 150.0},
                timestamp=time.time()
            )
        else:
            return self.generate_market_data()
