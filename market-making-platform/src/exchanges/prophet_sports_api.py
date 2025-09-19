"""
Prophet Sports Betting API Client
Based on the actual Prophet API structure from ProphetApiTest repository
"""

import asyncio
import json
import time
import uuid
import base64
import random
from contextlib import suppress
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin

import requests
import pysher
from loguru import logger


class WagerSide(Enum):
    """Wager side for sports betting - now represents the selection being bet on"""
    SELECTION = "selection"  # betting on a specific selection (team, over/under, etc.)


class WagerStatus(Enum):
    """Wager status"""
    PENDING = "pending"
    OPEN = "open"
    MATCHED = "matched"
    CANCELLED = "cancelled"
    SETTLED = "settled"


@dataclass
class Tournament:
    """Tournament data structure"""
    id: int
    name: str
    sport: str


@dataclass 
class SportEvent:
    """Sport event data structure"""
    event_id: int
    name: str
    tournament_id: int
    start_time: str
    markets: List[Dict] = field(default_factory=list)


@dataclass
class Market:
    """Market data structure"""
    market_id: int
    event_id: int
    market_type: str  # e.g., 'moneyline', 'spread', 'total'
    selections: List[Dict] = field(default_factory=list)


@dataclass
class Wager:
    """Wager data structure"""
    external_id: str
    line_id: int
    odds: int  # American odds format
    stake: float
    selection_id: int = 0  # The specific selection being bet on
    selection_name: str = ""  # Name of the selection (team name, over/under, etc.)
    status: WagerStatus = WagerStatus.PENDING
    wager_id: Optional[int] = None
    filled_stake: float = 0.0
    timestamp: Optional[float] = None


@dataclass
class Balance:
    """Account balance structure"""
    balance: float
    currency: str = "USD"


class ProphetSportsAPI:
    """
    Prophet Sports Betting API Client
    Built from the actual Prophet API structure
    """
    
    def __init__(self, access_key: str, secret_key: str, base_url: str = "https://api-ss-sandbox.betprophet.co"):
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = base_url
        
        # API endpoints
        self.urls = {
            'mm_login': 'partner/auth/login',
            'mm_refresh': 'partner/auth/refresh',
            'mm_ping': 'partner/mm/pusher/ping',
            'mm_auth': 'partner/mm/pusher',
            'mm_tournaments': 'partner/mm/get_tournaments',
            'mm_events': 'partner/mm/get_sport_events',
            'mm_markets': 'partner/mm/get_markets',
            'mm_multiple_markets': 'partner/mm/get_multiple_markets',
            'mm_balance': 'partner/mm/get_balance',
            'mm_place_wager': 'partner/mm/place_wager',
            'mm_cancel_wager': 'partner/mm/cancel_wager',
            'mm_odds_ladder': 'partner/mm/get_odds_ladder',
            'mm_batch_cancel': 'partner/mm/cancel_multiple_wagers',
            'mm_batch_place': 'partner/mm/place_multiple_wagers',
            'mm_cancel_all_wagers': 'partner/mm/cancel_all_wagers',
            'websocket_config': 'partner/websocket/connection-config',
        }
        
        # Session and state
        self.mm_session: Dict = {}
        self.balance: float = 0.0
        self.all_tournaments: List[Tournament] = []
        self.my_tournaments: Dict[int, Tournament] = {}
        self.sport_events: Dict[int, SportEvent] = {}
        self.wagers: Dict[str, int] = {}  # external_id -> wager_id mapping
        self.valid_odds: List[int] = []
        self.pusher = None
        self.is_connected = False
        
        # Event loop reference for WebSocket callbacks
        self.event_loop = None
        self._token_refresh_task: Optional[asyncio.Task] = None
        self._token_refresh_interval = 8 * 60  # seconds
        
        # Tournaments interested in
        self.tournaments_interested = ["MLB", "NBA", "NFL", "NHL"]  # Default sports
        
        # Callbacks
        self.callbacks: Dict[str, List[Callable]] = {
            'market_data': [],
            'wager_update': [],
            'settlement': [],
            'balance_update': []
        }
        
    async def login(self) -> bool:
        """Login to Prophet API and establish session"""
        try:
            # Store reference to current event loop for WebSocket callbacks
            self.event_loop = asyncio.get_running_loop()

            login_url = urljoin(self.base_url, self.urls['mm_login'])
            request_body = {
                'access_key': self.access_key,
                'secret_key': self.secret_key,
            }

            response = await self._async_request(
                "POST",
                login_url,
                data=json.dumps(request_body),
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code != 200:
                logger.error(f"Login failed: {response.status_code} - {response.text}")
                return False
                
            self.mm_session = response.json()['data']
            logger.info("Successfully logged into Prophet API")
            self.is_connected = True
            
            # Schedule token refresh
            self._schedule_token_refresh()
            
            return True
            
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False
    
    def _schedule_token_refresh(self):
        """Schedule automatic token refresh on the event loop"""
        if self._token_refresh_task and not self._token_refresh_task.done():
            return

        loop = asyncio.get_running_loop()
        self._token_refresh_task = loop.create_task(self._run_token_refresh())

    async def _run_token_refresh(self):
        """Background task that refreshes the token periodically"""
        try:
            while self.is_connected:
                try:
                    await asyncio.sleep(self._token_refresh_interval)
                except asyncio.CancelledError:
                    raise

                if not self.is_connected:
                    break

                await self._refresh_token()
        except asyncio.CancelledError:
            logger.debug("Token refresh task cancelled")
            raise

    async def _refresh_token(self):
        """Refresh the access token"""
        try:
            refresh_url = urljoin(self.base_url, self.urls['mm_refresh'])
            response = await self._async_request(
                "POST",
                refresh_url,
                json={'refresh_token': self.mm_session['refresh_token']},
                headers=self._get_auth_headers()
            )

            if response.status_code == 200:
                self.mm_session['access_token'] = response.json()['data']['access_token']
                logger.info("Access token refreshed successfully")

                # Reconnect pusher with new token
                if self.pusher:
                    self.pusher.disconnect()
                    self.pusher = None
                    await self._start_websocket_connection()
            else:
                logger.error("Failed to refresh access token")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
    
    async def initialize_data(self):
        """Initialize tournaments, events, and market data"""
        try:
            # Get valid odds ladder
            await self._load_odds_ladder()
            
            # Load tournaments
            await self._load_tournaments()
            
            # Load events and markets for interested tournaments
            await self._load_events_and_markets()
            
            logger.info(f"Initialized {len(self.my_tournaments)} tournaments with {len(self.sport_events)} events")
            
            # Start WebSocket connection after data is loaded
            await self._start_websocket_connection()
            
        except Exception as e:
            logger.error(f"Error initializing data: {e}")
            raise
    
    async def _load_odds_ladder(self):
        """Load valid odds ladder from API"""
        try:
            odds_url = urljoin(self.base_url, self.urls['mm_odds_ladder'])
            response = await self._async_request(
                "GET",
                odds_url,
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 200:
                self.valid_odds = response.json()['data']
                logger.info(f"Loaded {len(self.valid_odds)} valid odds levels")
            else:
                # Fallback to predefined odds
                self.valid_odds = self._get_default_odds()
                logger.warning("Using fallback odds ladder")
                
        except Exception as e:
            logger.error(f"Error loading odds ladder: {e}")
            self.valid_odds = self._get_default_odds()
    
    def _get_default_odds(self) -> List[int]:
        """Get default odds ladder"""
        return list(range(-200, -100, 5)) + list(range(100, 300, 5))
    
    async def _load_tournaments(self):
        """Load available tournaments"""
        try:
            tournaments_url = urljoin(self.base_url, self.urls['mm_tournaments'])
            response = await self._async_request(
                "GET",
                tournaments_url,
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 200:
                tournaments_data = response.json()['data']['tournaments']
                self.all_tournaments = [
                    Tournament(id=t['id'], name=t['name'], sport=t.get('sport', ''))
                    for t in tournaments_data
                ]
                
                # Filter tournaments we're interested in
                for tournament in self.all_tournaments:
                    if tournament.name in self.tournaments_interested:
                        self.my_tournaments[tournament.id] = tournament
                        
                logger.info(f"Loaded {len(self.my_tournaments)} relevant tournaments")
                
        except Exception as e:
            logger.error(f"Error loading tournaments: {e}")
    
    async def _load_events_and_markets(self):
        """Load events and markets for interested tournaments"""
        try:
            events_url = urljoin(self.base_url, self.urls['mm_events'])
            markets_url = urljoin(self.base_url, self.urls['mm_multiple_markets'])
            
            for tournament_id, tournament in self.my_tournaments.items():
                # Get events for this tournament
                events_response = await self._async_request(
                    "GET",
                    events_url,
                    params={'tournament_id': tournament_id},
                    headers=self._get_auth_headers()
                )
                
                if events_response.status_code == 200:
                    events_data = events_response.json()['data']['sport_events']
                    if not events_data:
                        continue
                    
                    # Get markets for all events in batch
                    event_ids = ','.join([str(event['event_id']) for event in events_data])
                    markets_response = await self._async_request(
                        "GET",
                        markets_url,
                        params={'event_ids': event_ids},
                        headers=self._get_auth_headers()
                    )
                    
                    if markets_response.status_code == 200:
                        markets_by_event = markets_response.json()['data']
                        
                        # Process each event
                        for event_data in events_data:
                            event_id = event_data['event_id']
                            markets = markets_by_event.get(str(event_id), [])
                            
                            sport_event = SportEvent(
                                event_id=event_id,
                                name=event_data['name'],
                                tournament_id=tournament_id,
                                start_time=event_data.get('start_time', ''),
                                markets=markets
                            )
                            
                            self.sport_events[event_id] = sport_event
                            
                logger.info(f"Loaded events for tournament {tournament.name}")
                            
        except Exception as e:
            logger.error(f"Error loading events and markets: {e}")
    
    async def get_balance(self) -> Balance:
        """Get account balance"""
        try:
            balance_url = urljoin(self.base_url, self.urls['mm_balance'])
            response = await self._async_request(
                "GET",
                balance_url,
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 200:
                balance_data = response.json()['data']
                self.balance = balance_data.get('balance', 0.0)
                return Balance(balance=self.balance)
            else:
                logger.error(f"Failed to get balance: {response.status_code}")
                return Balance(balance=0.0)
                
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return Balance(balance=0.0)
    
    async def place_wager(self, wager: Wager) -> Optional[int]:
        """Place a single wager"""
        try:
            place_url = urljoin(self.base_url, self.urls['mm_place_wager'])
            
            wager_data = {
                'external_id': wager.external_id,
                'line_id': wager.line_id,
                'odds': wager.odds,
                'stake': wager.stake
            }
            
            response = await self._async_request(
                "POST",
                place_url,
                json=wager_data,
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 200:
                result = response.json()['data']
                wager_id = result['wager']['id']
                self.wagers[wager.external_id] = wager_id
                logger.info(f"Placed wager {wager.external_id} with ID {wager_id}")
                return wager_id
            else:
                logger.error(f"Failed to place wager: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error placing wager: {e}")
            return None
    
    async def place_multiple_wagers(self, wagers: List[Wager]) -> List[int]:
        """Place multiple wagers in batch"""
        try:
            batch_url = urljoin(self.base_url, self.urls['mm_batch_place'])
            
            wagers_data = []
            for wager in wagers:
                wager_data = {
                    'external_id': wager.external_id,
                    'line_id': wager.line_id,
                    'odds': wager.odds,
                    'stake': wager.stake
                }
                wagers_data.append(wager_data)
            
            response = await self._async_request(
                "POST",
                batch_url,
                json={"data": wagers_data},
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 200:
                result = response.json()['data']
                successful_wagers = result.get('succeed_wagers', [])
                
                wager_ids = []
                for wager_result in successful_wagers:
                    external_id = wager_result['external_id']
                    wager_id = wager_result['id']
                    self.wagers[external_id] = wager_id
                    wager_ids.append(wager_id)
                
                logger.info(f"Placed {len(successful_wagers)} wagers successfully")
                return wager_ids
            else:
                logger.error(f"Failed to place batch wagers: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error placing batch wagers: {e}")
            return []
    
    async def cancel_wager(self, external_id: str) -> bool:
        """Cancel a single wager"""
        try:
            if external_id not in self.wagers:
                logger.error(f"Wager {external_id} not found")
                return False
            
            cancel_url = urljoin(self.base_url, self.urls['mm_cancel_wager'])
            wager_id = self.wagers[external_id]
            
            cancel_data = {
                'external_id': external_id,
                'wager_id': wager_id
            }
            
            response = await self._async_request(
                "POST",
                cancel_url,
                json=cancel_data,
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 200:
                self.wagers.pop(external_id, None)
                logger.info(f"Cancelled wager {external_id}")
                return True
            elif response.status_code == 404:
                # Already cancelled
                self.wagers.pop(external_id, None)
                logger.info(f"Wager {external_id} already cancelled")
                return True
            else:
                logger.error(f"Failed to cancel wager: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling wager: {e}")
            return False
    
    async def cancel_all_wagers(self) -> bool:
        """Cancel all open wagers"""
        try:
            cancel_all_url = urljoin(self.base_url, self.urls['mm_cancel_all_wagers'])
            
            response = await self._async_request(
                "POST",
                cancel_all_url,
                json={},
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 200:
                self.wagers.clear()
                logger.info("Cancelled all wagers successfully")
                return True
            elif response.status_code == 404:
                logger.info("No wagers to cancel")
                return True
            else:
                logger.error(f"Failed to cancel all wagers: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling all wagers: {e}")
            return False
    
    async def _start_websocket_connection(self):
        """Start WebSocket connection using Pusher"""
        try:
            # Get connection configuration
            config_response = await self._get_connection_config()
            if not config_response:
                logger.error("Failed to get WebSocket configuration")
                return
            
            key = config_response['key']
            cluster = config_response['cluster']
            
            # Setup Pusher authentication
            auth_endpoint_url = urljoin(self.base_url, self.urls['mm_auth'])
            # WORKAROUND: Don't include header-subscriptions to avoid 500 Internal Server Error
            # The API has a bug when processing tournament IDs in header-subscriptions
            auth_headers = {
                "Authorization": f"Bearer {self.mm_session['access_token']}"
            }
            
            # Initialize Pusher
            self.pusher = pysher.Pusher(
                key=key,
                cluster=cluster,
                auth_endpoint=auth_endpoint_url,
                auth_endpoint_headers=auth_headers
            )
            
            # Set up connection handler
            self.pusher.connection.bind('pusher:connection_established', self._on_websocket_connected)
            
            # Connect
            self.pusher.connect()
            logger.info("WebSocket connection initiated")
            
        except Exception as e:
            logger.error(f"Error starting WebSocket connection: {e}")
    
    async def _get_connection_config(self) -> Optional[dict]:
        """Get WebSocket connection configuration"""
        try:
            config_url = urljoin(self.base_url, self.urls['websocket_config'])
            response = await self._async_request(
                "GET",
                config_url,
                headers=self._get_auth_headers()
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get connection config: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting connection config: {e}")
            return None
    
    def _on_websocket_connected(self, data):
        """Handle WebSocket connection established"""
        try:
            socket_id = json.loads(data)['socket_id']
            channels = self._get_channels(socket_id)
            
            if not channels:
                logger.error("No channels available")
                return
            
            # Subscribe to channels
            for channel_info in channels:
                channel_name = channel_info['channel_name']
                channel = self.pusher.subscribe(channel_name)
                
                if 'broadcast' in channel_name:
                    # Public channel - subscribe to tournament events
                    for tournament_id in self.my_tournaments.keys():
                        event_name = f'tournament_{tournament_id}'
                        channel.bind(event_name, self._handle_public_event)
                        logger.info(f"Subscribed to public channel event: {event_name}")
                        
                else:
                    # Private channel - subscribe to all binding events
                    binding_events = channel_info.get('binding_events', [])
                    for event_info in binding_events:
                        event_name = event_info['name']
                        channel.bind(event_name, self._handle_private_event)
                        logger.info(f"Subscribed to private channel event: {event_name}")
            
        except Exception as e:
            logger.error(f"Error handling WebSocket connection: {e}")
    
    def _get_channels(self, socket_id: str) -> List[dict]:
        """Get available channels for WebSocket subscription"""
        try:
            auth_url = urljoin(self.base_url, self.urls['mm_auth'])
            
            # Use form-encoded headers for pusher auth
            # WORKAROUND: Don't include header-subscriptions to avoid 500 Internal Server Error
            headers = {
                'Authorization': f'Bearer {self.mm_session["access_token"]}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                auth_url,
                data={'socket_id': socket_id},
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully got channels: {len(result.get('data', {}).get('authorized_channel', []))} channels")
                return result['data']['authorized_channel']
            else:
                logger.error(f"Failed to get channels: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting channels: {e}")
            return []
    
    def _handle_public_event(self, *args, **kwargs):
        """Handle public WebSocket events (market data updates)"""
        try:
            if args and len(args) > 0:
                # Parse event data
                event_data = json.loads(args[0]) if isinstance(args[0], str) else args[0]
                payload = event_data.get('payload', '')
                change_type = event_data.get('change_type', 'unknown')
                timestamp = event_data.get('timestamp', time.time())
                
                if payload:
                    # Decode base64 payload as per ProphetX API spec
                    decoded_data = base64.b64decode(payload).decode('utf-8')
                    
                    try:
                        # Parse decoded JSON
                        market_update = json.loads(decoded_data)
                        
                        # Enhance market update with event metadata
                        market_update['_meta'] = {
                            'change_type': change_type,
                            'timestamp': timestamp,
                            'raw_event': event_data
                        }
                        
                        # Log market data update
                        logger.debug(f"Market data update [{change_type}]: {market_update}")
                        
                        # Process different change types from Prophet API
                        if change_type in ['selections', 'market_selections']:
                            # Selection/odds updates - these are live market changes
                            self._schedule_callback('market_data', market_update)
                        elif change_type in ['matched_bet']:
                            # Trade execution events - public market activity
                            self._schedule_callback('market_data', market_update)
                        elif change_type in ['market_line']:
                            # New market lines or line status changes
                            self._schedule_callback('market_data', market_update)
                        else:
                            # Generic market update for any other change types
                            self._schedule_callback('market_data', market_update)
                            
                    except json.JSONDecodeError:
                        # If payload is not JSON, treat as raw string update
                        logger.debug(f"Non-JSON market update: {decoded_data}")
                        self._schedule_callback('market_data', {
                            'raw_data': decoded_data,
                            '_meta': {
                                'change_type': change_type,
                                'timestamp': timestamp,
                                'raw_event': event_data
                            }
                        })
                    
        except Exception as e:
            logger.error(f"Error handling public event: {e}")
    
    def _handle_private_event(self, *args, **kwargs):
        """Handle private WebSocket events (wager updates, settlements, balance)"""
        try:
            if args and len(args) > 0:
                # Parse event data
                event_data = json.loads(args[0]) if isinstance(args[0], str) else args[0]
                payload = event_data.get('payload', '')
                
                if payload:
                    # Decode base64 payload as per ProphetX API spec
                    decoded_data = base64.b64decode(payload).decode('utf-8')
                    
                    try:
                        # Parse decoded JSON
                        private_update = json.loads(decoded_data)
                        
                        # Log private event
                        logger.debug(f"Private event: {private_update}")
                        
                        # Process different private event types based on ProphetX API
                        event_type = private_update.get('type', private_update.get('event_type', 'unknown'))
                        
                        if event_type in ['wager_update', 'wager_placed', 'wager_cancelled', 'wager_matched']:
                            # Wager updates - trigger wager_update callbacks
                            self._schedule_callback('wager_update', private_update)
                        elif event_type in ['settlement', 'wager_settled', 'market_settled']:
                            # Settlement events - trigger settlement callbacks
                            self._schedule_callback('settlement', private_update)
                        elif event_type in ['balance_update', 'balance_change']:
                            # Balance updates - trigger balance_update callbacks
                            self._schedule_callback('balance_update', private_update)
                            
                            # Also update local balance if available
                            if 'balance' in private_update:
                                self.balance = private_update['balance']
                        else:
                            # Generic private update - default to wager_update
                            self._schedule_callback('wager_update', private_update)
                            
                    except json.JSONDecodeError:
                        # If payload is not JSON, treat as raw string update
                        logger.debug(f"Non-JSON private update: {decoded_data}")
                        self._schedule_callback('wager_update', {'raw_data': decoded_data})
                    
        except Exception as e:
            logger.error(f"Error handling private event: {e}")
    
    def _schedule_callback(self, event_type: str, data: Any):
        """Safely schedule callback execution on the main event loop"""
        if self.event_loop and not self.event_loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._trigger_callbacks(event_type, data),
                    self.event_loop
                )
            except Exception as e:
                logger.error(f"Error scheduling callback for {event_type}: {e}")
        else:
            logger.warning(f"No event loop available for {event_type} callback")
    
    async def _trigger_callbacks(self, event_type: str, data: Any):
        """Trigger registered callbacks"""
        for callback in self.callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in callback for {event_type}: {e}")
    
    def subscribe_market_data(self, callback: Callable):
        """Subscribe to market data updates"""
        self.callbacks['market_data'].append(callback)
    
    def subscribe_wager_updates(self, callback: Callable):
        """Subscribe to wager updates"""
        self.callbacks['wager_update'].append(callback)
    
    def subscribe_settlements(self, callback: Callable):
        """Subscribe to settlement updates"""
        self.callbacks['settlement'].append(callback)
    
    def subscribe_balance_updates(self, callback: Callable):
        """Subscribe to balance updates"""
        self.callbacks['balance_update'].append(callback)
    
    def get_random_valid_odds(self) -> int:
        """Get a random valid odds value"""
        if not self.valid_odds:
            return 100
        return random.choice(self.valid_odds)
    
    def _get_auth_headers(self) -> dict:
        """Get authentication headers for API requests"""
        if not self.mm_session.get('access_token'):
            return {}

        return {
            'Authorization': f'Bearer {self.mm_session["access_token"]}',
            'Content-Type': 'application/json'
        }

    async def _async_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Execute an HTTP request in a background thread"""
        kwargs.setdefault('timeout', 10)
        return await asyncio.to_thread(requests.request, method, url, **kwargs)
    
    async def disconnect(self):
        """Disconnect from Prophet API"""
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._token_refresh_task
            self._token_refresh_task = None

        if self.pusher:
            self.pusher.disconnect()
            self.pusher = None

        self.is_connected = False
        logger.info("Disconnected from Prophet Sports API")
    
    def create_wager(self, line_id: int, odds: int, stake: float) -> Wager:
        """Create a new wager object"""
        return Wager(
            external_id=str(uuid.uuid4()),
            line_id=line_id,
            odds=odds,
            stake=stake,
            timestamp=time.time()
        )
