"""
Risk Manager
Handles risk assessment and position monitoring
"""

import time
from typing import Dict, List, Optional, Any

from loguru import logger
from config.settings import RiskConfig
from core.wager_manager import WagerManager
from exchanges.prophet_sports_api import Wager


class RiskManager:
    """
    Manages trading risk and position limits
    """
    
    def __init__(self, risk_config: RiskConfig, wager_manager: WagerManager):
        self.config = risk_config
        self.wager_manager = wager_manager
        
        # Risk tracking
        self.daily_pnl = 0.0
        self.session_start_time = time.time()
        self.risk_breaches = []
        
        logger.info("Risk Manager initialized")
    
    def check_wager_risk(self, wager: Wager, market_context: Dict[str, Any] = None) -> bool:
        """
        Check if a wager passes risk controls
        
        Args:
            wager: The wager to check
            market_context: Additional market context
            
        Returns:
            True if wager passes risk checks, False otherwise
        """
        try:
            # Check position size limits
            if wager.stake > self.config.max_position_size:
                logger.warning(f"Wager stake {wager.stake} exceeds max position size {self.config.max_position_size}")
                return False
            
            # Check total exposure
            current_exposure = self.wager_manager.get_total_exposure()
            if current_exposure + wager.stake > self.config.max_position_size * 10:  # Simple exposure check
                logger.warning(f"Total exposure would exceed limits: {current_exposure + wager.stake}")
                return False
            
            # Check daily loss limit
            if self.daily_pnl < -self.config.max_daily_loss:
                logger.warning(f"Daily loss limit exceeded: {self.daily_pnl}")
                return False
            
            # Event-specific limits
            if market_context:
                event_id = market_context.get('event_id')
                if event_id:
                    event_exposure = self.wager_manager.get_exposure_by_event(event_id)
                    event_limit = self.config.position_limits.get(str(event_id), self.config.max_position_size)
                    if event_exposure + wager.stake > event_limit:
                        logger.warning(f"Event exposure limit exceeded for event {event_id}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in risk check: {e}")
            return False
    
    def update_pnl(self, pnl_change: float):
        """Update daily P&L"""
        self.daily_pnl += pnl_change
        
        # Check for stop loss
        if abs(self.daily_pnl) > self.config.max_daily_loss:
            self.risk_breaches.append({
                'type': 'daily_loss_limit',
                'value': self.daily_pnl,
                'limit': self.config.max_daily_loss,
                'timestamp': time.time()
            })
            logger.error(f"Daily loss limit breached: {self.daily_pnl}")
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary"""
        return {
            'daily_pnl': self.daily_pnl,
            'total_exposure': self.wager_manager.get_total_exposure(),
            'active_wagers': len(self.wager_manager.active_wagers),
            'session_uptime': time.time() - self.session_start_time,
            'risk_breaches': len(self.risk_breaches),
            'limits': {
                'max_daily_loss': self.config.max_daily_loss,
                'max_position_size': self.config.max_position_size,
                'max_drawdown': self.config.max_drawdown
            }
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics (typically called at start of new trading day)"""
        self.daily_pnl = 0.0
        self.risk_breaches.clear()
        logger.info("Daily risk statistics reset")
