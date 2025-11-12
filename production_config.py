"""
Production configuration management
Handles environment-specific settings, secrets, and security
"""

import os
import logging
import secrets
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str = "localhost"
    port: int = 5432
    name: str = "condition_task_list_trader"
    username: str = "postgres"
    password: Optional[str] = None
    ssl_mode: str = "require"
    pool_size: int = 10
    max_overflow: int = 20

@dataclass
class BrokerConfig:
    """Broker API configuration"""
    alpaca_api_key: Optional[str] = None
    alpaca_api_secret: Optional[str] = None
    alpaca_paper: bool = True
    alpaca_base_url: Optional[str] = None
    
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    binance_testnet: bool = True

@dataclass
class SecurityConfig:
    """Security configuration"""
    secret_key: str = None
    jwt_expiration_hours: int = 24
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # seconds
    enable_api_key_auth: bool = True
    log_sensitive_data: bool = False

@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration"""
    enable_prometheus: bool = True
    prometheus_port: int = 8000
    enable_health_check: bool = True
    health_check_port: int = 8001
    log_level: str = "INFO"
    file_logging: bool = True
    log_file_path: str = "/var/log/condition_task_list_trader"
    enable_error_alerts: bool = True

@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_position_size: float = 10000.0
    max_daily_loss: float = 1000.0
    stop_loss_percentage: float = 0.02
    take_profit_percentage: float = 0.05
    max_risk_per_trade: float = 0.01
    require_manual_confirmation: bool = False
    emergency_stop_loss_percentage: float = 0.05
    max_positions_per_symbol: int = 3

@dataclass
class ProductionConfig:
    """Complete production configuration"""
    environment: str = "development"
    debug: bool = False
    database: DatabaseConfig = DatabaseConfig()
    brokers: BrokerConfig = BrokerConfig()
    security: SecurityConfig = SecurityConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    risk: RiskConfig = RiskConfig()
    
    @classmethod
    def from_environment(cls) -> 'ProductionConfig':
        """Load configuration from environment variables"""
        config = cls()
        
        # Environment settings
        config.environment = os.getenv('ENVIRONMENT', 'production')
        config.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        
        # Database settings
        config.database.host = os.getenv('DB_HOST', 'localhost')
        config.database.port = int(os.getenv('DB_PORT', 5432))
        config.database.name = os.getenv('DB_NAME', 'condition_task_list_trader')
        config.database.username = os.getenv('DB_USERNAME', 'postgres')
        config.database.password = os.getenv('DB_PASSWORD')
        config.database.ssl_mode = os.getenv('DB_SSL_MODE', 'require')
        
        # Broker settings
        config.brokers.alpaca_api_key = os.getenv('ALPACA_API_KEY')
        config.brokers.alpaca_api_secret = os.getenv('ALPACA_API_SECRET')
        config.brokers.alpaca_paper = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'
        config.brokers.binance_api_key = os.getenv('BINANCE_API_KEY')
        config.brokers.binance_api_secret = os.getenv('BINANCE_API_SECRET')
        config.brokers.binance_testnet = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
        
        # Security settings
        config.security.secret_key = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
        config.security.jwt_expiration_hours = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
        config.security.rate_limit_requests = int(os.getenv('RATE_LIMIT_REQUESTS', 100))
        config.security.log_sensitive_data = os.getenv('LOG_SENSITIVE_DATA', 'false').lower() == 'true'
        
        # Monitoring settings
        config.monitoring.enable_prometheus = os.getenv('ENABLE_PROMETHEUS', 'true').lower() == 'true'
        config.monitoring.prometheus_port = int(os.getenv('PROMETHEUS_PORT', 8000))
        config.monitoring.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        config.monitoring.enable_error_alerts = os.getenv('ENABLE_ERROR_ALERTS', 'true').lower() == 'true'
        
        # Risk settings
        config.risk.max_position_size = float(os.getenv('MAX_POSITION_SIZE', 10000.0))
        config.risk.max_daily_loss = float(os.getenv('MAX_DAILY_LOSS', 1000.0))
        config.risk.stop_loss_percentage = float(os.getenv('STOP_LOSS_PERCENTAGE', 0.02))
        config.risk.take_profit_percentage = float(os.getenv('TAKE_PROFIT_PERCENTAGE', 0.05))
        config.risk.max_risk_per_trade = float(os.getenv('MAX_RISK_PER_TRADE', 0.01))
        config.risk.require_manual_confirmation = os.getenv('REQUIRE_MANUAL_CONFIRMATION', 'false').lower() == 'true'
        
        return config
    
    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return validation results"""
        issues = []
        
        # Check required settings for production
        if self.environment == 'production':
            if not self.database.password:
                issues.append("Database password not set")
            
            if not any([self.brokers.alpaca_api_key, self.brokers.binance_api_key]):
                issues.append("No broker API keys configured")
            
            if self.debug:
                issues.append("Debug mode should be disabled in production")
            
            if len(self.security.secret_key) < 32:
                issues.append("Secret key should be at least 32 characters")
        
        # Check risk settings
        if self.risk.max_risk_per_trade > 0.05:  # 5%
            issues.append("Max risk per trade should not exceed 5%")
        
        if self.risk.stop_loss_percentage > 0.10:  # 10%
            issues.append("Stop loss percentage should not exceed 10%")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'environment': self.environment
        }
    
    def get_database_url(self) -> str:
        """Get database connection URL"""
        if self.database.password:
            return (f"postgresql://{self.database.username}:{self.database.password}@"
                   f"{self.database.host}:{self.database.port}/{self.database.name}")
        else:
            return (f"postgresql://{self.database.username}@"
                   f"{self.database.host}:{self.database.port}/{self.database.name}")

class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "production_config.yaml"
        self.config = ProductionConfig.from_environment()
        self._validate_and_log()
    
    def _validate_and_log(self):
        """Validate configuration and log results"""
        validation = self.config.validate()
        
        if validation['valid']:
            logging.info(f"✅ Configuration valid for {validation['environment']} environment")
        else:
            for issue in validation['issues']:
                logging.warning(f"⚠️ Configuration issue: {issue}")
            
            if self.config.environment == 'production':
                raise ValueError("Configuration validation failed for production deployment")
    
    def get_config(self) -> ProductionConfig:
        """Get current configuration"""
        return self.config
    
    def reload_config(self):
        """Reload configuration from environment"""
        self.config = ProductionConfig.from_environment()
        self._validate_and_log()

# Global configuration instance
config_manager = ConfigManager()
