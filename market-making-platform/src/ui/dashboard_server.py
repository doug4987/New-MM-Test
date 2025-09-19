"""
Real-time Dashboard Server
FastAPI web server with WebSocket support for live order book visualization
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from loguru import logger
from core.platform import MarketMakingPlatform
from data.market_data_manager import OrderBook


class DashboardServer:
    """Real-time dashboard server for market making platform"""
    
    def __init__(self, platform: MarketMakingPlatform, host: str = "127.0.0.1", port: int = 8000):
        self.platform = platform
        self.host = host
        self.port = port
        
        # WebSocket connections
        self.active_connections: List[WebSocket] = []
        
        # FastAPI app
        self.app = FastAPI(title="Market Making Dashboard")
        
        # Setup templates and static files
        self.setup_static_files()
        self.setup_routes()
        
        # Subscribe to market data updates
        if platform.market_data_manager:
            platform.market_data_manager.subscribe_to_updates(self._on_market_data_update)
        
        logger.info(f"Dashboard server initialized on {host}:{port}")
    
    def setup_static_files(self):
        """Setup static file serving and templates"""
        # Create directories if they don't exist
        static_dir = Path("src/ui/static")
        templates_dir = Path("src/ui/templates")
        
        static_dir.mkdir(parents=True, exist_ok=True)
        templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # Templates
        self.templates = Jinja2Templates(directory=str(templates_dir))
    
    def setup_routes(self):
        """Setup API routes and WebSocket endpoints"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Main dashboard page"""
            return self.templates.TemplateResponse("dashboard.html", {"request": request})
        
        @self.app.get("/api/platform/status")
        async def platform_status():
            """Get platform status"""
            return self.platform.get_platform_status()
        
        @self.app.get("/api/events")
        async def get_events():
            """Get active events"""
            return self.platform.get_active_events()
        
        @self.app.get("/api/order-books")
        async def get_order_books(limit: Optional[int] = None):
            """Get all order books"""
            order_books = []
            if self.platform.market_data_manager:
                # Get all order books and sort by event and market priority
                all_order_books = list(self.platform.market_data_manager.get_all_order_books().values())
                sorted_order_books = self._sort_order_books_by_priority(all_order_books)
                
                # Apply limit if specified
                if limit:
                    sorted_order_books = sorted_order_books[:limit]
                
                for order_book in sorted_order_books:
                    order_books.append(self._serialize_order_book(order_book))
            return order_books
        
        @self.app.get("/api/order-books/{market_id}")
        async def get_order_book(market_id: str):
            """Get specific order book"""
            if self.platform.market_data_manager:
                order_book = self.platform.market_data_manager.get_order_book(market_id)
                if order_book:
                    return self._serialize_order_book(order_book)
            raise HTTPException(status_code=404, detail="Order book not found")
        
        @self.app.get("/api/events/{event_id}/order-books")
        async def get_event_order_books(event_id: int):
            """Get order books for a specific event"""
            order_books = []
            if self.platform.market_data_manager:
                event_order_books = self.platform.market_data_manager.get_event_order_books(event_id)
                for order_book in event_order_books:
                    order_books.append(self._serialize_order_book(order_book))
            return order_books
        
        @self.app.get("/api/wagers")
        async def get_wagers():
            """Get active wagers"""
            wagers = []
            if self.platform.wager_manager:
                for wager_record in self.platform.wager_manager.get_active_wagers():
                    wagers.append({
                        'external_id': wager_record.wager.external_id,
                        'line_id': wager_record.wager.line_id,
                        'odds': wager_record.wager.odds,
                        'stake': wager_record.wager.stake,
                        'status': wager_record.wager.status.value,
                        'strategy': wager_record.strategy_name,
                        'created_at': wager_record.created_at,
                        'market_context': wager_record.market_context
                    })
            return wagers
        
        @self.app.get("/api/statistics")
        async def get_statistics():
            """Get platform statistics"""
            stats = {
                'platform': self.platform.get_platform_status(),
                'wager_manager': self.platform.wager_manager.get_statistics() if self.platform.wager_manager else {},
                'market_data': self.platform.market_data_manager.get_statistics() if self.platform.market_data_manager else {},
                'risk_manager': self.platform.risk_manager.get_risk_summary() if self.platform.risk_manager else {}
            }
            
            if self.platform.strategy:
                stats['strategy'] = self.platform.strategy.get_strategy_stats()
            
            return stats
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await self.connect_websocket(websocket)
            try:
                while True:
                    # Keep connection alive and handle any incoming messages
                    data = await websocket.receive_text()
                    # Echo back or handle commands if needed
                    await websocket.send_text(f"Echo: {data}")
                    
            except WebSocketDisconnect:
                await self.disconnect_websocket(websocket)
    
    async def connect_websocket(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Send initial data
        await self._send_initial_data(websocket)
        
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    async def disconnect_websocket(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def _send_initial_data(self, websocket: WebSocket):
        """Send initial data to newly connected WebSocket"""
        try:
            # Send platform status
            await websocket.send_text(json.dumps({
                'type': 'platform_status',
                'data': self.platform.get_platform_status()
            }))
            
            # Send order books
            if self.platform.market_data_manager:
                order_books = []
                for order_book in self.platform.market_data_manager.get_all_order_books().values():
                    order_books.append(self._serialize_order_book(order_book))
                
                await websocket.send_text(json.dumps({
                    'type': 'order_books_snapshot',
                    'data': order_books
                }))
            
        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
    
    async def _on_market_data_update(self, update_type: str, data: Any):
        """Handle market data updates and broadcast to WebSocket clients"""
        try:
            if not self.active_connections:
                return
                
            message = None
            
            if update_type == 'order_book_update':
                order_book = data.get('order_book')
                if order_book:
                    message = {
                        'type': 'order_book_update',
                        'data': self._serialize_order_book(order_book)
                    }
            
            elif update_type == 'selection_update':
                # Live odds/selection changes
                message = {
                    'type': 'selection_update',
                    'data': {
                        'event_id': data.get('event_id'),
                        'market_id': data.get('market_id'),
                        'timestamp': time.time(),
                        'change_info': data.get('data', {})
                    }
                }
                
            elif update_type == 'trade_update':
                # Live trade/match notifications
                trade = data.get('trade', {})
                message = {
                    'type': 'trade_update', 
                    'data': {
                        'event_id': data.get('event_id'),
                        'market_id': data.get('market_id'),
                        'trade': {
                            'timestamp': trade.get('timestamp'),
                            'line': trade.get('line'),
                            'odds': trade.get('odds'),
                            'stake': trade.get('stake')
                        }
                    }
                }
                
            elif update_type == 'market_line_update':
                # New market lines
                message = {
                    'type': 'market_line_update',
                    'data': {
                        'event_id': data.get('event_id'),
                        'market_id': data.get('market_id'),
                        'line': data.get('line'),
                        'status': data.get('status'),
                        'timestamp': time.time()
                    }
                }
                
            elif update_type == 'market_data_update':
                # Generic market updates
                message = {
                    'type': 'market_data_update', 
                    'data': data
                }
            
            if message:
                # Broadcast to all connected clients
                await self._broadcast_message(message)
                logger.debug(f"Broadcasted {update_type} to {len(self.active_connections)} clients")
                
        except Exception as e:
            logger.error(f"Error handling market data update: {e}")
    
    async def _broadcast_message(self, message: dict):
        """Broadcast message to all connected WebSocket clients"""
        if not self.active_connections:
            return
        
        message_str = json.dumps(message, default=str)
        disconnected = []
        
        for websocket in self.active_connections:
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            await self.disconnect_websocket(websocket)
    
    def _sort_order_books_by_priority(self, order_books: List[OrderBook]) -> List[OrderBook]:
        """Sort order books by event and market type priority"""
        def get_market_priority(market_type: str) -> int:
            """Get priority for market type (lower number = higher priority)"""
            market_type_lower = market_type.lower()
            
            # Main markets appear first
            if 'moneyline' in market_type_lower or 'match_winner' in market_type_lower or 'winner' in market_type_lower:
                return 0
            elif 'spread' in market_type_lower or 'handicap' in market_type_lower or 'point_spread' in market_type_lower:
                return 1
            elif 'total' in market_type_lower or 'over_under' in market_type_lower or 'totals' in market_type_lower:
                return 2
            else:
                # All other markets
                return 10
        
        # Sort by event_id first, then by market priority, then by market_type alphabetically
        return sorted(order_books, key=lambda ob: (
            ob.event_id,
            get_market_priority(ob.market_type),
            ob.market_type.lower()
        ))
    
    def _serialize_order_book(self, order_book: OrderBook) -> dict:
        """Serialize order book for JSON transmission"""
        # Serialize line groups if they exist (for spread/total markets)
        line_groups = {}
        for line_value, selections_by_name in order_book.line_groups.items():
            line_groups[line_value] = {}
            for selection_name, selection_levels in selections_by_name.items():
                line_groups[line_value][selection_name] = [{
                    'selection_id': level.selection_id,
                    'selection_name': level.selection_name,
                    'odds': 'request' if level.odds is None else level.odds,
                    'size': level.size,
                    'timestamp': level.timestamp
                } for level in selection_levels]
        
        return {
            'market_id': order_book.market_id,
            'event_id': order_book.event_id,
            'event_name': order_book.event_name,
            'market_type': order_book.market_type,
            'last_update': order_book.last_update,
            'spread': order_book.spread,
            'total_volume': order_book.total_volume,
            'best_selection': {
                'selection_id': order_book.best_selection.selection_id,
                'selection_name': order_book.best_selection.selection_name,
                'odds': 'request' if order_book.best_selection.odds is None else order_book.best_selection.odds,
                'size': order_book.best_selection.size,
                'timestamp': order_book.best_selection.timestamp
            } if order_book.best_selection else None,
            'selections': [{
                'selection_id': selection.selection_id,
                'selection_name': selection.selection_name,
                'odds': 'request' if selection.odds is None else selection.odds,
                'size': selection.size,
                'timestamp': selection.timestamp
            } for selection in order_book.selections.values()],
            # New line-grouped data
            'line_groups': line_groups,
            'available_lines': order_book.available_lines,
            'has_multiple_lines': len(order_book.available_lines) > 1
        }
    
    async def start_server(self):
        """Start the dashboard server"""
        import uvicorn
        
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
