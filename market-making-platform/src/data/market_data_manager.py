"""
Market Data Manager
Handles market data processing and storage with real-time order book support
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import deque, defaultdict

from loguru import logger
from src.exchanges.prophet_sports_api import ProphetSportsAPI


@dataclass
class OrderBookLevel:
    """Single order book level (price and size)"""
    price: float
    size: float
    odds: int  # American odds format for sports betting
    timestamp: float = field(default_factory=time.time)


@dataclass
class SelectionLevel:
    """Order book level for a specific selection (team, over/under, etc.)"""
    selection_id: int
    selection_name: str  # Team name, "Over 8.5", "Under 8.5", etc.
    odds: int  # American odds format
    size: float  # Available stake
    timestamp: float = field(default_factory=time.time)

@dataclass
class OrderBook:
    """Order book for a market showing available selections"""
    event_id: int
    market_id: str
    market_type: str  # 'moneyline', 'spread', 'total'
    event_name: str
    selections: Dict[int, SelectionLevel] = field(default_factory=dict)  # selection_id -> SelectionLevel
    line_groups: Dict[str, Dict[str, List[SelectionLevel]]] = field(default_factory=dict)  # line_value -> {selection_name -> [levels]}
    available_lines: List[str] = field(default_factory=list)  # List of available line values
    last_update: float = field(default_factory=time.time)
    best_selection: Optional[SelectionLevel] = None  # Most favorable odds
    spread: float = 0.0
    total_volume: float = 0.0


@dataclass
class MarketDataSnapshot:
    """Market data snapshot"""
    timestamp: float
    event_id: int
    market_type: str
    data: Dict[str, Any]
    order_book: Optional[OrderBook] = None


class MarketDataManager:
    """
    Manages market data feeds and processing with real-time order book support
    """
    
    def __init__(self, api: ProphetSportsAPI):
        self.api = api
        
        # Order book storage
        self.order_books: Dict[str, OrderBook] = {}  # market_id -> OrderBook
        self.event_order_books: Dict[int, List[OrderBook]] = defaultdict(list)  # event_id -> [OrderBooks]
        
        # Market data storage
        self.current_data: Dict[int, Dict[str, Any]] = {}  # event_id -> market_data
        self.data_history: deque = deque(maxlen=1000)  # Recent data snapshots
        
        # Statistics
        self.total_updates = 0
        self.last_update_time = 0.0
        
        # WebSocket subscribers for real-time updates
        self.subscribers: List[Callable] = []
        
        logger.info("Market Data Manager initialized with order book support")
    
    def subscribe_to_updates(self, callback: Callable):
        """Subscribe to real-time market data updates"""
        self.subscribers.append(callback)
    
    def unsubscribe_from_updates(self, callback: Callable):
        """Unsubscribe from real-time updates"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    async def _notify_subscribers(self, update_type: str, data: Any):
        """Notify all subscribers of market data updates"""
        for callback in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update_type, data)
                else:
                    callback(update_type, data)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")
    
    async def process_update(self, update_data: Any):
        """Process incoming market data update from Prophet WebSocket"""
        try:
            self.total_updates += 1
            self.last_update_time = time.time()
            
            logger.debug(f"Processing Prophet market data update: {type(update_data)}")
            
            # Handle different update data formats
            if isinstance(update_data, dict):
                parsed_data = update_data
            else:
                parsed_data = self._parse_market_update(update_data)
            
            if not parsed_data:
                return
                
            # Extract metadata and determine update type
            meta = parsed_data.get('_meta', {})
            change_type = meta.get('change_type', 'unknown')
            
            # Extract relevant IDs - they can be at root level or inside 'info'
            info = parsed_data.get('info', {})
            event_id = (
                parsed_data.get('sport_event_id') or 
                parsed_data.get('event_id') or 
                info.get('sport_event_id') or 
                info.get('event_id')
            )
            market_id = (
                parsed_data.get('market_id') or 
                info.get('market_id')
            )
            
            # Convert to integers if they're strings
            try:
                if event_id is not None:
                    event_id = int(event_id)
                if market_id is not None:
                    market_id = int(market_id)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert event_id ({event_id}) or market_id ({market_id}) to integers")
            
            logger.debug(f"Processing [{change_type}] update for event {event_id}, market {market_id}")
            
            # Process different change types from Prophet API
            if change_type in ['selections', 'market_selections']:
                await self._process_selection_update(parsed_data, event_id, market_id)
            elif change_type in ['matched_bet']:
                await self._process_trade_update(parsed_data, event_id, market_id)
            elif change_type in ['market_line']:
                await self._process_market_line_update(parsed_data, event_id, market_id)
            else:
                # Generic update - try to extract event info and refresh
                if event_id:
                    await self._process_generic_update(parsed_data, event_id, market_id)
                else:
                    # Raw data or unknown format
                    await self._notify_subscribers('market_data_update', parsed_data)
            
        except Exception as e:
            logger.error(f"Error processing market data update: {e}")
    
    def _parse_market_update(self, update_data: Any) -> Optional[Dict[str, Any]]:
        """Parse raw market data update into structured format"""
        try:
            # This would parse the actual Prophet API format
            # For now, we'll create a mock structure based on what we know
            if isinstance(update_data, str):
                try:
                    data = json.loads(update_data)
                except:
                    return None
            else:
                data = update_data
            
            # Mock parsing - replace with actual Prophet API format
            return {
                'event_id': data.get('event_id', 0),
                'market_type': data.get('market_type', 'unknown'),
                'timestamp': time.time(),
                'raw_data': data
            }
            
        except Exception as e:
            logger.error(f"Error parsing market update: {e}")
            return None
    
    async def _update_order_books(self, market_data: Dict[str, Any]):
        """Update order books from market data"""
        try:
            event_id = market_data.get('event_id')
            if not event_id:
                return
            
            # Get event information
            event = self.api.sport_events.get(event_id)
            if not event:
                return
            
            # Process each market for this event
            for market in event.markets:
                market_id = f"{event_id}_{market.get('id', 'unknown')}"
                market_type = market.get('type', 'unknown')
                
                # Create or update order book
                order_book = self.order_books.get(market_id)
                if not order_book:
                    order_book = OrderBook(
                        event_id=event_id,
                        market_id=market_id,
                        market_type=market_type,
                        event_name=event.name
                    )
                    self.order_books[market_id] = order_book
                    self.event_order_books[event_id].append(order_book)
                
                # Update order book with market data
                await self._process_market_selections(order_book, market)
                
                # Calculate spread and mid-price
                self._calculate_order_book_metrics(order_book)
                
                # Notify subscribers of order book update
                await self._notify_subscribers('order_book_update', {
                    'order_book': order_book,
                    'event_id': event_id,
                    'market_id': market_id
                })
                
        except Exception as e:
            logger.error(f"Error updating order books: {e}")
    
    async def _process_market_selections(self, order_book: OrderBook, market: Dict[str, Any]):
        """Process market selections and update order book levels using real Prophet API data"""
        try:
            order_book.selections.clear()
            
            # Handle different market structures
            if 'selections' in market and market['selections']:
                # Direct selections (e.g., Moneyline markets)
                await self._process_direct_selections(order_book, market['selections'])
            elif 'market_lines' in market and market['market_lines']:
                # Market lines with selections (e.g., Spread/Total markets) 
                await self._process_market_lines(order_book, market['market_lines'])
            
            order_book.last_update = time.time()
            
        except Exception as e:
            logger.error(f"Error processing market selections: {e}")
    
    async def _process_direct_selections(self, order_book: OrderBook, selections: List):
        """Process direct selections (e.g., moneyline)"""
        # Flatten all selections into a single list for processing
        all_selections = []
        for selection_group in selections:
            if isinstance(selection_group, list):
                all_selections.extend(selection_group)
            else:
                all_selections.append(selection_group)
        
        # Group by selection name to find best odds
        best_selections = {}
        
        for selection in all_selections:
            name = selection.get('name', '')
            odds = selection.get('odds')
            # Use 'value' field instead of deprecated 'stake' field
            value = selection.get('value', 0)
            line_id = selection.get('line_id', '')
            outcome_id = selection.get('outcome_id', 0)
            
            # Include all selections with names
            if name:
                # For null odds, show 0 liquidity; otherwise use actual value
                display_value = 0.0 if odds is None else (value if value > 0 else 1.0)
                
                # Keep the best odds for each selection (better price for bettors)
                if name not in best_selections:
                    best_selections[name] = {
                        'name': name,
                        'odds': odds,  # Keep original odds (including None)
                        'value': display_value,
                        'original_value': value,
                        'line_id': line_id,
                        'outcome_id': outcome_id or hash(name) % 10000  # Generate ID if missing
                    }
                elif self._is_better_odds(odds, best_selections[name]['odds']):
                    # Update with better odds
                    new_display_value = 0.0 if odds is None else (value if value > 0 else 1.0)
                    best_selections[name].update({
                        'odds': odds,
                        'value': max(new_display_value, best_selections[name]['value']),
                        'line_id': line_id,
                        'outcome_id': outcome_id or best_selections[name]['outcome_id']
                    })
        
        # Create selection levels from best selections
        for name, sel_data in best_selections.items():
            selection_level = SelectionLevel(
                selection_id=sel_data['outcome_id'],
                selection_name=name,
                odds=sel_data['odds'],
                size=sel_data['value'],
                timestamp=time.time()
            )
            order_book.selections[sel_data['outcome_id']] = selection_level
    
    async def _process_market_lines(self, order_book: OrderBook, market_lines: List):
        """Process market lines (e.g., spread, totals)"""
        if not market_lines:
            return
            
        # Clear existing data
        order_book.line_groups.clear()
        order_book.available_lines.clear()
        
        # Process ALL market lines to get complete market depth (not just primary line)
        # Debug logging for total and spread markets
        if 'total' in order_book.market_type.lower() or 'spread' in order_book.market_type.lower():
            logger.debug(f"Processing {order_book.market_type} market {order_book.market_id}:")
            logger.debug(f"Raw market_lines data: {market_lines}")
        
        # Process each line separately to maintain line grouping
        for line in market_lines:
            line_value = str(line.get('line', 'N/A'))  # Convert to string for consistency
            selections = line.get('selections', [])
            
            if 'total' in order_book.market_type.lower() or 'spread' in order_book.market_type.lower():
                logger.debug(f"Processing line {line_value} selections: {len(selections)} groups")
            
            # Initialize line group if not exists
            if line_value not in order_book.line_groups:
                order_book.line_groups[line_value] = {}
                order_book.available_lines.append(line_value)
            
            # Process selections for this specific line
            line_selections = []
            for selection_group in selections:
                if isinstance(selection_group, list):
                    line_selections.extend(selection_group)
                else:
                    line_selections.append(selection_group)
            
            # Group selections by name for this line
            selections_by_name = {}
            for selection in line_selections:
                name = selection.get('name', '')
                odds = selection.get('odds')
                value = selection.get('value', 0)
                line_id = selection.get('line_id', '')
                outcome_id = selection.get('outcome_id', 0)
                
                if 'total' in order_book.market_type.lower() and odds is not None:
                    logger.debug(f"Processing selection: {name}, raw odds: {odds}, value: {value}")
                
                if name:
                    display_value = 0.0 if odds is None else (value if value > 0 else 1.0)
                    
                    # Create unique ID for each odds level within this line
                    unique_id = f"{outcome_id}_{line_value}_{odds}_{value}"[:20]
                    unique_selection_id = hash(unique_id) % 100000
                    
                    # Group by selection name within this line
                    if name not in selections_by_name:
                        selections_by_name[name] = []
                    
                    selections_by_name[name].append({
                        'name': name,
                        'odds': odds,
                        'value': display_value,
                        'original_value': value,
                        'line_id': line_id,
                        'outcome_id': outcome_id,
                        'unique_id': unique_selection_id,
                        'line_value': line_value
                    })
            
            # Create SelectionLevels for this line and add to both line_groups and main selections
            for name, selection_levels in selections_by_name.items():
                # Sort by odds within each line
                if selection_levels and selection_levels[0]['odds'] is not None:
                    selection_levels.sort(key=lambda x: x['odds'] if x['odds'] is not None else float('inf'), reverse=True)
                
                # Initialize selection list for this name in this line
                if name not in order_book.line_groups[line_value]:
                    order_book.line_groups[line_value][name] = []
                
                for level_data in selection_levels:
                    selection_level = SelectionLevel(
                        selection_id=level_data['unique_id'],
                        selection_name=name,
                        odds=level_data['odds'],
                        size=level_data['value'],
                        timestamp=time.time()
                    )
                    
                    # Add to line group
                    order_book.line_groups[line_value][name].append(selection_level)
                    
                    # Also add to main selections for backward compatibility
                    order_book.selections[level_data['unique_id']] = selection_level
                    
                    if 'total' in order_book.market_type.lower() and level_data['odds'] is not None:
                        logger.debug(f"Created SelectionLevel for line {line_value}: {name}, odds: {selection_level.odds}, size: {selection_level.size}")
        
        # Sort available lines for consistent display (numeric sorting for spread/total lines)
        try:
            order_book.available_lines.sort(key=lambda x: float(x) if x != 'N/A' else float('inf'))
        except ValueError:
            # If lines aren't numeric, sort alphabetically
            order_book.available_lines.sort()
    
    def _calculate_order_book_metrics(self, order_book: OrderBook):
        """Calculate order book metrics like spread and volume"""
        try:
            if not order_book.selections:
                order_book.best_selection = None
                order_book.spread = 0.0
                order_book.total_volume = 0.0
                return
            
            selections = list(order_book.selections.values())
            
            # No "best selection" concept - each selection has independent odds
            # Just pick the first selection for dashboard compatibility
            order_book.best_selection = selections[0] if selections else None
            
            # Calculate spread (difference between highest and lowest odds) for markets with multiple selections
            valid_odds_selections = [sel for sel in selections if sel.odds is not None]
            if len(valid_odds_selections) >= 2:
                odds_values = [sel.odds for sel in valid_odds_selections]
                order_book.spread = max(odds_values) - min(odds_values)
            else:
                order_book.spread = 0.0
            
            # Calculate total volume across all selections
            order_book.total_volume = sum(sel.size for sel in selections)
                
        except Exception as e:
            logger.error(f"Error calculating order book metrics: {e}")
    
    def get_order_book(self, market_id: str) -> Optional[OrderBook]:
        """Get order book for a specific market"""
        return self.order_books.get(market_id)
    
    def get_event_order_books(self, event_id: int) -> List[OrderBook]:
        """Get all order books for an event"""
        return self.event_order_books.get(event_id, [])
    
    def get_all_order_books(self) -> Dict[str, OrderBook]:
        """Get all order books"""
        return self.order_books.copy()
    
    def get_current_data(self, event_id: int) -> Optional[Dict[str, Any]]:
        """Get current market data for an event"""
        return self.current_data.get(event_id)
    
    def _is_better_odds(self, new_odds: Optional[int], current_odds: Optional[int]) -> bool:
        """Determine if new odds are better than current odds for American odds format"""
        # Handle None values
        if new_odds is None and current_odds is None:
            return False
        if new_odds is None:
            return False  # Keep current over None
        if current_odds is None:
            return True   # New odds are better than None
        
        # For American odds (better odds = more favorable to the bettor):
        # Positive odds: higher is better (+200 better than +150)
        # Negative odds: closer to 0 is better (-110 better than -150)
        # Positive odds are generally better than negative odds at similar probability levels
        
        if new_odds > 0 and current_odds > 0:
            # Both positive: higher value is better for bettors
            return new_odds > current_odds
        elif new_odds < 0 and current_odds < 0:
            # Both negative: closer to 0 is better for bettors (lower absolute value)
            return abs(new_odds) < abs(current_odds)
        elif new_odds > 0 and current_odds < 0:
            # New is positive, current is negative: positive is almost always better
            return True
        elif new_odds < 0 and current_odds > 0:
            # New is negative, current is positive: positive is almost always better
            return False
        else:
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get market data statistics"""
        return {
            'total_updates': self.total_updates,
            'last_update_time': self.last_update_time,
            'events_tracked': len(self.current_data),
            'order_books': len(self.order_books),
            'history_size': len(self.data_history),
            'subscribers': len(self.subscribers)
        }
    
    async def initialize_order_books(self):
        """Initialize order books for all available events"""
        try:
            logger.info("Initializing order books for all events...")
            
            for event_id, event in self.api.sport_events.items():
                # Group markets by type to avoid duplicates
                processed_market_types = set()
                
                for market in event.markets:
                    market_type = market.get('name', 'unknown').lower()
                    
                    # Only process each market type once per event
                    if market_type not in processed_market_types:
                        processed_market_types.add(market_type)
                        
                        market_id = f"{event_id}_{market_type}_{market.get('id', 'unknown')}"
                        
                        order_book = OrderBook(
                            event_id=event_id,
                            market_id=market_id,
                            market_type=market_type,
                            event_name=event.name
                        )
                        
                        # Process initial market data with real Prophet API data
                        await self._process_market_selections(order_book, market)
                        self._calculate_order_book_metrics(order_book)
                        
                        # Always add order books, even if empty (to show 0 liquidity)
                        self.order_books[market_id] = order_book
                        self.event_order_books[event_id].append(order_book)
            
            logger.info(f"Initialized {len(self.order_books)} order books for {len(self.event_order_books)} events")
            
        except Exception as e:
            logger.error(f"Error initializing order books: {e}")
    
    async def _refresh_event_order_books(self, event_id: int):
        """Refresh order books for a specific event with latest API data"""
        try:
            event = self.api.sport_events.get(event_id)
            if not event:
                logger.warning(f"Event {event_id} not found for refresh")
                return
            
            logger.debug(f"Refreshing order books for event {event_id}: {event.name}")
            
            # Update each existing order book for this event
            existing_order_books = self.event_order_books.get(event_id, [])
            
            for order_book in existing_order_books:
                # Find the corresponding market data
                market_found = False
                for market in event.markets:
                    market_type = market.get('name', 'unknown').lower()
                    if market_type in order_book.market_id:
                        # Update this order book with fresh market data
                        await self._process_market_selections(order_book, market)
                        self._calculate_order_book_metrics(order_book)
                        market_found = True
                        
                        # Notify subscribers of the order book update
                        await self._notify_subscribers('order_book_update', {
                            'order_book': order_book,
                            'event_id': event_id,
                            'market_id': order_book.market_id
                        })
                        break
                
                if not market_found:
                    logger.warning(f"Market not found for order book {order_book.market_id}")
            
            logger.debug(f"Refreshed {len(existing_order_books)} order books for event {event_id}")
            
        except Exception as e:
            logger.error(f"Error refreshing order books for event {event_id}: {e}")
    
    async def _process_selection_update(self, data: Dict[str, Any], event_id: int, market_id: int):
        """Process selection updates (odds changes, stake changes)"""
        try:
            if not event_id or not market_id:
                logger.warning(f"Missing event_id ({event_id}) or market_id ({market_id}) in selection update")
                return
            
            # Update current data
            if event_id not in self.current_data:
                self.current_data[event_id] = {}
            self.current_data[event_id]['selections'] = data
            
            # Refresh order books for this event to pick up the changes
            await self._refresh_event_order_books(event_id)
            
            # Store historical snapshot
            snapshot = MarketDataSnapshot(
                timestamp=time.time(),
                event_id=event_id,
                market_type='selection_update',
                data=data
            )
            self.data_history.append(snapshot)
            
            # Notify subscribers
            await self._notify_subscribers('selection_update', {
                'event_id': event_id,
                'market_id': market_id,
                'data': data
            })
            
            logger.debug(f"Processed selection update for event {event_id}, market {market_id}")
            
        except Exception as e:
            logger.error(f"Error processing selection update: {e}")
    
    async def _process_trade_update(self, data: Dict[str, Any], event_id: int, market_id: int):
        """Process matched bet/trade events"""
        try:
            if not event_id or not market_id:
                logger.warning(f"Missing event_id ({event_id}) or market_id ({market_id}) in trade update")
                return
            
            # Extract trade info
            info = data.get('info', {})
            matched_stake = info.get('matched_stake', 0)
            matched_odds = info.get('matched_odds', 0)
            line = info.get('line', 'N/A')
            
            # Update current data
            if event_id not in self.current_data:
                self.current_data[event_id] = {}
            if 'trades' not in self.current_data[event_id]:
                self.current_data[event_id]['trades'] = []
            
            # Add trade to history
            trade_data = {
                'timestamp': time.time(),
                'market_id': market_id,
                'line': line,
                'odds': matched_odds,
                'stake': matched_stake,
                'info': info
            }
            self.current_data[event_id]['trades'].append(trade_data)
            
            # Keep only recent trades (last 50)
            if len(self.current_data[event_id]['trades']) > 50:
                self.current_data[event_id]['trades'] = self.current_data[event_id]['trades'][-50:]
            
            # Refresh order books since liquidity may have changed
            await self._refresh_event_order_books(event_id)
            
            # Notify subscribers
            await self._notify_subscribers('trade_update', {
                'event_id': event_id,
                'market_id': market_id,
                'trade': trade_data
            })
            
            logger.debug(f"Processed trade update for event {event_id}, market {market_id}: {matched_stake}@{matched_odds}")
            
        except Exception as e:
            logger.error(f"Error processing trade update: {e}")
    
    async def _process_market_line_update(self, data: Dict[str, Any], event_id: int, market_id: int):
        """Process new market lines or line status changes"""
        try:
            if not event_id or not market_id:
                logger.warning(f"Missing event_id ({event_id}) or market_id ({market_id}) in market line update")
                return
            
            # Extract line info
            info = data.get('info', {})
            line = info.get('line', 'N/A')
            line_id = info.get('line_id', '')
            status = info.get('status', 'unknown')
            
            # Update current data
            if event_id not in self.current_data:
                self.current_data[event_id] = {}
            if 'market_lines' not in self.current_data[event_id]:
                self.current_data[event_id]['market_lines'] = {}
            
            # Update market line data
            self.current_data[event_id]['market_lines'][str(market_id)] = {
                'line': line,
                'line_id': line_id,
                'status': status,
                'timestamp': time.time(),
                'info': info
            }
            
            # Refresh order books for this event
            await self._refresh_event_order_books(event_id)
            
            # Store historical snapshot
            snapshot = MarketDataSnapshot(
                timestamp=time.time(),
                event_id=event_id,
                market_type='market_line_update',
                data=data
            )
            self.data_history.append(snapshot)
            
            # Notify subscribers
            await self._notify_subscribers('market_line_update', {
                'event_id': event_id,
                'market_id': market_id,
                'line': line,
                'status': status,
                'data': data
            })
            
            logger.debug(f"Processed market line update for event {event_id}, market {market_id}: line {line} ({status})")
            
        except Exception as e:
            logger.error(f"Error processing market line update: {e}")
    
    async def _process_generic_update(self, data: Dict[str, Any], event_id: int, market_id: Optional[int]):
        """Process generic updates that don't fit specific categories"""
        try:
            # Update current data
            if event_id not in self.current_data:
                self.current_data[event_id] = {}
            self.current_data[event_id]['last_generic_update'] = {
                'timestamp': time.time(),
                'data': data
            }
            
            # Refresh order books for this event
            await self._refresh_event_order_books(event_id)
            
            # Notify subscribers
            await self._notify_subscribers('market_data_update', {
                'event_id': event_id,
                'market_id': market_id,
                'data': data
            })
            
            logger.debug(f"Processed generic update for event {event_id}, market {market_id}")
            
        except Exception as e:
            logger.error(f"Error processing generic update: {e}")


def random_size() -> float:
    """Generate random order size for mock data"""
    import random
    return round(random.uniform(10.0, 1000.0), 2)
