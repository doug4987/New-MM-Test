#!/usr/bin/env python3
"""
Market Making Platform - Main Application Entry Point
Built on top of Prophet API
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add src to Python path
sys.path.append(str(Path(__file__).parent))

from config.settings import Settings
from core.platform import MarketMakingPlatform
from utils.logger import setup_logger
from ui.dashboard_server import DashboardServer


async def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="Market Making Platform")
    parser.add_argument(
        "--config", "-c", 
        default="config/default.yaml",
        help="Configuration file path"
    )
    parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Run in simulation mode (no real trades)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logger(args.log_level)
    
    # Load configuration
    settings = Settings(args.config)
    if args.dry_run:
        settings.trading.dry_run = True
    
    logger.info("Starting Market Making Platform")
    logger.info(f"Configuration: {args.config}")
    logger.info(f"Dry run mode: {settings.trading.dry_run}")
    
    # Initialize and start the platform
    platform = MarketMakingPlatform(settings)
    
    try:
        await platform.start()
        logger.info("Platform started successfully")
        
        # Initialize and start dashboard server
        dashboard_server = DashboardServer(platform, host="127.0.0.1", port=8000)
        logger.info("Starting dashboard server on http://127.0.0.1:8000")
        
        # Run platform and dashboard server concurrently
        async def keep_platform_running():
            while True:
                await asyncio.sleep(1)
        
        # Start both the platform loop and dashboard server
        await asyncio.gather(
            keep_platform_running(),
            dashboard_server.start_server()
        )
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Platform error: {e}")
        raise
    finally:
        await platform.stop()
        logger.info("Platform stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
