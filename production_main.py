"""
Production entry point for Condition Task List Trader
Includes proper startup, shutdown, and monitoring
"""

import os
import sys
import signal
import threading
import time
import logging
from pathlib import Path

# Add application directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import production components
from production_config import config_manager
from production_logger import get_production_logger, production_logger
from health_checks import health_monitor, RecoveryManager, HealthCheckServer
from conversation_manager import conversation_manager

# Import application components
from condition_parser import ConditionParser
from conditions_matcher import ConditionsMatcher
from trade_executor import TradeExecutor
from market_data_simulator import MarketDataSimulator
from broker_integrations import BrokerManager

class ProductionApplication:
    """Production-ready application wrapper"""
    
    def __init__(self):
        self.config = config_manager.get_config()
        self.logger = production_logger
        self.running = False
        self.shutdown_event = threading.Event()
        
        # Application components
        self.parser = None
        self.matcher = None
        self.executor = None
        self.simulator = None
        self.simulation_thread = None
        
        # Monitoring components
        self.health_server = None
        self.recovery_manager = None
        
        # Setup graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.shutdown()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGUSR1, lambda s, f: self._log_system_status())
    
    def initialize(self):
        """Initialize all application components"""
        self.logger.info("Initializing production application...")
        
        try:
            # Validate configuration
            validation = self.config.validate()
            if not validation['valid']:
                self.logger.error(f"Configuration validation failed: {validation['issues']}")
                raise RuntimeError("Invalid configuration")
            
            # Initialize application components
            self.parser = ConditionParser()
            self.matcher = ConditionsMatcher()
            self.executor = TradeExecutor()
            self.simulator = MarketDataSimulator("AAPL")
            
            # Start conversation manager
            conversation_manager.start_conversation("Production Trading Session")
            
            # Setup monitoring
            self._setup_monitoring()
            
            # Connect to brokers
            self._connect_brokers()
            
            # Start main components
            self._start_components()
            
            self.logger.info("✅ Production application initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize application: {e}")
            raise
    
    def _setup_monitoring(self):
        """Setup health checks and monitoring"""
        from health_checks import DatabaseHealthCheck, BrokerHealthCheck, MemoryHealthCheck, DiskSpaceHealthCheck, ConditionsEngineHealthCheck
        
        # Add health checks
        health_monitor.add_check(DatabaseHealthCheck(self.executor.broker_manager.db))
        health_monitor.add_check(BrokerHealthCheck(self.executor.broker_manager))
        health_monitor.add_check(MemoryHealthCheck())
        health_monitor.add_check(DiskSpaceHealthCheck())
        health_monitor.add_check(ConditionsEngineHealthCheck(self.matcher))
        
        # Setup recovery manager
        self.recovery_manager = RecoveryManager(health_monitor)
        self._setup_recovery_actions()
        
        # Start health monitoring
        health_monitor.start_monitoring(interval_seconds=30.0)
        
        # Start health check server
        if self.config.monitoring.enable_health_check:
            self.health_server = HealthCheckServer(health_monitor, self.config.monitoring.health_check_port)
            health_thread = threading.Thread(target=self.health_server.start_server, daemon=True)
            health_thread.start()
            self.logger.info(f"Health check server started on port {self.config.monitoring.health_check_port}")
    
    def _setup_recovery_actions(self):
        """Setup automatic recovery actions"""
        def restart_conditions_engine() -> bool:
            try:
                if not self.matcher.running:
                    self.matcher.start_matching()
                    self.logger.info("Conditions engine restarted successfully")
                    return True
                return True
            except Exception as e:
                self.logger.error(f"Failed to restart conditions engine: {e}")
                return False
        
        def reconnect_brokers() -> bool:
            try:
                connection_results = self.executor.broker_manager.connect_all()
                connected = any(connection_results.values())
                if connected:
                    self.logger.info("Broker connections re-established")
                    return True
                return False
            except Exception as e:
                self.logger.error(f"Failed to reconnect brokers: {e}")
                return False
        
        self.recovery_manager.register_recovery_action("conditions_engine", restart_conditions_engine)
        self.recovery_manager.register_recovery_action("broker_api", reconnect_brokers)
    
    def _connect_brokers(self):
        """Connect to broker APIs"""
        if self.executor.using_real_broker:
            broker_name = type(self.executor.broker_manager.active_broker).__name__.replace('Broker', '')
            self.logger.info(f"🎯 Connected to {broker_name} for real trade execution")
        else:
            self.logger.info("⚠️ No broker connected - using simulation mode")
    
    def _start_components(self):
        """Start main application components"""
        # Setup trade execution callback
        def on_trade_executed(symbol: str, conditions):
            self.logger.info(f"🎯 ALL CONDITIONS MET! EXECUTING TRADE: {symbol}")
            
            market_data = self.matcher.market_data.get(symbol)
            if market_data:
                execution = self.executor.execute_trade(symbol, market_data, conditions)
                if execution:
                    trade_type = "REAL" if self.executor.using_real_broker else "SIMULATED"
                    self.logger.info(f"🚀 {trade_type} trade executed successfully!")
            
            # Archive trade execution
            conversation_manager.add_conversation_turn(
                "TRADE_EXECUTED", 
                f"Trade executed on {symbol} with {len(conditions)} conditions met",
                {'trade_execution': True, 'symbol': symbol, 'conditions_count': len(conditions)}
            )
        
        def on_conditions_updated(conditions):
            completed = sum(1 for c in conditions if c.completed)
            total = len(conditions)
            self.logger.debug(f"Condition status: {completed}/{total} conditions met")
        
        self.matcher.register_trade_callback(on_trade_executed)
        self.matcher.register_update_callback(on_conditions_updated)
        
        # Start conditions matching engine
        self.matcher.start_matching()
        
        # Start market data simulation
        def update_market_data(symbol: str, data):
            self.matcher.update_market_data(symbol, data)
        
        self.simulation_thread = threading.Thread(
            target=self.simulator.simulate_data_stream,
            args=(update_market_data, 0.1),
            daemon=True
        )
        self.simulation_thread.start()
        
        self.logger.info("📊 Market data simulation started")
    
    def start(self):
        """Start the application"""
        try:
            self.initialize()
            self.running = True
            
            self.logger.info("🚀 Condition Task List Trader started successfully")
            self.logger.info("📡 Health endpoints available:")
            self.logger.info(f"   Health: http://localhost:{self.config.monitoring.health_check_port}/health")
            self.logger.info(f"   Detailed: http://localhost:{self.config.monitoring.health_check_port}/health/detailed")
            
            # Main application loop
            self._run_application()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start application: {e}")
            self.shutdown()
            raise
    
    def _run_application(self):
        """Main application loop"""
        while self.running and not self.shutdown_event.is_set():
            try:
                # Check application health
                health_status = health_monitor.check_all()
                
                if health_status['overall_status'] == 'unhealthy':
                    self.logger.warning("Application health status is unhealthy")
                
                # Log system metrics periodically
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    self._log_system_status()
                
                # Check for shutdown signal
                if self.shutdown_event.wait(timeout=10):
                    break
                
            except Exception as e:
                self.logger.error(f"Error in application loop: {e}")
                time.sleep(1)
    
    def _log_system_status(self):
        """Log current system status"""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent(interval=1)
            
            self.logger.info(f"System status - CPU: {cpu_percent:.1f}%, "
                           f"Memory: {memory.percent:.1f}%, "
                           f"Disk: {disk.percent:.1f}%")
            
            # Log component status
            component_status = {
                'matcher_running': self.matcher.running if self.matcher else False,
                'using_real_broker': self.executor.using_real_broker if self.executor else False,
                'active_conversation': conversation_manager.current_session_id is not None
            }
            
            self.logger.debug(f"Component status: {component_status}")
            
        except Exception as e:
            self.logger.error(f"Error logging system status: {e}")
    
    def shutdown(self):
        """Graceful shutdown"""
        if not self.running:
            return
        
        self.logger.info("Initiating graceful shutdown...")
        self.running = False
        self.shutdown_event.set()
        
        try:
            # Stop simulation
            if self.simulator:
                self.simulator.stop_simulation()
            
            # Stop matcher
            if self.matcher:
                self.matcher.stop_matching()
            
            # Stop monitoring
            if health_monitor:
                health_monitor.stop_monitoring()
            
            # End conversation
            conversation_manager.end_conversation({'reason': 'shutdown'})
            conversation_manager.shutdown()
            
            self.logger.info("✅ Application shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

def main():
    """Main production entry point"""
    app = ProductionApplication()
    
    try:
        app.start()
    except KeyboardInterrupt:
        app.shutdown()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        app.shutdown()
        sys.exit(1)

if __name__ == "__main__":
    main()
