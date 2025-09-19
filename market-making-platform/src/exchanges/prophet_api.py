"""
Prophet API Client
Integration with Prophet sports betting API for market making platform
"""

import asyncio
import json
import time
import uuid
import base64
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin

import aiohttp
import pysher
import requests
from loguru import logger


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Order data structure"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    timestamp: Optional[float] = None


@dataclass
class MarketData:
    """Market data structure"""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: float


@dataclass
class Position:
    """Position data structure"""
    symbol: str
    quantity: float
    avg_price: float
    unrealized_pnl: float
    realized_pnl: float


class ProphetAPI:
    """
    Prophet API client for trading operations
    This is a base implementation that will be adapted based on the actual API
    """
    
    def __init__(self, api_key: str, api_secret: str, base_url: str, ws_url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.ws_url = ws_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.callbacks: Dict[str, List[Callable]] = {
            'market_data': [],
            'order_update': [],
            'trade': [],
            'position_update': []
        }
        
    async def connect(self):
        """Establish connection to Prophet API"""
        try:
            # Initialize HTTP session
            self.session = aiohttp.ClientSession()
            
            # Test connection with account info
            account_info = await self.get_account_info()
            if account_info:
                logger.info("Successfully connected to Prophet API")
                self.is_connected = True
                
                # Start WebSocket connection for real-time data
                await self._start_websocket()
            else:
                logger.error("Failed to connect to Prophet API")
                
        except Exception as e:
            logger.error(f"Error connecting to Prophet API: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Prophet API"""
        self.is_connected = False
        
        if self.websocket:
            await self.websocket.close()
            
        if self.session:
            await self.session.close()
            
        logger.info("Disconnected from Prophet API")
    
    async def _start_websocket(self):
        """Start WebSocket connection for real-time data"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            
            # Send authentication message
            auth_msg = {
                "type": "auth",
                "api_key": self.api_key,
                "timestamp": int(time.time())
            }
            await self.websocket.send(json.dumps(auth_msg))
            
            # Start message handler
            asyncio.create_task(self._handle_websocket_messages())
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
    
    async def _handle_websocket_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self._process_message(data)
                
        except Exception as e:
            logger.error(f"WebSocket message handling error: {e}")
    
    async def _process_message(self, data: dict):
        """Process incoming WebSocket messages"""
        msg_type = data.get('type')
        
        if msg_type == 'market_data':
            market_data = MarketData(
                symbol=data['symbol'],
                bid=data['bid'],
                ask=data['ask'],
                last=data['last'],
                volume=data['volume'],
                timestamp=data['timestamp']
            )
            await self._trigger_callbacks('market_data', market_data)
            
        elif msg_type == 'order_update':
            # Process order updates
            await self._trigger_callbacks('order_update', data)
            
        elif msg_type == 'trade':
            # Process trade updates
            await self._trigger_callbacks('trade', data)
            
        elif msg_type == 'position_update':
            # Process position updates
            await self._trigger_callbacks('position_update', data)
    
    async def _trigger_callbacks(self, event_type: str, data: Any):
        """Trigger registered callbacks for events"""
        for callback in self.callbacks.get(event_type, []):
            try:
                await callback(data)
            except Exception as e:
                logger.error(f"Callback error for {event_type}: {e}")
    
    def subscribe_market_data(self, callback: Callable):
        """Subscribe to market data updates"""
        self.callbacks['market_data'].append(callback)
    
    def subscribe_order_updates(self, callback: Callable):
        """Subscribe to order updates"""
        self.callbacks['order_update'].append(callback)
    
    def subscribe_trades(self, callback: Callable):
        """Subscribe to trade updates"""
        self.callbacks['trade'].append(callback)
    
    def subscribe_position_updates(self, callback: Callable):
        """Subscribe to position updates"""
        self.callbacks['position_update'].append(callback)
    
    async def get_account_info(self) -> Optional[dict]:
        """Get account information"""
        try:
            headers = self._get_auth_headers()
            async with self.session.get(f"{self.base_url}/account", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Account info request failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    async def place_order(self, order: Order) -> Optional[str]:
        """Place a new order"""
        try:
            headers = self._get_auth_headers()
            order_data = {
                "symbol": order.symbol,
                "side": order.side.value,
                "type": order.order_type.value,
                "quantity": order.quantity
            }
            
            if order.price:
                order_data["price"] = order.price
            if order.stop_price:
                order_data["stop_price"] = order.stop_price
            
            async with self.session.post(
                f"{self.base_url}/orders", 
                headers=headers, 
                json=order_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('order_id')
                else:
                    logger.error(f"Order placement failed: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        try:
            headers = self._get_auth_headers()
            async with self.session.delete(
                f"{self.base_url}/orders/{order_id}", 
                headers=headers
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {e}")
            return False
    
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        try:
            headers = self._get_auth_headers()
            async with self.session.get(f"{self.base_url}/positions", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    positions = []
                    for pos_data in data:
                        position = Position(
                            symbol=pos_data['symbol'],
                            quantity=pos_data['quantity'],
                            avg_price=pos_data['avg_price'],
                            unrealized_pnl=pos_data['unrealized_pnl'],
                            realized_pnl=pos_data['realized_pnl']
                        )
                        positions.append(position)
                    return positions
                else:
                    logger.error(f"Positions request failed: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_order_book(self, symbol: str) -> Optional[dict]:
        """Get order book for a symbol"""
        try:
            headers = self._get_auth_headers()
            async with self.session.get(
                f"{self.base_url}/orderbook/{symbol}", 
                headers=headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Order book request failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting order book: {e}")
            return None
    
    def _get_auth_headers(self) -> dict:
        """Generate authentication headers"""
        timestamp = str(int(time.time()))
        # This will need to be implemented based on actual Prophet API auth requirements
        return {
            "X-API-Key": self.api_key,
            "X-Timestamp": timestamp,
            "Content-Type": "application/json"
        }
    
    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to market data for a symbol"""
        if self.websocket:
            subscribe_msg = {
                "type": "subscribe",
                "symbol": symbol,
                "channels": ["market_data", "trades"]
            }
            await self.websocket.send(json.dumps(subscribe_msg))
    
    async def unsubscribe_from_symbol(self, symbol: str):
        """Unsubscribe from market data for a symbol"""
        if self.websocket:
            unsubscribe_msg = {
                "type": "unsubscribe",
                "symbol": symbol
            }
            await self.websocket.send(json.dumps(unsubscribe_msg))
