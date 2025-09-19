"""
Market Making Platform Core
Main orchestrator that coordinates all components of the platform
"""

import asyncio
import time
import threading
import schedule
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from loguru import logger

from config.settings import Settings
from exchanges.prophet_sports_api import ProphetSportsAPI, Wager, WagerSide
from strategies.simple_market_maker import SimpleMarketMaker
from risk.risk_manager import RiskManager
from data.market_data_manager import MarketDataManager
from core.wager_manager import WagerManager


@dataclass
class PlatformStats:
    """Platform performance statistics"""
    start_time: float
    total_wagers_placed: int = 0
    total_wagers_cancelled: int = 0
    total_matched_wagers: int = 0
    current_balance: float = 0.0
    total_pnl: float = 0.0
    active_positions: int = 0
    uptime_seconds: float = 0.0


class MarketMakingPlatform:
    """
    Main Market Making Platform
    Orchestrates all components and manages the trading lifecycle
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.is_running = False
        self.stats = PlatformStats(start_time=time.time())
        
        # Core components
        self.prophet_api: Optional[ProphetSportsAPI] = None
        self.market_data_manager: Optional[MarketDataManager] = None
        self.strategy: Optional[SimpleMarketMaker] = None
        self.risk_manager: Optional[RiskManager] = None
        self.wager_manager: Optional[WagerManager] = None
        
        # Internal state
        self.active_tournaments: Dict = {}
        self.active_events: Dict = {}
        self.current_positions: Dict = {}
        self.pending_wagers: Dict = {}
        
        # Threading
        self.scheduler_thread: Optional[threading.Thread] = None
        self.stop_event = asyncio.Event()
        
        logger.info("Market Making Platform initialized")
    
    async def start(self):
        """Start the market making platform"""
        try:
            logger.info("Starting Market Making Platform...")
            
            # Validate configuration
            if not self.settings.validate():
                raise ValueError("Configuration validation failed")
            
            # Initialize components
            await self._initialize_components()
            
            # Connect to Prophet API
            await self._connect_to_api()
            
            # Load market data
            await self._load_market_data()
            
            # Start trading strategies
            await self._start_strategies()
            
            # Start scheduler
            self._start_scheduler()
            
            # Start async periodic tasks
            asyncio.create_task(self._run_periodic_tasks())
            
            self.is_running = True
            logger.info("Market Making Platform started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start platform: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the market making platform"""
        try:
            logger.info("Stopping Market Making Platform...")
            self.is_running = False
            self.stop_event.set()
            
            # Cancel all open wagers
            if self.prophet_api and not self.settings.trading.dry_run:
                logger.info("Cancelling all open wagers...")
                await self.prophet_api.cancel_all_wagers()
            
            # Stop scheduler
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=5.0)
            
            # Disconnect from API
            if self.prophet_api:
                await self.prophet_api.disconnect()
            
            # Update final stats
            self.stats.uptime_seconds = time.time() - self.stats.start_time
            
            logger.info("Market Making Platform stopped")
            logger.info(f"Final Stats: {self._get_stats_summary()}")
            
        except Exception as e:
            logger.error(f"Error stopping platform: {e}")
    
    async def _initialize_components(self):
        """Initialize all platform components"""
        logger.info("Initializing platform components...")
        
        # Initialize Prophet API client
        self.prophet_api = ProphetSportsAPI(
            access_key=self.settings.prophet_api.access_key,
            secret_key=self.settings.prophet_api.secret_key,
            base_url=self.settings.prophet_api.base_url
        )
        
        # Set tournaments of interest
        self.prophet_api.tournaments_interested = self.settings.prophet_api.tournaments
        
        # Initialize market data manager
        self.market_data_manager = MarketDataManager(self.prophet_api)
        
        # Initialize wager manager
        self.wager_manager = WagerManager(
            api=self.prophet_api,
            trading_config=self.settings.trading
        )
        
        # Initialize risk manager
        self.risk_manager = RiskManager(
            risk_config=self.settings.risk,
            wager_manager=self.wager_manager
        )
        
        # Initialize trading strategy
        self.strategy = SimpleMarketMaker(
            strategy_config=self.settings.strategy,
            api=self.prophet_api,
            risk_manager=self.risk_manager,
            wager_manager=self.wager_manager
        )
        
        logger.info("Platform components initialized")
    
    async def _connect_to_api(self):
        """Connect to Prophet API"""
        logger.info("Connecting to Prophet API...")
        
        success = await self.prophet_api.login()
        if not success:
            raise ConnectionError("Failed to connect to Prophet API")
        
        # Setup event handlers
        self.prophet_api.subscribe_market_data(self._on_market_data_update)
        self.prophet_api.subscribe_wager_updates(self._on_wager_update)
        self.prophet_api.subscribe_balance_updates(self._on_balance_update)
        
        logger.info("Connected to Prophet API successfully")
    
    async def _create_mock_data(self):
        """Create mock data for demonstration when API is unavailable"""
        from exchanges.prophet_sports_api import Tournament, SportEvent
        
        logger.info("Creating mock data for demonstration...")
        
        # Create mock tournaments
        mock_tournament = Tournament(id=1, name="MLB", sport="Baseball")
        self.prophet_api.my_tournaments = {1: mock_tournament}
        
        # Create mock events
        mock_events = {
            1001: SportEvent(
                event_id=1001,
                name="Yankees vs Red Sox",
                tournament_id=1,
                start_time="2023-09-17T19:00:00Z",
                markets=[
                    {"market_id": 2001, "market_type": "moneyline", "selections": [
                        {"selection_id": 3001, "name": "Yankees", "odds": -120},
                        {"selection_id": 3002, "name": "Red Sox", "odds": 110}
                    ]}
                ]
            ),
            1002: SportEvent(
                event_id=1002,
                name="Dodgers vs Giants",
                tournament_id=1,
                start_time="2023-09-17T22:00:00Z",
                markets=[
                    {"market_id": 2002, "market_type": "moneyline", "selections": [
                        {"selection_id": 3003, "name": "Dodgers", "odds": -150},
                        {"selection_id": 3004, "name": "Giants", "odds": 130}
                    ]}
                ]
            )
        }
        
        self.prophet_api.sport_events = mock_events
        
        # Set mock balance
        self.prophet_api.balance = 10000.0
        
        # Create mock odds ladder
        self.prophet_api.valid_odds = list(range(-200, -100, 5)) + list(range(100, 300, 5))
        
        logger.info(f"Created mock data: {len(self.prophet_api.my_tournaments)} tournaments, {len(mock_events)} events")
    
    async def _load_market_data(self):
        """Load initial market data"""
        logger.info("Loading market data...")
        
        # Load real data from API
        await self.prophet_api.initialize_data()
        
        # Get initial balance
        balance = await self.prophet_api.get_balance()
        self.stats.current_balance = balance.balance
        
        # Update our local state
        self.active_tournaments = self.prophet_api.my_tournaments
        self.active_events = self.prophet_api.sport_events
        
        # Initialize order books
        await self.market_data_manager.initialize_order_books()
        
        logger.info(f"Loaded {len(self.active_tournaments)} tournaments with {len(self.active_events)} events")
        logger.info(f"Initialized {len(self.market_data_manager.order_books)} order books")
        logger.info(f"Current balance: ${self.stats.current_balance:.2f}")
    
    async def _start_strategies(self):
        """Start trading strategies"""
        logger.info("Starting trading strategies...")
        
        if self.settings.trading.dry_run:
            logger.warning("Running in DRY RUN mode - no real wagers will be placed")
        
        # Start the strategy
        await self.strategy.start()
        
        logger.info("Trading strategies started")
    
    def _start_scheduler(self):
        """Start the task scheduler"""
        logger.info("Starting task scheduler...")
        
        # Schedule regular tasks
        schedule.every(self.settings.strategy.quote_refresh_seconds).seconds.do(
            self._schedule_quote_refresh
        )
        
        schedule.every(30).seconds.do(
            self._schedule_balance_check
        )
        
        schedule.every(60).seconds.do(
            self._schedule_stats_update
        )
        
        schedule.every(300).seconds.do(  # 5 minutes
            self._schedule_position_rebalance
        )
        
        # Note: Real-time market data comes from Prophet API WebSocket - no simulation needed
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(
            target=self._run_scheduler,
            daemon=True
        )
        self.scheduler_thread.start()
        
        logger.info("Task scheduler started")
    
    def _run_scheduler(self):
        """Run the scheduler in a separate thread"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)
    
    def _schedule_quote_refresh(self):
        """Scheduled task to refresh quotes"""
        if self.is_running and self.strategy:
            asyncio.create_task(self.strategy.refresh_quotes())
    
    def _schedule_balance_check(self):
        """Scheduled task to check balance"""
        if self.is_running and self.prophet_api:
            asyncio.create_task(self._update_balance())
    
    def _schedule_stats_update(self):
        """Scheduled task to update statistics"""
        if self.is_running:
            asyncio.create_task(self._update_stats())
    
    def _schedule_position_rebalance(self):
        """Scheduled task to rebalance positions"""
        if self.is_running and self.strategy:
            asyncio.create_task(self.strategy.rebalance_positions())
    
    
    async def _update_balance(self):
        """Update current balance"""
        try:
            balance = await self.prophet_api.get_balance()
            self.stats.current_balance = balance.balance
        except Exception as e:
            logger.error(f"Error updating balance: {e}")
    
    async def _update_stats(self):
        """Update platform statistics"""
        try:
            self.stats.uptime_seconds = time.time() - self.stats.start_time
            self.stats.active_positions = len(self.current_positions)
            
            # Log periodic stats
            if int(self.stats.uptime_seconds) % 300 == 0:  # Every 5 minutes
                logger.info(f"Platform Stats: {self._get_stats_summary()}")
                
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
    
    def _get_stats_summary(self) -> str:
        """Get formatted stats summary"""
        return (
            f"Uptime: {self.stats.uptime_seconds/3600:.1f}h, "
            f"Balance: ${self.stats.current_balance:.2f}, "
            f"Wagers: {self.stats.total_wagers_placed} placed, "
            f"{self.stats.total_wagers_cancelled} cancelled, "
            f"{self.stats.total_matched_wagers} matched"
        )
    
    async def _on_market_data_update(self, data: Any):
        """Handle market data updates"""
        try:
            # Process market data update
            if self.market_data_manager:
                await self.market_data_manager.process_update(data)
            
            # Notify strategy of market data change
            if self.strategy:
                await self.strategy.on_market_data_update(data)
                
        except Exception as e:
            logger.error(f"Error processing market data update: {e}")
    
    async def _on_wager_update(self, data: Any):
        """Handle wager status updates"""
        try:
            # Process wager update
            if self.wager_manager:
                await self.wager_manager.process_update(data)
            
            # Update stats based on wager status
            # This would parse the actual wager update format
            # For now, we'll increment counters
            
        except Exception as e:
            logger.error(f"Error processing wager update: {e}")
    
    async def _on_balance_update(self, data: Any):
        """Handle balance updates"""
        try:
            # Update balance from real-time feed
            logger.info(f"Balance update: {data}")
            
        except Exception as e:
            logger.error(f"Error processing balance update: {e}")
    
    async def place_manual_wager(self, line_id: int, odds: int, stake: float) -> Optional[int]:
        """Place a manual wager (for testing or manual intervention)"""
        try:
            if self.settings.trading.dry_run:
                logger.info(f"DRY RUN: Would place wager - Line: {line_id}, Odds: {odds}, Stake: ${stake}")
                return None
            
            # Create and place wager
            wager = self.prophet_api.create_wager(line_id, odds, stake)
            wager_id = await self.prophet_api.place_wager(wager)
            
            if wager_id:
                self.stats.total_wagers_placed += 1
                logger.info(f"Manual wager placed: {wager_id}")
            
            return wager_id
            
        except Exception as e:
            logger.error(f"Error placing manual wager: {e}")
            return None
    
    async def cancel_manual_wager(self, external_id: str) -> bool:
        """Cancel a manual wager"""
        try:
            if self.settings.trading.dry_run:
                logger.info(f"DRY RUN: Would cancel wager {external_id}")
                return True
            
            success = await self.prophet_api.cancel_wager(external_id)
            
            if success:
                self.stats.total_wagers_cancelled += 1
                logger.info(f"Manual wager cancelled: {external_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error cancelling manual wager: {e}")
            return False
    
    def get_platform_status(self) -> Dict[str, Any]:
        """Get current platform status"""
        return {
            'is_running': self.is_running,
            'uptime_seconds': time.time() - self.stats.start_time,
            'dry_run': self.settings.trading.dry_run,
            'active_tournaments': len(self.active_tournaments),
            'active_events': len(self.active_events),
            'current_balance': self.stats.current_balance,
            'total_wagers_placed': self.stats.total_wagers_placed,
            'total_wagers_cancelled': self.stats.total_wagers_cancelled,
            'total_matched_wagers': self.stats.total_matched_wagers,
            'api_connected': self.prophet_api.is_connected if self.prophet_api else False
        }
    
    def get_active_events(self) -> List[Dict[str, Any]]:
        """Get list of active events"""
        events = []
        for event_id, event in self.active_events.items():
            events.append({
                'event_id': event.event_id,
                'name': event.name,
                'tournament_id': event.tournament_id,
                'start_time': event.start_time,
                'markets_count': len(event.markets)
            })
        return events
    
    async def emergency_stop(self):
        """Emergency stop - cancel all wagers and stop immediately"""
        logger.warning("EMERGENCY STOP INITIATED")
        
        try:
            # Cancel all wagers immediately
            if self.prophet_api and not self.settings.trading.dry_run:
                await self.prophet_api.cancel_all_wagers()
            
            # Stop the platform
            await self.stop()
            
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
        
        logger.warning("EMERGENCY STOP COMPLETED")
    
    async def _run_periodic_tasks(self):
        """Run periodic tasks in the async event loop"""
        logger.info("Starting periodic tasks for balance updates only")
        
        # Track last execution time
        last_balance_update = 0
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # Balance update every 30 seconds
                if current_time - last_balance_update >= 30:
                    if self.prophet_api:
                        try:
                            balance = await self.prophet_api.get_balance()
                            self.stats.current_balance = balance.balance
                        except:
                            pass  # Ignore balance update errors
                    last_balance_update = current_time
                
                # Sleep for 5 seconds before next iteration
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in periodic tasks: {e}")
                await asyncio.sleep(5)
