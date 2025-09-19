# Market Making Platform

A professional market making trading platform built on top of existing trading APIs.

## Features

- **Real-time Market Making**: Automated bid/ask quote generation
- **Risk Management**: Position limits, exposure controls, and real-time monitoring
- **Strategy Engine**: Configurable market making strategies
- **Exchange Connectivity**: Integration with trading APIs
- **Web Interface**: Real-time dashboard for monitoring and control
- **Backtesting**: Historical strategy performance analysis

## Architecture

```
src/
├── core/           # Core trading engine (order book, matching, orders)
├── strategies/     # Market making strategies and algorithms
├── data/          # Market data handling and storage
├── risk/          # Risk management and position monitoring
├── exchanges/     # Exchange API integrations
├── config/        # Configuration management
├── utils/         # Utility functions and helpers
└── ui/            # Web interface and dashboards
```

## Getting Started

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure your trading API credentials
4. Run the platform: `python src/main.py`

## Documentation

See the `docs/` directory for detailed documentation.

## License

MIT License
