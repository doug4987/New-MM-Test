"""
Wager Manager
Handles wager lifecycle, tracking, and management
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from loguru import logger
from config.settings import TradingConfig
from exchanges.prophet_sports_api import ProphetSportsAPI, Wager, WagerStatus


@dataclass
class WagerRecord:
    """Extended wager record with tracking information"""
    wager: Wager
    created_at: float
    updated_at: float
    strategy_name: str
    market_context: Dict[str, Any]


class WagerManager:
    """
    Manages the lifecycle of all wagers placed by the platform
    """
    
    def __init__(self, api: ProphetSportsAPI, trading_config: TradingConfig):
        self.api = api
        self.trading_config = trading_config
        
        # Wager tracking
        self.active_wagers: Dict[str, WagerRecord] = {}  # external_id -> WagerRecord
        self.wager_history: List[WagerRecord] = []
        self.pending_placements: Dict[str, Wager] = {}
        self.pending_cancellations: Dict[str, str] = {}  # external_id -> reason
        
        # Statistics
        self.total_placed = 0
        self.total_cancelled = 0
        self.total_matched = 0
        self.total_settled = 0
        
        logger.info("Wager Manager initialized")
    
    async def place_wager(self, wager: Wager, strategy_name: str, market_context: Dict[str, Any] = None) -> Optional[int]:
        """
        Place a new wager through the manager
        
        Args:
            wager: The wager to place
            strategy_name: Name of the strategy placing the wager
            market_context: Additional market context
            
        Returns:
            Wager ID if successful, None otherwise
        """
        try:
            # Validate wager before placing
            if not self._validate_wager(wager):
                logger.error(f"Wager validation failed: {wager}")
                return None
            
            # Check position limits
            if not self._check_position_limits(wager):
                logger.warning(f"Position limits exceeded for wager: {wager}")
                return None
            
            # Add to pending placements
            self.pending_placements[wager.external_id] = wager
            
            # Place the wager via API
            wager_id = await self.api.place_wager(wager)
            
            if wager_id:
                # Create wager record
                wager_record = WagerRecord(
                    wager=wager,
                    created_at=time.time(),
                    updated_at=time.time(),
                    strategy_name=strategy_name,
                    market_context=market_context or {}
                )
                
                # Add to active wagers
                self.active_wagers[wager.external_id] = wager_record
                self.total_placed += 1
                
                logger.info(f"Placed wager {wager.external_id} (ID: {wager_id}) for strategy {strategy_name}")
                
            # Remove from pending
            self.pending_placements.pop(wager.external_id, None)
            
            return wager_id
            
        except Exception as e:
            logger.error(f"Error placing wager: {e}")
            self.pending_placements.pop(wager.external_id, None)
            return None
    
    async def cancel_wager(self, external_id: str, reason: str = "strategy_request") -> bool:
        """
        Cancel an active wager
        
        Args:
            external_id: External ID of the wager to cancel
            reason: Reason for cancellation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if external_id not in self.active_wagers:
                logger.warning(f"Cannot cancel wager {external_id} - not found in active wagers")
                return False
            
            # Add to pending cancellations
            self.pending_cancellations[external_id] = reason
            
            # Cancel via API
            success = await self.api.cancel_wager(external_id)
            
            if success:
                # Move to history
                wager_record = self.active_wagers.pop(external_id)
                wager_record.updated_at = time.time()
                wager_record.wager.status = WagerStatus.CANCELLED
                
                self.wager_history.append(wager_record)
                self.total_cancelled += 1
                
                logger.info(f"Cancelled wager {external_id} - reason: {reason}")
            
            # Remove from pending
            self.pending_cancellations.pop(external_id, None)
            
            return success
            
        except Exception as e:
            logger.error(f"Error cancelling wager {external_id}: {e}")
            self.pending_cancellations.pop(external_id, None)
            return False
    
    async def cancel_all_wagers(self, reason: str = "platform_stop") -> bool:
        """
        Cancel all active wagers
        
        Args:
            reason: Reason for mass cancellation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Cancelling all {len(self.active_wagers)} active wagers - reason: {reason}")
            
            # Cancel via API (mass cancellation)
            success = await self.api.cancel_all_wagers()
            
            if success:
                # Move all active wagers to history
                current_time = time.time()
                for external_id, wager_record in self.active_wagers.items():
                    wager_record.updated_at = current_time
                    wager_record.wager.status = WagerStatus.CANCELLED
                    self.wager_history.append(wager_record)
                
                self.total_cancelled += len(self.active_wagers)
                self.active_wagers.clear()
                
                logger.info(f"Successfully cancelled all wagers")
            
            return success
            
        except Exception as e:
            logger.error(f"Error cancelling all wagers: {e}")
            return False
    
    async def process_update(self, update_data: Any):
        """Process wager status updates from the API"""
        try:
            # This would parse the actual update format from Prophet API
            # For now, we'll implement a basic structure
            
            logger.debug(f"Processing wager update: {update_data}")
            
            # Parse update data and update wager status
            # Implementation depends on actual Prophet API update format
            
        except Exception as e:
            logger.error(f"Error processing wager update: {e}")
    
    def get_active_wagers(self) -> List[WagerRecord]:
        """Get all active wagers"""
        return list(self.active_wagers.values())
    
    def get_wagers_by_strategy(self, strategy_name: str) -> List[WagerRecord]:
        """Get active wagers for a specific strategy"""
        return [
            record for record in self.active_wagers.values() 
            if record.strategy_name == strategy_name
        ]
    
    def get_wager_by_id(self, external_id: str) -> Optional[WagerRecord]:
        """Get a specific wager by external ID"""
        return self.active_wagers.get(external_id)
    
    def get_total_exposure(self) -> float:
        """Calculate total exposure from active wagers"""
        return sum(
            record.wager.stake 
            for record in self.active_wagers.values()
        )
    
    def get_exposure_by_event(self, event_id: int) -> float:
        """Calculate exposure for a specific event"""
        return sum(
            record.wager.stake 
            for record in self.active_wagers.values()
            if record.market_context.get('event_id') == event_id
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get wager manager statistics"""
        return {
            'active_wagers': len(self.active_wagers),
            'total_placed': self.total_placed,
            'total_cancelled': self.total_cancelled,
            'total_matched': self.total_matched,
            'total_settled': self.total_settled,
            'total_exposure': self.get_total_exposure(),
            'pending_placements': len(self.pending_placements),
            'pending_cancellations': len(self.pending_cancellations),
            'history_count': len(self.wager_history)
        }
    
    def _validate_wager(self, wager: Wager) -> bool:
        """Validate wager parameters"""
        # Check stake limits
        if wager.stake <= 0:
            logger.error(f"Invalid stake: {wager.stake}")
            return False
        
        if wager.stake > self.trading_config.max_stake_per_wager:
            logger.error(f"Stake {wager.stake} exceeds maximum {self.trading_config.max_stake_per_wager}")
            return False
        
        # Check odds limits
        if not (self.trading_config.min_odds <= wager.odds <= self.trading_config.max_odds):
            logger.error(f"Odds {wager.odds} outside allowed range [{self.trading_config.min_odds}, {self.trading_config.max_odds}]")
            return False
        
        return True
    
    def _check_position_limits(self, wager: Wager) -> bool:
        """Check if wager would exceed position limits"""
        # Check total exposure limit
        current_exposure = self.get_total_exposure()
        if current_exposure + wager.stake > self.trading_config.max_total_exposure:
            logger.warning(f"Total exposure limit exceeded: {current_exposure + wager.stake} > {self.trading_config.max_total_exposure}")
            return False
        
        # Check concurrent wager limit
        if len(self.active_wagers) >= self.trading_config.max_concurrent_wagers:
            logger.warning(f"Maximum concurrent wagers reached: {len(self.active_wagers)}")
            return False
        
        return True
    
    def cleanup_old_records(self, max_age_days: int = 7):
        """Clean up old wager history records"""
        try:
            cutoff_time = time.time() - (max_age_days * 24 * 3600)
            
            original_count = len(self.wager_history)
            self.wager_history = [
                record for record in self.wager_history 
                if record.updated_at > cutoff_time
            ]
            
            cleaned_count = original_count - len(self.wager_history)
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old wager records")
                
        except Exception as e:
            logger.error(f"Error cleaning up wager records: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on wager manager"""
        health = {
            'status': 'healthy',
            'issues': [],
            'statistics': self.get_statistics()
        }
        
        try:
            # Check for stuck pending operations
            current_time = time.time()
            
            # Check for old pending placements (more than 30 seconds)
            old_placements = [
                ext_id for ext_id, wager in self.pending_placements.items()
                if current_time - (wager.timestamp or 0) > 30
            ]
            
            if old_placements:
                health['issues'].append(f"Stuck pending placements: {len(old_placements)}")
                health['status'] = 'warning'
            
            # Check for excessive exposure
            total_exposure = self.get_total_exposure()
            if total_exposure > self.trading_config.max_total_exposure * 0.9:
                health['issues'].append(f"High exposure: ${total_exposure:.2f}")
                health['status'] = 'warning'
            
            # Check for too many active wagers
            if len(self.active_wagers) > self.trading_config.max_concurrent_wagers * 0.9:
                health['issues'].append(f"High wager count: {len(self.active_wagers)}")
                health['status'] = 'warning'
            
        except Exception as e:
            health['status'] = 'error'
            health['issues'].append(f"Health check error: {e}")
        
        return health
