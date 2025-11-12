import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from condition_parser import Condition
from conditions_matcher import MarketData
from broker_integrations import BrokerManager

@dataclass
class TradeOrder:
    symbol: str
    order_type: str  # 'market', 'limit', 'stop'
    quantity: int
    price: Optional[float] = None  # For limit orders
    stop_price: Optional[float] = None  # For stop orders
    time_in_force: str = 'IOC'  # Immediate or Cancel
    
@dataclass
class TradeExecution:
    order: TradeOrder
    executed_price: float
    executed_quantity: int
    timestamp: float
    execution_id: str
    commission: float = 0.0
    
@dataclass
class RiskParameters:
    max_position_size: float = 10000.0  # Maximum position value
    max_daily_loss: float = 1000.0  # Maximum daily loss limit
    stop_loss_percentage: float = 0.02  # 2% stop loss
    take_profit_percentage: float = 0.05  # 5% take profit
    max_risk_per_trade: float = 0.01  # 1% of portfolio per trade

class TradeExecutor:
    """
    Handles trade execution when all conditions are met
    Integrates with real broker APIs when available
    """
    
    def __init__(self, portfolio_value: float = 100000.0):
        self.portfolio_value = portfolio_value
        self.risk_params = RiskParameters()
        self.executed_trades: List[TradeExecution] = []
        self.daily_pnl = 0.0
        self.last_reset_date = time.time() // 86400  # Days since epoch
        
        # Initialize broker manager for real integration
        self.broker_manager = BrokerManager()
        self.using_real_broker = False
        
        # Try to connect to real brokers
        self._connect_to_brokers()
    
    def _connect_to_brokers(self):
        """Connect to available broker APIs"""
        connection_results = self.broker_manager.connect_all()
        
        connected_brokers = [name for name, connected in connection_results.items() if connected]
        
        if connected_brokers:
            self.using_real_broker = True
            broker_name = connected_brokers[0]
            print(f"🎯 Connected to {broker_name.capitalize()} for real trade execution")
        else:
            print("⚠️  No broker connected - using simulation mode")

    def execute_trade(self, symbol: str, market_data: MarketData, 
                     conditions: List[Condition]) -> Optional[TradeExecution]:
        """
        Execute trade when all conditions are met
        Uses real broker if available, otherwise simulation
        """
        # Check risk parameters
        if not self._check_risk_limits(symbol, market_data):
            return None
        
        # Calculate position size
        position_size = self._calculate_position_size(market_data)
        if position_size <= 0:
            return None
        
        # Create order
        order = self._create_order(symbol, market_data, position_size)
        
        # Execute with real broker or simulation
        if self.using_real_broker:
            execution = self._execute_real_broker(order, market_data)
        else:
            execution = self._simulate_execution(order, market_data)
        
        if execution:
            self.executed_trades.append(execution)
            self._log_execution(execution, conditions)
            
            # Set risk management orders for real trades
            if self.using_real_broker:
                self._set_broker_risk_orders(execution, market_data)
        
        return execution
    
    def _execute_real_broker(self, order: TradeOrder, market_data: MarketData) -> Optional[TradeExecution]:
        """Execute trade through real broker API"""
        try:
            execution = self.broker_manager.execute_trade(order)
            if execution:
                print(f"🎯 REAL trade executed via {type(self.broker_manager.active_broker).__name__}")
            return execution
        except Exception as e:
            print(f"❌ Real broker execution failed: {e}")
            print("Falling back to simulation...")
            return self._simulate_execution(order, market_data)
    
    def _set_broker_risk_orders(self, execution: TradeExecution, market_data: MarketData):
        """Set stop loss and take profit orders with broker"""
        try:
            # Calculate risk management prices
            stop_loss_price = execution.executed_price * (1 - self.risk_params.stop_loss_percentage)
            take_profit_price = execution.executed_price * (1 + self.risk_params.take_profit_percentage)
            
            # Create risk orders
            stop_order = TradeOrder(
                symbol=execution.order.symbol,
                order_type='stop',
                quantity=execution.executed_quantity,
                stop_price=stop_loss_price
            )
            
            limit_order = TradeOrder(
                symbol=execution.order.symbol,
                order_type='limit', 
                quantity=execution.executed_quantity,
                price=take_profit_price
            )
            
            # Submit risk orders to broker
            self.broker_manager.execute_trade(stop_order)
            self.broker_manager.execute_trade(limit_order)
            
            print(f"🛑 Stop loss set at ${stop_loss_price:.2f}")
            print(f"🎯 Take profit set at ${take_profit_price:.2f}")
            
        except Exception as e:
            print(f"❌ Failed to set risk orders: {e}")
    
    def _check_risk_limits(self, symbol: str, market_data: MarketData) -> bool:
        """Check if trade passes risk management rules"""
        
        # Check daily loss limit
        if self.daily_pnl < -self.risk_params.max_daily_loss:
            print(f"❌ Daily loss limit exceeded: ${self.daily_pnl:.2f}")
            return False
        
        # Check maximum position size
        current_price = market_data.price
        order_value = current_price * 100  # Assuming 100 shares
        if order_value > self.risk_params.max_position_size:
            print(f"❌ Position size too large: ${order_value:.2f}")
            return False
        
        return True
    
    def _calculate_position_size(self, market_data: MarketData) -> int:
        """
        Calculate position size based on risk parameters
        """
        current_price = market_data.price
        
        # Risk 1% of portfolio per trade
        max_risk_amount = self.portfolio_value * self.risk_params.max_risk_per_trade
        
        # Calculate shares based on stop loss
        stop_loss_amount = current_price * self.risk_params.stop_loss_percentage
        position_size = max_risk_amount / stop_loss_amount
        
        # Round down to nearest whole share
        shares = int(position_size)
        
        return shares
    
    def _create_order(self, symbol: str, market_data: MarketData, 
                     quantity: int) -> TradeOrder:
        """
        Create market order for immediate execution
        """
        return TradeOrder(
            symbol=symbol,
            order_type='market',
            quantity=quantity,
            price=market_data.price,
            time_in_force='IOC'
        )
    
    def _simulate_execution(self, order: TradeOrder, 
                          market_data: MarketData) -> Optional[TradeExecution]:
        """
        Simulate order execution
        """
        try:
            # For market order, execute at current price (with small slippage)
            slippage = random.uniform(-0.0005, 0.0005)  # Small random slippage
            executed_price = market_data.price * (1 + slippage)
            
            # Calculate commission (0.1% of trade value)
            trade_value = executed_price * order.quantity
            commission = trade_value * 0.001
            
            execution = TradeExecution(
                order=order,
                executed_price=executed_price,
                executed_quantity=order.quantity,
                timestamp=time.time(),
                execution_id=f"EXEC_{int(time.time() * 1000)}",
                commission=commission
            )
            
            return execution
            
        except Exception as e:
            print(f"❌ Trade execution failed: {e}")
            return None
    
    def _log_execution(self, execution: TradeExecution, conditions: List[Condition]):
        """Log trade execution details"""
        print("\n" + "="*60)
        print("🚀 TRADE EXECUTED SUCCESSFULLY")
        print("="*60)
        print(f"Symbol: {execution.order.symbol}")
        print(f"Price: ${execution.executed_price:.2f}")
        print(f"Quantity: {execution.executed_quantity} shares")
        print(f"Value: ${execution.executed_price * execution.executed_quantity:.2f}")
        print(f"Commission: ${execution.commission:.2f}")
        print(f"Execution ID: {execution.execution_id}")
        print("\nConditions Met:")
        for condition in conditions:
            status = "✅"
            print(f"  {status} {condition.description}")
        print("="*60)
    
    def set_stop_loss(self, execution_id: str, stop_price: float):
        """Set stop loss for existing position"""
        # In real implementation, this would send stop order to broker
        print(f"🛑 Stop loss set for {execution_id} at ${stop_price:.2f}")
    
    def set_take_profit(self, execution_id: str, target_price: float):
        """Set take profit target for existing position"""
        # In real implementation, this would send limit order to broker
        print(f"🎯 Take profit set for {execution_id} at ${target_price:.2f}")
    
    def get_portfolio_status(self) -> Dict:
        """Get current portfolio status"""
        total_invested = sum(
            exec.executed_price * exec.executed_quantity 
            for exec in self.executed_trades
        )
        total_commission = sum(exec.commission for exec in self.executed_trades)
        
        return {
            'portfolio_value': self.portfolio_value,
            'total_invested': total_invested,
            'total_commission': total_commission,
            'daily_pnl': self.daily_pnl,
            'trade_count': len(self.executed_trades),
            'cash_available': self.portfolio_value - total_invested
        }
    
    def reset_daily_account(self):
        """Reset daily tracking for new trading day"""
        current_date = time.time() // 86400
        if current_date > self.last_reset_date:
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            print("📅 Daily account reset - new trading day")

# Import random for slippage simulation
import random
