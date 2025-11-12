"""
Production logging system
Structured logging with security, monitoring, and compliance features
"""

import logging
import logging.handlers
import json
import time
import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
import traceback
from functools import wraps

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str
    level: str
    message: str
    component: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    trade_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    error_details: Optional[str] = None

class SecurityFilter(logging.Filter):
    """Filter to prevent sensitive data from being logged"""
    
    SENSITIVE_FIELDS = [
        'password', 'api_key', 'api_secret', 'token', 
        'secret', 'credential', 'key', 'auth', 'private'
    ]
    
    def filter(self, record):
        """Replace sensitive data in log records"""
        if hasattr(record, 'msg') and record.msg:
            record.msg = self._sanitize_data(record.msg)
        
        if hasattr(record, 'args') and record.args:
            record.args = tuple(self._sanitize_data(str(arg)) for arg in record.args)
        
        return True
    
    def _sanitize_data(self, data: str) -> str:
        """Replace sensitive data with placeholder"""
        sanitized = data
        for field in self.SENSITIVE_FIELDS:
            # Simple pattern matching for sensitive fields
            import re
            pattern = rf'{field}["\':\s]+["\']*([^"\'\s,}}]+)["\']*'
            sanitized = re.sub(pattern, f'{field}="[REDACTED]"', sanitized, flags=re.IGNORECASE)
        return sanitized

class StructuredFormatter(logging.Formatter):
    """JSON structured logging formatter"""
    
    def __init__(self, include_metadata: bool = True):
        super().__init__()
        self.include_metadata = include_metadata
    
    def format(self, record):
        """Format log record as JSON"""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'component': getattr(record, 'component', 'unknown'),
            'function': record.funcName,
            'line': record.lineno,
            'module': record.module
        }
        
        # Add optional fields if present
        optional_fields = ['session_id', 'user_id', 'trade_id']
        for field in optional_fields:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)
        
        # Add metadata if available
        if self.include_metadata and hasattr(record, 'metadata'):
            log_entry['metadata'] = record.metadata
        
        # Add error details for exceptions
        if record.exc_info:
            log_entry['error_details'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry, default=str, separators=(',', ':'))

class ProductionLogger:
    """Production-ready logging system"""
    
    def __init__(self, config):
        self.config = config
        self.loggers = {}
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        # Create log directory if it doesn't exist
        log_dir = Path(self.config.monitoring.log_file_path)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Root logger setup
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.monitoring.log_level))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler (human readable for terminal)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler (structured JSON)
        if self.config.monitoring.file_logging:
            app_log_file = log_dir / "application.log"
            file_handler = logging.handlers.RotatingFileHandler(
                str(app_log_file),
                maxBytes=50*1024*1024,  # 50MB
                backupCount=10
            )
            file_handler.setLevel(getattr(logging, self.config.monitoring.log_level))
            file_handler.addFilter(SecurityFilter())
            file_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(file_handler)
            
            # Error log file (for critical errors)
            error_log_file = log_dir / "errors.log"
            error_handler = logging.handlers.RotatingFileHandler(
                str(error_log_file),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.addFilter(SecurityFilter())
            error_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(error_handler)
            
            # Trade log file (for audit trail)
            trade_log_file = log_dir / "trades.log"
            trade_handler = logging.handlers.RotatingFileHandler(
                str(trade_log_file),
                maxBytes=20*1024*1024,  # 20MB
                backupCount=20
            )
            trade_handler.setLevel(logging.INFO)
            trade_handler.addFilter(TradeLogFilter())
            trade_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(trade_handler)
    
    def get_logger(self, name: str, component: str = None) -> logging.Logger:
        """Get configured logger with additional fields"""
        logger = logging.getLogger(name)
        
        # Add component information if provided
        if component:
            old_factory = logging.getLogRecordFactory()
            
            def record_factory(*args, **kwargs):
                record = old_factory(*args, **kwargs)
                record.component = component
                return record
            
            logging.setLogRecordFactory(record_factory)
        
        return logger

class TradeLogFilter(logging.Filter):
    """Filter for trade-related logs"""
    
    def filter(self, record):
        """Only allow trade-related logs"""
        trade_keywords = ['trade', 'order', 'position', 'execution', 'broker']
        message = record.getMessage().lower()
        return any(keyword in message for keyword in trade_keywords)

class AuditLogger:
    """Specialized logger for compliance and audit trails"""
    
    def __init__(self, base_logger: logging.Logger):
        self.logger = base_logger
    
    def log_trade_execution(self, trade_data: Dict[str, Any]):
        """Log trade execution for audit"""
        self.logger.info(
            "Trade executed",
            extra={
                'component': 'trade_executor',
                'trade_id': trade_data.get('execution_id'),
                'metadata': {
                    'symbol': trade_data.get('symbol'),
                    'quantity': trade_data.get('quantity'),
                    'price': trade_data.get('price'),
                    'order_type': trade_data.get('order_type'),
                    'broker': trade_data.get('broker'),
                    'timestamp': trade_data.get('timestamp')
                }
            }
        )
    
    def log_condition_change(self, condition_data: Dict[str, Any]):
        """Log condition status changes"""
        self.logger.info(
            "Condition status changed",
            extra={
                'component': 'conditions_matcher',
                'session_id': condition_data.get('session_id'),
                'metadata': {
                    'condition_id': condition_data.get('condition_id'),
                    'task_id': condition_data.get('task_id'),
                    'status': condition_data.get('status'),
                    'current_value': condition_data.get('current_value'),
                    'target_value': condition_data.get('target_value')
                }
            }
        )
    
    def log_security_event(self, security_event: Dict[str, Any]):
        """Log security-related events"""
        self.logger.warning(
            f"Security event: {security_event.get('event_type')}",
            extra={
                'component': 'security',
                'metadata': {
                    'event_type': security_event.get('event_type'),
                    'source_ip': security_event.get('source_ip'),
                    'user_agent': security_event.get('user_agent'),
                    'timestamp': security_event.get('timestamp'),
                    'severity': security_event.get('severity', 'medium')
                }
            }
        )

class MetricsLogger:
    """Logger for application metrics and performance"""
    
    def __init__(self, base_logger: logging.Logger):
        self.logger = base_logger
        self.timings = {}
    
    def log_timing(self, operation: str, duration: float, metadata: Dict = None):
        """Log operation timing"""
        self.logger.info(
            f"Operation timing: {operation}",
            extra={
                'component': 'performance',
                'metadata': {
                    'operation': operation,
                    'duration_seconds': duration,
                    **(metadata or {})
                }
            }
        )
    
    def log_memory_usage(self, component: str, memory_mb: float):
        """Log memory usage"""
        self.logger.debug(
            f"Memory usage: {component}",
            extra={
                'component': 'performance',
                'metadata': {
                    'metric_type': 'memory_usage',
                    'component': component,
                    'memory_mb': memory_mb
                }
            }
        )
    
    def log_error_rate(self, component: str, errors: int, total: float):
        """Log error rate"""
        error_rate = (errors / total) * 100 if total > 0 else 0
        self.logger.info(
            f"Error rate for {component}: {error_rate:.2f}%",
            extra={
                'component': 'performance',
                'metadata': {
                    'metric_type': 'error_rate',
                    'component': component,
                    'errors': errors,
                    'total_requests': total,
                    'error_rate_percentage': error_rate
                }
            }
        )

def log_execution_time(logger: logging.Logger = None):
    """Decorator to log function execution time"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                target_logger = logger or logging.getLogger(func.__module__)
                target_logger.debug(
                    f"Function {func.__name__} executed in {duration:.3f}s",
                    extra={'component': 'performance', 'metadata': {'function': func.__name__, 'duration': duration}}
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                target_logger = logger or logging.getLogger(func.__module__)
                target_logger.error(
                    f"Function {func.__name__} failed after {duration:.3f}s: {str(e)}",
                    extra={'component': 'performance', 'metadata': {'function': func.__name__, 'duration': duration}}
                )
                raise
        return wrapper
    return decorator

# Global logger instances
def get_production_logger():
    """Get production logger instance"""
    from production_config import config_manager
    production_logger = ProductionLogger(config_manager.get_config())
    return production_logger.get_logger("condition_task_list_trader", "main_application")

def get_audit_logger():
    """Get audit logger for compliance"""
    base_logger = logging.getLogger("audit")
    return AuditLogger(base_logger)

def get_metrics_logger():
    """Get metrics logger"""
    base_logger = logging.getLogger("metrics")
    return MetricsLogger(base_logger)

# Initialize logging system
production_logger = get_production_logger()
audit_logger = get_audit_logger()
metrics_logger = get_metrics_logger()
