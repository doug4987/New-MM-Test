"""
Configuration Management System
Handles loading and validation of configuration settings
"""

import os
import json
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class ProphetAPIConfig:
    """Prophet API configuration"""
    access_key: str = ""
    secret_key: str = ""
    base_url: str = "https://api-ss-sandbox.betprophet.co"
    tournaments: List[str] = field(default_factory=lambda: ["MLB", "NBA", "NFL", "NHL"])
    

@dataclass 
class TradingConfig:
    """Trading configuration"""
    dry_run: bool = True
    max_stake_per_wager: float = 10.0
    max_total_exposure: float = 1000.0
    min_odds: int = -200
    max_odds: int = 200
    default_stake: float = 5.0
    wager_frequency_seconds: int = 30
    max_concurrent_wagers: int = 50


@dataclass
class StrategyConfig:
    """Strategy configuration"""
    strategy_type: str = "simple_market_maker"
    spread_margin: float = 0.02  # 2% margin
    inventory_target: int = 0
    max_position: int = 100
    rebalance_threshold: int = 10
    quote_refresh_seconds: int = 5
    

@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_daily_loss: float = 500.0
    max_position_size: float = 100.0
    stop_loss_percentage: float = 0.05  # 5%
    max_drawdown: float = 0.10  # 10%
    position_limits: Dict[str, float] = field(default_factory=dict)


@dataclass
class WebConfig:
    """Web interface configuration"""
    host: str = "127.0.0.1"
    port: int = 8000
    enable_dashboard: bool = True
    auto_reload: bool = False


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file_path: str = "logs/market_maker.log"
    max_file_size: str = "10MB"
    retention: str = "30 days"
    format: str = "{time} | {level} | {module}:{line} | {message}"


@dataclass 
class DatabaseConfig:
    """Database configuration"""
    type: str = "sqlite"
    url: str = "sqlite:///market_maker.db"
    echo_sql: bool = False


class Settings:
    """
    Main settings class that loads and manages all configuration
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config/default.yaml"
        
        # Initialize with defaults
        self.prophet_api = ProphetAPIConfig()
        self.trading = TradingConfig()
        self.strategy = StrategyConfig()
        self.risk = RiskConfig()
        self.web = WebConfig()
        self.logging = LoggingConfig()
        self.database = DatabaseConfig()
        
        # Load configuration
        self.load_config()
        
        # Load credentials from environment or user file
        self.load_credentials()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            config_path = Path(self.config_file)
            
            if not config_path.exists():
                logger.warning(f"Config file {self.config_file} not found, using defaults")
                self.create_default_config()
                return
            
            with open(config_path, 'r') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)
            
            # Update configurations
            if 'prophet_api' in config_data:
                self._update_config(self.prophet_api, config_data['prophet_api'])
            
            if 'trading' in config_data:
                self._update_config(self.trading, config_data['trading'])
            
            if 'strategy' in config_data:
                self._update_config(self.strategy, config_data['strategy'])
                
            if 'risk' in config_data:
                self._update_config(self.risk, config_data['risk'])
                
            if 'web' in config_data:
                self._update_config(self.web, config_data['web'])
                
            if 'logging' in config_data:
                self._update_config(self.logging, config_data['logging'])
                
            if 'database' in config_data:
                self._update_config(self.database, config_data['database'])
            
            logger.info(f"Configuration loaded from {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
    
    def load_credentials(self):
        """Load API credentials from environment variables or user_info.json"""
        try:
            # Try environment variables first
            access_key = os.getenv('PROPHET_ACCESS_KEY')
            secret_key = os.getenv('PROPHET_SECRET_KEY')
            
            if access_key and secret_key:
                self.prophet_api.access_key = access_key
                self.prophet_api.secret_key = secret_key
                logger.info("Loaded Prophet API credentials from environment variables")
                return
            
            # Try user_info.json file
            user_info_path = Path("config/user_info.json")
            if user_info_path.exists():
                with open(user_info_path, 'r') as f:
                    user_info = json.load(f)
                
                self.prophet_api.access_key = user_info.get('access_key', '')
                self.prophet_api.secret_key = user_info.get('secret_key', '')
                
                if 'tournaments' in user_info:
                    self.prophet_api.tournaments = user_info['tournaments']
                
                logger.info("Loaded Prophet API credentials from user_info.json")
                return
            
            # Create template user_info.json if it doesn't exist
            self.create_user_info_template()
            logger.warning("No API credentials found. Please configure them in config/user_info.json or environment variables")
            
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
    
    def create_user_info_template(self):
        """Create a template user_info.json file"""
        try:
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            user_info_template = {
                "_comment": "Add your Prophet API credentials here",
                "access_key": "your_access_key_here",
                "secret_key": "your_secret_key_here",
                "tournaments": ["MLB", "NBA", "NFL", "NHL"]
            }
            
            user_info_path = config_dir / "user_info.json"
            with open(user_info_path, 'w') as f:
                json.dump(user_info_template, f, indent=2)
            
            logger.info(f"Created user_info.json template at {user_info_path}")
            
        except Exception as e:
            logger.error(f"Error creating user_info.json template: {e}")
    
    def create_default_config(self):
        """Create default configuration file"""
        try:
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            default_config = {
                'prophet_api': {
                    'base_url': 'https://api-ss-sandbox.betprophet.co',
                    'tournaments': ['MLB', 'NBA', 'NFL', 'NHL']
                },
                'trading': {
                    'dry_run': True,
                    'max_stake_per_wager': 10.0,
                    'max_total_exposure': 1000.0,
                    'min_odds': -200,
                    'max_odds': 200,
                    'default_stake': 5.0,
                    'wager_frequency_seconds': 30,
                    'max_concurrent_wagers': 50
                },
                'strategy': {
                    'strategy_type': 'simple_market_maker',
                    'spread_margin': 0.02,
                    'inventory_target': 0,
                    'max_position': 100,
                    'rebalance_threshold': 10,
                    'quote_refresh_seconds': 5
                },
                'risk': {
                    'max_daily_loss': 500.0,
                    'max_position_size': 100.0,
                    'stop_loss_percentage': 0.05,
                    'max_drawdown': 0.10,
                    'position_limits': {}
                },
                'web': {
                    'host': '127.0.0.1',
                    'port': 8000,
                    'enable_dashboard': True,
                    'auto_reload': False
                },
                'logging': {
                    'level': 'INFO',
                    'file_path': 'logs/market_maker.log',
                    'max_file_size': '10MB',
                    'retention': '30 days',
                    'format': '{time} | {level} | {module}:{line} | {message}'
                },
                'database': {
                    'type': 'sqlite',
                    'url': 'sqlite:///market_maker.db',
                    'echo_sql': False
                }
            }
            
            config_path = Path(self.config_file)
            with open(config_path, 'w') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(default_config, f, default_flow_style=False, indent=2)
                else:
                    json.dump(default_config, f, indent=2)
            
            logger.info(f"Created default configuration at {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error creating default configuration: {e}")
    
    def _update_config(self, config_obj, config_data: dict):
        """Update configuration object with data from dict"""
        for key, value in config_data.items():
            if hasattr(config_obj, key):
                setattr(config_obj, key, value)
    
    def validate(self) -> bool:
        """Validate configuration settings"""
        try:
            # Validate Prophet API credentials
            if not self.prophet_api.access_key or not self.prophet_api.secret_key:
                logger.error("Prophet API credentials are required")
                return False
            
            # Validate trading settings
            if self.trading.max_stake_per_wager <= 0:
                logger.error("max_stake_per_wager must be positive")
                return False
            
            if self.trading.max_total_exposure <= 0:
                logger.error("max_total_exposure must be positive")
                return False
            
            # Validate strategy settings
            if self.strategy.spread_margin < 0:
                logger.error("spread_margin cannot be negative")
                return False
            
            # Validate risk settings
            if self.risk.max_daily_loss <= 0:
                logger.error("max_daily_loss must be positive")
                return False
            
            if not 0 < self.risk.stop_loss_percentage < 1:
                logger.error("stop_loss_percentage must be between 0 and 1")
                return False
            
            # Validate web settings
            if not 1024 <= self.web.port <= 65535:
                logger.error("Web port must be between 1024 and 65535")
                return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary"""
        return {
            'prophet_api': {
                'access_key': '***HIDDEN***',  # Don't expose credentials
                'secret_key': '***HIDDEN***',
                'base_url': self.prophet_api.base_url,
                'tournaments': self.prophet_api.tournaments
            },
            'trading': self.trading.__dict__,
            'strategy': self.strategy.__dict__,
            'risk': self.risk.__dict__,
            'web': self.web.__dict__,
            'logging': self.logging.__dict__,
            'database': self.database.__dict__
        }
    
    def update_from_dict(self, config_dict: Dict[str, Any]):
        """Update settings from dictionary"""
        for section, values in config_dict.items():
            if hasattr(self, section):
                config_obj = getattr(self, section)
                self._update_config(config_obj, values)
    
    def get_log_file_path(self) -> Path:
        """Get the log file path, creating directory if needed"""
        log_path = Path(self.logging.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path
