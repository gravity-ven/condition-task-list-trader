"""
Health checks and monitoring for production deployment
Includes system health, service status, and recovery mechanisms
"""

import time
import psutil
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import deque
import logging

@dataclass
class HealthStatus:
    """Health status of a component"""
    name: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    last_check: datetime
    response_time_ms: float
    details: Dict[str, Any] = None
    error_message: Optional[str] = None

class HealthCheck:
    """Base class for health checks"""
    
    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout
        self.last_status = None
        self.consecutive_failures = 0
        self.is_healthy = True
    
    def check(self) -> HealthStatus:
        """Perform health check"""
        start_time = time.time()
        
        try:
            result = self._check_health()
            response_time = (time.time() - start_time) * 1000
            
            status = HealthStatus(
                name=self.name,
                status='healthy' if result else 'unhealthy',
                last_check=datetime.now(),
                response_time_ms=response_time,
                details={'check_time': response_time}
            )
            
            if result:
                self.consecutive_failures = 0
                self.is_healthy = True
            else:
                self.consecutive_failures += 1
                if self.consecutive_failures >= 3:
                    self.is_healthy = False
                    status.status = 'unhealthy'
            
            self.last_status = status
            return status
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.consecutive_failures += 1
            
            status = HealthStatus(
                name=self.name,
                status='unhealthy',
                last_check=datetime.now(),
                response_time_ms=response_time,
                error_message=str(e),
                details={'exception_type': type(e).__name__}
            )
            
            if self.consecutive_failures >= 3:
                self.is_healthy = False
            
            self.last_status = status
            return status
    
    def _check_health(self) -> bool:
        """Override in subclasses"""
        raise NotImplementedError

class DatabaseHealthCheck(HealthCheck):
    """Database connectivity health check"""
    
    def __init__(self, database_connection):
        super().__init__("database")
        self.db_connection = database_connection
    
    def _check_health(self) -> bool:
        """Check database connectivity"""
        try:
            with self.db_connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            return result is not None
        except Exception:
            return False

class BrokerHealthCheck(HealthCheck):
    """Broker API health check"""
    
    def __init__(self, broker_manager):
        super().__init__("broker_api")
        self.broker_manager = broker_manager
    
    def _check_health(self) -> bool:
        """Check broker connectivity"""
        try:
            if self.broker_manager.active_broker:
                account_info = self.broker_manager.get_account_status()
                return len(account_info) > 0
            return True  # No broker configured is not unhealthy
        except Exception:
            return False

class MemoryHealthCheck(HealthCheck):
    """Memory usage health check"""
    
    def __init__(self, warning_threshold_mb: float = 1000, critical_threshold_mb: float = 2000):
        super().__init__("memory")
        self.warning_threshold = warning_threshold_mb
        self.critical_threshold = critical_threshold_mb
    
    def _check_health(self) -> bool:
        """Check memory usage"""
        memory = psutil.virtual_memory()
        used_mb = memory.used / (1024 * 1024)
        return used_mb < self.critical_threshold_mb

class DiskSpaceHealthCheck(HealthCheck):
    """Disk space health check"""
    
    def __init__(self, path: str = "/", warning_threshold_percent: float = 80, critical_threshold_percent: float = 90):
        super().__init__("disk_space")
        self.path = path
        self.warning_threshold = warning_threshold_percent
        self.critical_threshold = critical_threshold_percent
    
    def _check_health(self) -> bool:
        """Check disk space"""
        disk = psutil.disk_usage(self.path)
        used_percent = (disk.used / disk.total) * 100
        return used_percent < self.critical_threshold_percent

class ConditionsEngineHealthCheck(HealthCheck):
    """Conditions matching engine health check"""
    
    def __init__(self, conditions_matcher):
        super().__init__("conditions_engine")
        self.matcher = conditions_matcher
    
    def _check_health(self) -> bool:
        """Check conditions engine"""
        try:
            return self.matcher.running
        except Exception:
            return False

class HealthMonitor:
    """Main health monitoring system"""
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.health_history = deque(maxlen=1000)  # Keep last 1000 checks
        self.alert_callbacks: List[Callable] = []
        self.monitoring_thread = None
        self.is_monitoring = False
        self.logger = logging.getLogger("health_monitor")
    
    def add_check(self, health_check: HealthCheck):
        """Add a health check"""
        self.health_checks[health_check.name] = health_check
        self.logger.info(f"Added health check: {health_check.name}")
    
    def remove_check(self, name: str):
        """Remove a health check"""
        if name in self.health_checks:
            del self.health_checks[name]
            self.logger.info(f"Removed health check: {name}")
    
    def add_alert_callback(self, callback: Callable[[HealthStatus], None]):
        """Add callback for health alerts"""
        self.alert_callbacks.append(callback)
    
    def check_all(self) -> Dict[str, Any]:
        """Check all registered health checks"""
        results = {}
        overall_status = 'healthy'
        
        for name, check in self.health_checks.items():
            status = check.check()
            results[name] = asdict(status)
            
            # Determine overall status
            if status.status == 'unhealthy':
                overall_status = 'unhealthy'
            elif status.status == 'degraded' and overall_status == 'healthy':
                overall_status = 'degraded'
            
            # Trigger alerts if status changed
            if (check.last_status and 
                check.last_status.status != status.status and
                status.status in ['degraded', 'unhealthy']):
                self._trigger_alert(status)
        
        # Add system metrics
        system_metrics = self._get_system_metrics()
        
        full_check = {
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'checks': results,
            'system_metrics': system_metrics
        }
        
        # Store in history
        self.health_history.append(full_check)
        
        return full_check
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024 * 1024),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024 * 1024 * 1024),
                'uptime_hours': time.time() / 3600  # System uptime in hours
            }
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")
            return {}
    
    def _trigger_alert(self, status: HealthStatus):
        """Trigger health alert"""
        self.logger.warning(f"Health alert: {status.name} is {status.status}")
        
        for callback in self.alert_callbacks:
            try:
                callback(status)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    def start_monitoring(self, interval_seconds: float = 30.0):
        """Start continuous monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.monitoring_thread.start()
        self.logger.info(f"Started health monitoring with {interval_seconds}s interval")
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        self.logger.info("Stopped health monitoring")
    
    def _monitoring_loop(self, interval: float):
        """Background monitoring loop"""
        while self.is_monitoring:
            try:
                self.check_all()
                time.sleep(interval)
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(interval)
    
    def get_recent_history(self, limit: int = 100) -> List[Dict]:
        """Get recent health check history"""
        return list(self.health_history)[-limit:]

class RecoveryManager:
    """Automatic recovery for failed components"""
    
    def __init__(self, health_monitor: HealthMonitor):
        self.health_monitor = health_monitor
        self.recovery_actions: Dict[str, Callable] = {}
        self.logger = logging.getLogger("recovery_manager")
        
        # Register as alert callback
        health_monitor.add_alert_callback(self._handle_health_alert)
    
    def register_recovery_action(self, component: str, action: Callable[[], bool]):
        """Register automatic recovery action for a component"""
        self.recovery_actions[component] = action
        self.logger.info(f"Registered recovery action for {component}")
    
    def _handle_health_alert(self, status: HealthStatus):
        """Handle health change alert"""
        if status.status == 'unhealthy' and status.name in self.recovery_actions:
            self.logger.warning(f"Attempting recovery for {status.name}")
            
            try:
                success = self.recovery_actions[status.name]()
                if success:
                    self.logger.info(f"Recovery successful for {status.name}")
                else:
                    self.logger.error(f"Recovery failed for {status.name}")
            except Exception as e:
                self.logger.error(f"Error during recovery for {status.name}: {e}")

class HealthCheckServer:
    """HTTP server for health check endpoints"""
    
    def __init__(self, health_monitor: HealthMonitor, port: int = 8001):
        self.health_monitor = health_monitor
        self.port = port
        self.logger = logging.getLogger("health_server")
    
    def start_server(self):
        """Start simple HTTP health check server"""
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            
            class HealthHandler(BaseHTTPRequestHandler):
                def __init__(self, health_monitor, *args, **kwargs):
                    self.health_monitor = health_monitor
                    super().__init__(*args, **kwargs)
                
                def do_GET(self):
                    if self.path == '/health':
                        self.send_health_response()
                    elif self.path == '/health/detailed':
                        self.send_detailed_health_response()
                    else:
                        self.send_error(404, "Not Found")
                
                def send_health_response(self):
                    health_status = self.health_monitor.check_all()
                    overall_status = health_status['overall_status']
                    
                    status_code = 200 if overall_status == 'healthy' else 503
                    
                    self.send_response(status_code)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {
                        'status': overall_status,
                        'timestamp': health_status['timestamp']
                    }
                    
                    self.wfile.write(json.dumps(response).encode())
                
                def send_detailed_health_response(self):
                    health_status = self.health_monitor.check_all()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    self.wfile.write(json.dumps(health_status, indent=2).encode())
                
                def log_message(self, format, *args):
                    # Suppress default HTTP logging
                    pass
            
            # Create handler with health_monitor reference
            handler_factory = lambda *args, **kwargs: HealthHandler(self.health_monitor, *args, **kwargs)
            
            server = HTTPServer(('0.0.0.0', self.port), handler_factory)
            self.logger.info(f"Health check server started on port {self.port}")
            server.serve_forever()
            
        except ImportError:
            self.logger.error("http.server not available - health endpoint disabled")
        except Exception as e:
            self.logger.error(f"Failed to start health server: {e}")

# Global health monitoring instance
health_monitor = HealthMonitor()
