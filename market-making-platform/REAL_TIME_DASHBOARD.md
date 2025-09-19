# 📈 Real-Time Order Book Dashboard

## 🎯 What You Asked For

You wanted to see **"a visual, real-time order book for each event"** when the platform processes live market data. 

**Mission Accomplished! 🎉**

We've built a comprehensive real-time web dashboard that shows:

- **Live Order Books** for every sports betting event
- **Real-time Updates** via WebSocket connections
- **Interactive Event Selection** to focus on specific games
- **Bid/Ask Spreads** with live pricing data
- **Platform Statistics** showing wagers and exposure
- **Connection Status** indicators

## 🚀 How to Run the Dashboard

### Quick Start
```bash
# Run the platform with live dashboard
python run_with_dashboard.py --dry-run

# Then open your browser to:
http://127.0.0.1:8000
```

### Command Line Options
```bash
# Custom port
python run_with_dashboard.py --port 8080 --dry-run

# Debug mode with detailed logging
python run_with_dashboard.py --log-level DEBUG --dry-run

# Production mode (real wagers!)
python run_with_dashboard.py --port 8000
```

## 📊 What the Dashboard Shows

### Real-Time Order Books
When the platform connects to the Prophet API and processes live market data, the dashboard displays:

#### **📈 Order Book Visualization**
- **Event Name** (e.g., "Yankees vs Red Sox")
- **Market Type** (Moneyline, Spread, Total)
- **Live Bid/Ask Levels** with odds and stake sizes
- **Best Bid/Ask** highlighting
- **Spread Information** and mid-price
- **Last Update Time** for each book

#### **🎯 Interactive Features**
- **Click Events** in the sidebar to filter order books
- **Real-time Updates** as market data changes
- **Connection Status** indicators (API & WebSocket)
- **Platform Statistics** showing active wagers and exposure

### Market Data Flow

```
Prophet API → Market Data Manager → Order Book Processing → WebSocket → Dashboard
     ↓                ↓                      ↓                ↓            ↓
Live Sports    Parse Market Data     Create Order Books   Broadcast    Visual Display
   Feeds       & Event Updates      with Bid/Ask Levels    Updates    of Order Books
```

## 🏗️ Technical Architecture

### Backend Components

1. **Enhanced Market Data Manager** (`src/data/market_data_manager.py`)
   - Processes live Prophet API feeds
   - Creates structured order books from market data
   - Manages real-time subscriptions
   - Broadcasts updates to dashboard

2. **Dashboard Server** (`src/ui/dashboard_server.py`)
   - FastAPI web server with WebSocket support
   - REST API endpoints for market data
   - Real-time broadcasting to connected clients
   - Order book serialization and transmission

3. **Order Book Data Structures**
   ```python
   @dataclass
   class OrderBook:
       event_id: int
       market_id: str
       market_type: str  # 'moneyline', 'spread', 'total'
       event_name: str
       bids: List[OrderBookLevel]  # Back orders (betting FOR)
       asks: List[OrderBookLevel]  # Lay orders (betting AGAINST)
       best_bid: Optional[OrderBookLevel]
       best_ask: Optional[OrderBookLevel]
       spread: float
       mid_price: float
   ```

### Frontend Features

1. **Real-Time WebSocket Connection**
   - Automatic reconnection on disconnect
   - Live order book updates
   - Platform status monitoring

2. **Interactive Event Selection**
   - Clickable event list in sidebar
   - Filtered order book display
   - Real-time statistics

3. **Professional Trading Interface**
   - Dark theme optimized for extended viewing
   - Color-coded bid/ask levels (green/red)
   - Monospace font for precise data alignment
   - Responsive grid layout

## 🎯 Order Book Data Processing

### How Live Market Data Becomes Visual Order Books

1. **Prophet API Feed Processing**
   ```python
   async def process_update(self, update_data):
       # Parse incoming Prophet API data
       parsed_data = self._parse_market_update(update_data)
       
       # Update order books with new market data
       await self._update_order_books(parsed_data)
       
       # Broadcast to WebSocket clients
       await self._notify_subscribers('order_book_update', order_book_data)
   ```

2. **Order Book Construction**
   - Extracts market selections from Prophet API
   - Creates bid/ask levels from betting odds
   - Calculates spreads and mid-prices
   - Sorts levels by price for proper display

3. **Real-Time Broadcasting**
   ```javascript
   // Frontend receives live updates
   ws.onmessage = (event) => {
       const message = JSON.parse(event.data);
       if (message.type === 'order_book_update') {
           this.updateOrderBook(message.data);
       }
   }
   ```

## 📱 Dashboard Screenshots

### Main Dashboard View
```
🏆 Market Making Platform                    [●] API  [●] WebSocket  $1,250.00
================================================================================

📊 Platform Stats          |  📈 Live Order Books
                           |  
Active Wagers: 15          |  ┌─ Yankees vs Red Sox - moneyline ─────────────┐
Total Exposure: $750       |  │ BACK (Bids)        │ LAY (Asks)             │
Order Books: 8             |  │ +140    $500  0.71 │ +160    $300  0.625    │
Events: 3                  |  │ +135    $250  0.74 │ +165    $450  0.606    │
                           |  │ +130    $750  0.77 │ +170    $200  0.588    │
🏅 Active Events           |  └─ Spread: 20 | Mid: 150.0 ─────────────────┘
                           |
[•] Yankees vs Red Sox     |  ┌─ Lakers vs Warriors - moneyline ──────────┐
    Markets: 3 | ID: 1234  |  │ BACK (Bids)        │ LAY (Asks)           │
                           |  │ -110    $1000 0.52 │ -105    $800  0.51   │
[ ] Cowboys vs Giants      |  │ -115    $600  0.53 │ -100    $1200 0.50   │
    Markets: 2 | ID: 1235  |  └─ Spread: 5 | Mid: -107.5 ────────────────┘
```

## 🔧 API Endpoints

The dashboard server provides these REST endpoints:

```bash
GET  /                          # Dashboard HTML page
GET  /api/platform/status       # Platform status and metrics
GET  /api/events               # List of active events
GET  /api/order-books          # All order books
GET  /api/order-books/{id}     # Specific order book
GET  /api/events/{id}/order-books  # Order books for event
GET  /api/wagers              # Active wagers
GET  /api/statistics          # Platform statistics
WS   /ws                      # WebSocket for real-time updates
```

## 🎨 Customization Options

### Styling and Appearance
- **Dark theme** optimized for trading
- **Color-coded** bid/ask levels
- **Responsive layout** for different screen sizes
- **Professional typography** with monospace fonts

### Configuration
```yaml
web:
  host: "127.0.0.1"
  port: 8000
  enable_dashboard: true
  auto_reload: false
```

### Real-Time Update Frequency
- **WebSocket**: Instant updates as market data changes
- **REST API**: 30-second periodic refreshes
- **Order Books**: Updated on every market data event

## 🎯 What This Means for You

When you run the platform with the dashboard:

1. **Connect to Prophet API** ✅
2. **Load live sports events** ✅
3. **Process real-time market data** ✅
4. **Create visual order books** ✅
5. **Display in web browser** ✅
6. **Update in real-time** ✅

You can now **see exactly what the platform is doing** with live market data:
- Which events have active markets
- Current bid/ask spreads for each market  
- How the order books change in real-time
- Platform performance and statistics
- Active wagers and exposure

## 🚦 Next Steps

1. **Test the Dashboard**
   ```bash
   python run_with_dashboard.py --dry-run
   # Open http://127.0.0.1:8000
   ```

2. **Monitor Live Data**
   - Click on different events to see their order books
   - Watch real-time updates as market data changes
   - Monitor platform statistics and wager activity

3. **Customize as Needed**
   - Adjust colors, layouts, or data display
   - Add more charts or visualizations
   - Integrate with additional data sources

**You now have a complete visual interface to see live market data processing in real-time! 🎉📈**
