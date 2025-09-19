"""
Simple Market Maker Strategy
Basic market making strategy for sports betting
"""

import asyncio
import random
import time
from typing import Dict, List, Optional, Any

from loguru import logger
from config.settings import StrategyConfig
from exchanges.prophet_sports_api import ProphetSportsAPI, Wager
from risk.risk_manager import RiskManager
from core.wager_manager import WagerManager


class SimpleMarketMaker:
    """
    Simple market making strategy that places random wagers for demonstration
    """
    
    def __init__(self, strategy_config: StrategyConfig, api: ProphetSportsAPI, 
                 risk_manager: RiskManager, wager_manager: WagerManager):
        self.config = strategy_config
        self.api = api
        self.risk_manager = risk_manager
        self.wager_manager = wager_manager
        
        self.is_active = False
        self.last_quote_time = 0.0
        
        logger.info("Simple Market Maker strategy initialized")
    
    async def start(self):
        """Start the strategy"""
        self.is_active = True
        logger.info("Simple Market Maker strategy started")
    
    async def stop(self):
        """Stop the strategy"""
        self.is_active = False
        logger.info("Simple Market Maker strategy stopped")
    
    async def refresh_quotes(self):
        """Refresh quotes (main strategy logic)"""
        if not self.is_active:
            return
        
        try:
            self.last_quote_time = time.time()
            
            # Get available events
            if not self.api.sport_events:
                logger.debug("No events available for market making")
                return
            
            # Simple strategy: randomly place small wagers on moneyline markets
            await self._place_random_wagers()
            
        except Exception as e:
            logger.error(f"Error in refresh_quotes: {e}")
    
    async def _place_random_wagers(self):
        """Place random wagers for demonstration"""
        try:
            # Limit to a few wagers per refresh
            max_wagers_per_refresh = 3
            wagers_placed = 0
            
            # Randomly select events
            event_ids = list(self.api.sport_events.keys())
            if not event_ids:
                return
            
            selected_events = random.sample(event_ids, min(max_wagers_per_refresh, len(event_ids)))
            
            for event_id in selected_events:
                if wagers_placed >= max_wagers_per_refresh:
                    break
                
                event = self.api.sport_events[event_id]
                
                # Look for moneyline markets
                for market in event.markets:
                    if market.get('type') == 'moneyline' and random.random() < 0.3:  # 30% chance
                        selections = market.get('selections', [])
                        if selections:
                            selection = random.choice(selections)
                            if isinstance(selection, list) and len(selection) > 0:
                                line_id = selection[0].get('line_id')
                                if line_id:
                                    # Create wager
                                    odds = self.api.get_random_valid_odds()
                                    stake = random.uniform(1.0, self.config.max_position / 10)  # Small stakes
                                    
                                    wager = self.api.create_wager(line_id, odds, stake)
                                    
                                    # Check risk
                                    market_context = {
                                        'event_id': event_id,
                                        'market_type': 'moneyline',
                                        'event_name': event.name
                                    }
                                    
                                    if self.risk_manager.check_wager_risk(wager, market_context):
                                        # Place wager via wager manager
                                        wager_id = await self.wager_manager.place_wager(
                                            wager, 
                                            "simple_market_maker", 
                                            market_context
                                        )
                                        
                                        if wager_id:
                                            wagers_placed += 1
                                            logger.info(f"Placed wager on {event.name}: {odds} odds, ${stake:.2f} stake")
                                        break  # One wager per event max
            
        except Exception as e:
            logger.error(f"Error placing random wagers: {e}")
    
    async def on_market_data_update(self, data: Any):
        """Handle market data updates"""
        try:
            # Process market data updates and adjust strategy if needed
            logger.debug(f"Market data update received: {type(data)}")
            
        except Exception as e:
            logger.error(f"Error processing market data update: {e}")
    
    async def rebalance_positions(self):
        """Rebalance positions if needed"""
        if not self.is_active:
            return
        
        try:
            # Simple rebalancing: cancel some old wagers randomly
            active_wagers = self.wager_manager.get_wagers_by_strategy("simple_market_maker")
            
            if len(active_wagers) > self.config.max_position:
                # Cancel some random wagers
                wagers_to_cancel = random.sample(
                    active_wagers, 
                    len(active_wagers) - self.config.max_position
                )
                
                for wager_record in wagers_to_cancel:
                    await self.wager_manager.cancel_wager(
                        wager_record.wager.external_id, 
                        "position_rebalance"
                    )
                    
                logger.info(f"Cancelled {len(wagers_to_cancel)} wagers for position rebalancing")
            
        except Exception as e:
            logger.error(f"Error in position rebalancing: {e}")
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        active_wagers = self.wager_manager.get_wagers_by_strategy("simple_market_maker")
        
        return {
            'strategy_name': 'simple_market_maker',
            'is_active': self.is_active,
            'active_wagers': len(active_wagers),
            'total_exposure': sum(w.wager.stake for w in active_wagers),
            'last_quote_time': self.last_quote_time,
            'config': {
                'max_position': self.config.max_position,
                'spread_margin': self.config.spread_margin,
                'quote_refresh_seconds': self.config.quote_refresh_seconds
            }
        }
