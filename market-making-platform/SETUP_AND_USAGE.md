# Market Making Platform - Setup and Usage Guide

## 🏗️ What We've Built

We've successfully created a comprehensive **Sports Betting Market Making Platform** built on top of the Prophet API. Here's what the platform includes:

### Core Components

1. **Prophet API Integration** (`src/exchanges/prophet_sports_api.py`)
   - Full REST API and WebSocket connectivity
   - Authentication and session management
   - Wager placement, cancellation, and batch operations
   - Real-time market data feeds via Pusher WebSockets

2. **Trading Engine** (`src/core/platform.py`)
   - Main orchestrator for all platform components
   - Automated scheduling and lifecycle management
   - Real-time event processing and callbacks

3. **Wager Management** (`src/core/wager_manager.py`)
   - Complete wager lifecycle tracking
   - Position and exposure monitoring
   - Risk validation and limits enforcement

4. **Risk Management** (`src/risk/risk_manager.py`)
   - Real-time risk assessment
   - Position size and exposure limits
   - Daily P&L tracking and stop-loss controls

5. **Strategy Engine** (`src/strategies/simple_market_maker.py`)
   - Configurable market making strategy
   - Automated quote generation and placement
   - Position rebalancing and inventory management

6. **Configuration System** (`src/config/settings.py`)
   - YAML/JSON configuration files
   - Environment variable support
   - Comprehensive validation

7. **Market Data Processing** (`src/data/market_data_manager.py`)
   - Real-time data feed processing
   - Historical data storage
   - Market state tracking

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /Users/doug/market-making-platform
pip install -r requirements.txt
```

### 2. Configure API Credentials

The platform uses the Prophet API credentials from your existing `ProphetApiTest` repository. We've already copied the `user_info.json` file:

```bash
# Verify credentials are in place
cat config/user_info.json
```

### 3. Test the Setup

Run the test script to verify everything works:

```bash
python test_platform.py
```

This will:
- ✅ Test Prophet API connection
- ✅ Verify account balance
- ✅ Load available tournaments and events
- ✅ Validate platform components

### 4. Run the Platform (Dry Run Mode)

Start the platform in safe mode (no real wagers):

```bash
python src/main.py --dry-run --log-level INFO
```

### 5. Run the Platform (Live Mode)

⚠️ **WARNING**: This will place real wagers with real money!

```bash
python src/main.py --log-level INFO
```

## 📊 Platform Features

### Real-Time Market Making
- Connects to Prophet API WebSocket feeds
- Processes live market data updates
- Automatically places and manages wagers
- Supports multiple tournaments (MLB, NBA, NFL, NHL)

### Risk Management
- **Position Limits**: Maximum stake per wager and total exposure
- **Daily Loss Limits**: Automatic trading halt on excessive losses
- **Exposure Controls**: Per-event and overall position monitoring
- **Emergency Stop**: Instant cancellation of all open wagers

### Strategy Configuration
- **Spread Margin**: Configurable profit margin on quotes
- **Inventory Management**: Automatic position rebalancing
- **Quote Refresh**: Regular strategy execution intervals
- **Market Selection**: Configurable sports and market types

### Monitoring & Logging
- **Real-time Statistics**: Platform uptime, wagers, P&L
- **Comprehensive Logging**: File and console output
- **Health Checks**: Component status monitoring
- **Performance Metrics**: Execution timing and success rates

## ⚙️ Configuration

### Main Configuration (`config/default.yaml`)

The platform creates a default configuration file with these key settings:

```yaml
trading:
  dry_run: true                    # Safe mode - no real wagers
  max_stake_per_wager: 10.0       # Maximum $ per individual wager
  max_total_exposure: 1000.0      # Maximum total $ at risk
  default_stake: 5.0              # Default wager amount
  max_concurrent_wagers: 50       # Maximum active wagers

strategy:
  strategy_type: "simple_market_maker"
  spread_margin: 0.02             # 2% profit margin
  max_position: 100               # Maximum wagers per strategy
  quote_refresh_seconds: 5        # How often to refresh quotes

risk:
  max_daily_loss: 500.0          # Daily stop-loss limit
  max_position_size: 100.0       # Maximum position per event
  stop_loss_percentage: 0.05     # 5% stop-loss trigger
```

### API Credentials (`config/user_info.json`)

```json
{
  "access_key": "your_prophet_api_key",
  "secret_key": "your_prophet_secret_key", 
  "tournaments": ["MLB", "NBA", "NFL", "NHL"]
}
```

## 🎯 Usage Examples

### Basic Operation
```bash
# Test connection and view available events
python test_platform.py

# Start in dry-run mode (recommended for testing)
python src/main.py --dry-run

# Start with debug logging
python src/main.py --dry-run --log-level DEBUG

# Use custom configuration
python src/main.py --config my_config.yaml --dry-run
```

### Platform Status
While running, the platform will show:
- Real-time balance updates
- Active wager count and exposure
- Tournament and event availability  
- Strategy performance metrics
- Risk management alerts

### Emergency Controls
- **Ctrl+C**: Graceful shutdown (cancels all wagers)
- **Emergency Stop**: Built-in risk limits automatically halt trading

## 🔧 Architecture Overview

```
Market Making Platform
├── Prophet API Client (REST + WebSocket)
├── Core Platform (Orchestration)
├── Wager Manager (Lifecycle Tracking)  
├── Risk Manager (Limits & Controls)
├── Strategy Engine (Market Making Logic)
├── Market Data Manager (Real-time Feeds)
└── Configuration System (Settings & Credentials)
```

### Data Flow
1. **Connection**: Platform connects to Prophet API
2. **Initialization**: Loads tournaments, events, and markets
3. **Strategy Execution**: Generates and places wagers based on algorithm
4. **Risk Monitoring**: Continuously validates exposure and limits
5. **Real-time Updates**: Processes market data and wager status changes
6. **Position Management**: Rebalances and cancels wagers as needed

## 🛡️ Safety Features

### Built-in Protections
- **Dry Run Mode**: Test all functionality without real money
- **Position Limits**: Automatic exposure controls
- **Daily Loss Limits**: Stop-loss protection
- **Wager Validation**: Pre-flight checks on all orders
- **Emergency Shutdown**: Instant halt and cleanup

### Recommended Settings for Testing
```yaml
trading:
  dry_run: true                   # Always start with dry run!
  max_stake_per_wager: 1.0       # Small stakes for testing
  max_total_exposure: 50.0       # Low exposure limit
  max_concurrent_wagers: 10      # Fewer simultaneous wagers
```

## 📈 Performance Monitoring

The platform provides real-time statistics:

- **Platform Status**: Running time, connection status
- **Trading Activity**: Wagers placed, cancelled, matched
- **Financial Metrics**: Current balance, total exposure, P&L
- **Risk Metrics**: Position limits, exposure ratios
- **API Performance**: Request success rates, response times

## 🐛 Troubleshooting

### Common Issues

1. **API Connection Fails**
   - Check credentials in `config/user_info.json`
   - Verify Prophet API service status
   - Check network connectivity

2. **No Events Available**
   - Verify tournament configuration
   - Check if events are currently active
   - Confirm API permissions

3. **Wagers Not Placing**
   - Check dry_run mode setting
   - Verify risk limits aren't exceeded
   - Review wager validation logs

### Debug Mode
```bash
python src/main.py --dry-run --log-level DEBUG
```

This provides detailed logging of:
- API requests and responses
- Strategy decision making
- Risk management checks
- WebSocket message processing

## 🎉 Success!

You now have a fully functional sports betting market making platform that:

✅ **Connects** to the Prophet API  
✅ **Processes** real-time market data  
✅ **Executes** automated trading strategies  
✅ **Manages** risk and exposure  
✅ **Monitors** performance and health  
✅ **Protects** against losses with built-in limits  

The platform is production-ready but start with dry-run mode to familiarize yourself with its operation before going live!

## 📞 Next Steps

1. **Test thoroughly** in dry-run mode
2. **Customize** strategy parameters for your preferences  
3. **Set appropriate** risk limits for your account size
4. **Monitor** performance and adjust as needed
5. **Scale up** gradually as you gain confidence

**Happy Trading! 🚀**
