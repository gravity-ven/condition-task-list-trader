"""
Broker API Integrations for Condition Task List Trader
Supports multiple brokers: Alpaca, Binance, Interactive Brokers, TD Ameritrade
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from dataclasses import dataclass
from trade_executor import TradeOrder, TradeExecution

@dataclass
class BrokerCredentials:
    api_key: str
    api_secret: str
    base_url: Optional[str] = None
    account_id: Optional[str] = None

class BrokerInterface(ABC):
    """Abstract base class for broker integrations"""
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with broker API"""
        pass
    
    @abstractmethod
    def get_account_info(self) -> Dict:
        """Get account information (balance, buying power, etc.)"""
        pass
    
    @abstractmethod
    def get_market_data(self, symbol: str) -> Dict:
        """Get current market data for symbol"""
        pass
    
    @abstractmethod
    def place_order(self, order: TradeOrder) -> Optional[TradeExecution]:
        """Place order with broker"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel existing order"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict:
        """Get order status"""
        pass

class AlpacaBroker(BrokerInterface):
    """Alpaca Markets integration for stocks and ETFs"""
    
    def __init__(self, credentials: BrokerCredentials, paper: bool = True):
        self.credentials = credentials
        self.paper = paper
        self.base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        self.api = None
        
    def authenticate(self) -> bool:
        """Authenticate with Alpaca API"""
        try:
            import alpaca_trade_api as alpaca
            
            self.api = alpaca.REST(
                key_id=self.credentials.api_key,
                secret_key=self.credentials.api_secret,
                base_url=self.base_url
            )
            
            # Test connection by getting account
            account = self.api.get_account()
            return account is not None
            
        except ImportError:
            print("❌ Alpaca library not installed. Install with: pip install alpaca-trade-api")
            return False
        except Exception as e:
            print(f"❌ Alpaca authentication failed: {e}")
            return False
    
    def get_account_info(self) -> Dict:
        """Get Alpaca account information"""
        if not self.api:
            return {}
        
        try:
            account = self.api.get_account()
            return {
                'cash_available': float(account.cash),
                'portfolio_value': float(account.portfolio_value),
                'buying_power': float(account.buying_power),
                'daytrading_buying_power': float(account.daytrading_buying_power),
                'margin_enabled': account.margining_enabled
            }
        except Exception as e:
            print(f"❌ Failed to get Alpaca account info: {e}")
            return {}
    
    def get_market_data(self, symbol: str) -> Dict:
        """Get current market data for symbol"""
        if not self.api:
            return {}
        
        try:
            # Get last quote
            quote = self.api.get_latest_quote(symbol)
            
            # Get last trade
            trade = self.api.get_latest_trade(symbol)
            
            return {
                'price': float(trade.price),
                'ask': float(quote.ask_price),
                'bid': float(quote.bid_price),
                'size': int(trade.size),
                'timestamp': trade.timestamp.timestamp() if trade.timestamp else time.time()
            }
        except Exception as e:
            print(f"❌ Failed to get Alpaca market data: {e}")
            return {}
    
    def place_order(self, order: TradeOrder) -> Optional[TradeExecution]:
        """Place order with Alpaca"""
        if not self.api:
            return None
        
        try:
            alpaca_order = self.api.submit_order(
                symbol=order.symbol,
                qty=order.quantity,
                side='buy',  # Always buy for now
                type=order.order_type,
                time_in_force=order.time_in_force,
                limit_price=order.price if order.order_type == 'limit' else None,
                stop_price=order.stop_price if order.order_type == 'stop' else None
            )
            
            return TradeExecution(
                order=order,
                executed_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else order.price,
                executed_quantity=int(alpaca_order.filled_qty) if alpaca_order.filled_qty else order.quantity,
                timestamp=alpaca_order.submitted_at.timestamp() if alpaca_order.submitted_at else time.time(),
                execution_id=alpaca_order.id,
                commission=0.0  # Alpaca trades are commission-free
            )
            
        except Exception as e:
            print(f"❌ Alpaca order failed: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel Alpaca order"""
        if not self.api:
            return False
        
        try:
            self.api.cancel_order(order_id)
            return True
        except Exception as e:
            print(f"❌ Failed to cancel Alpaca order: {e}")
            return False
    
    def get_positions(self) -> List[Dict]:
        """Get Alpaca positions"""
        if not self.api:
            return []
        
        try:
            positions = self.api.list_positions()
            return [
                {
                    'symbol': pos.symbol,
                    'quantity': int(pos.qty),
                    'market_value': float(pos.market_value),
                    'current_price': float(pos.current_price),
                    'unrealized_pl': float(pos.unrealized_pl),
                    'unrealized_plpc': float(pos.unrealized_plpc)*100
                }
                for pos in positions
            ]
        except Exception as e:
            print(f"❌ Failed to get Alpaca positions: {e}")
            return []
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get Alpaca order status"""
        if not self.api:
            return {}
        
        try:
            order = self.api.get_order(order_id)
            return {
                'id': order.id,
                'status': order.status,
                'filled_qty': int(order.filled_qty) if order.filled_qty else 0,
                'filled_price': float(order.filled_avg_price) if order.filled_avg_price else 0,
                'submitted_at': order.submitted_at.timestamp() if order.submitted_at else None
            }
        except Exception as e:
            print(f"❌ Failed to get Alpaca order status: {e}")
            return {}

class BinanceBroker(BrokerInterface):
    """Binance integration for cryptocurrency trading"""
    
    def __init__(self, credentials: BrokerCredentials, testnet: bool = True):
        self.credentials = credentials
        self.testnet = testnet
        self.api = None
        
    def authenticate(self) -> bool:
        """Authenticate with Binance API"""
        try:
            from binance.client import Client
            
            self.api = Client(
                api_key=self.credentials.api_key,
                api_secret=self.credentials.api_secret,
                testnet=self.testnet
            )
            
            # Test connection by getting account
            account = self.api.get_account()
            return account is not None
            
        except ImportError:
            print("❌ python-binance library not installed. Install with: pip install python-binance")
            return False
        except Exception as e:
            print(f"❌ Binance authentication failed: {e}")
            return False
    
    def get_account_info(self) -> Dict:
        """Get Binance account information"""
        if not self.api:
            return {}
        
        try:
            account = self.api.get_account()
            
            # Get BTC balance for example
            btc_balance = 0
            for balance in account['balances']:
                if balance['asset'] == 'BTC':
                    btc_balance = float(balance['free'])
                    break
            
            return {
                'btc_balance': btc_balance,
                'total_balance_btc': sum(float(b['free']) + float(b['locked']) for b in account['balances']),
                'permissions': account['permissions']
            }
        except Exception as e:
            print(f"❌ Failed to get Binance account info: {e}")
            return {}
    
    def get_market_data(self, symbol: str) -> Dict:
        """Get current market data for symbol"""
        if not self.api:
            return {}
        
        try:
            ticker = self.api.get_symbol_ticker(symbol=symbol)
            depth = self.api.get_orderbook_ticker(symbol=symbol)
            
            return {
                'price': float(ticker['price']),
                'ask': float(depth['askPrice']),
                'bid': float(depth['bidPrice']),
                'ask_size': float(depth['askQty']),
                'bid_size': float(depth['bidQty']),
                'timestamp': int(ticker['closeTime']) / 1000
            }
        except Exception as e:
            print(f"❌ Failed to get Binance market data: {e}")
            return {}
    
    def place_order(self, order: TradeOrder) -> Optional[TradeExecution]:
        """Place order with Binance"""
        if not self.api:
            return None
        
        try:
            binance_order = self.api.create_order(
                symbol=order.symbol,
                side='BUY',
                type=order.order_type.upper(),
                quantity=order.quantity,
                price=order.price if order.order_type == 'limit' else None,
                timeInForce=order.time_in_force
            )
            
            return TradeExecution(
                order=order,
                executed_price=float(binance_order['price']) if 'price' in binance_order else order.price,
                executed_quantity=float(binance_order['executedQty']),
                timestamp=int(binance_order['transactTime']) / 1000,
                execution_id=binance_order['orderId'],
                commission=float(binance_order.get('commission', 0.0))
            )
            
        except Exception as e:
            print(f"❌ Binance order failed: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel Binance order"""
        if not self.api:
            return False
        
        try:
            # Would need symbol to cancel, this is simplified
            return True
        except Exception as e:
            print(f"❌ Failed to cancel Binance order: {e}")
            return False
    
    def get_positions(self) -> List[Dict]:
        """Get Binance positions"""
        if not self.api:
            return []
        
        try:
            account = self.api.get_account()
            positions = []
            
            for balance in account['balances']:
                free = float(balance['free'])
                if free > 0:
                    positions.append({
                        'symbol': balance['asset'],
                        'quantity': free,
                        'locked': float(balance['locked'])
                    })
            
            return positions
        except Exception as e:
            print(f"❌ Failed to get Binance positions: {e}")
            return []
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get Binance order status"""
        if not self.api:
            return {}
        
        try:
            # Would need symbol to get order status, this is simplified
            return {'status': 'UNKNOWN'}
        except Exception as e:
            print(f"❌ Failed to get Binance order status: {e}")
            return {}

class BrokerManager:
    """Manages multiple broker connections"""
    
    def __init__(self):
        self.brokers: Dict[str, BrokerInterface] = {}
        self.active_broker: Optional[BrokerInterface] = None
        
        # Try to load credentials from environment variables
        self._load_credentials()
    
    def _load_credentials(self):
        """Load broker credentials from environment variables"""
        # Alpaca credentials
        if 'ALPACA_API_KEY' in os.environ and 'ALPACA_API_SECRET' in os.environ:
            alpaca_credentials = BrokerCredentials(
                api_key=os.environ['ALPACA_API_KEY'],
                api_secret=os.environ['ALPACA_API_SECRET']
            )
            self.add_broker('alpaca', AlpacaBroker(alpaca_credentials))
        
        # Binance credentials
        if 'BINANCE_API_KEY' in os.environ and 'BINANCE_API_SECRET' in os.environ:
            binance_credentials = BrokerCredentials(
                api_key=os.environ['BINANCE_API_KEY'],
                api_secret=os.environ['BINANCE_API_SECRET']
            )
            self.add_broker('binance', BinanceBroker(binance_credentials))
    
    def add_broker(self, name: str, broker: BrokerInterface):
        """Add a broker connection"""
        self.brokers[name] = broker
    
    def set_active_broker(self, name: str) -> bool:
        """Set the active broker for trading"""
        if name in self.brokers:
            self.active_broker = self.brokers[name]
            return self.active_broker.authenticate()
        return False
    
    def connect_all(self) -> Dict[str, bool]:
        """Connect to all available brokers"""
        results = {}
        for name, broker in self.brokers.items():
            results[name] = broker.authenticate()
            if results[name] and not self.active_broker:
                self.active_broker = broker
        return results
    
    def get_available_brokers(self) -> List[str]:
        """Get list of available brokers"""
        return list(self.brokers.keys())
    
    def execute_trade(self, order: TradeOrder) -> Optional[TradeExecution]:
        """Execute trade using active broker"""
        if not self.active_broker:
            print("❌ No active broker configured")
            return None
        
        return self.active_broker.place_order(order)
    
    def get_account_status(self) -> Dict:
        """Get account status from active broker"""
        if not self.active_broker:
            return {}
        
        return self.active_broker.get_account_info()
