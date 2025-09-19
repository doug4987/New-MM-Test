#!/usr/bin/env python3
"""
Market Making Platform with Real-time Dashboard
Launches the platform with a web-based dashboard for live order book visualization
"""

import asyncio
import argparse
import sys
import threading
import time
from pathlib import Path

# Add src to Python path
sys.path.append(str(Path(__file__).parent / "src"))

from src.config.settings import Settings
from src.core.platform import MarketMakingPlatform
from src.ui.dashboard_server import DashboardServer
from src.utils.logger import setup_logger


class PlatformWithDashboard:
    """Market Making Platform with integrated web dashboard"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.platform: MarketMakingPlatform = None
        self.dashboard: DashboardServer = None
        self.is_running = False
        self.logger = None
    
    async def start(self):
        """Start the platform and dashboard"""
        try:
            self.logger = setup_logger(
                self.settings.logging.level,
                str(self.settings.get_log_file_path())
            )
            
            self.logger.info("🚀 Starting Market Making Platform with Dashboard")
            
            # Initialize platform
            self.platform = MarketMakingPlatform(self.settings)
            
            # Initialize dashboard
            self.dashboard = DashboardServer(
                platform=self.platform,
                host=self.settings.web.host,
                port=self.settings.web.port
            )
            
            # Start platform in background
            self.logger.info("Starting trading platform...")
            platform_task = asyncio.create_task(self._run_platform())
            
            # Give platform time to start
            await asyncio.sleep(3)
            
            # Start dashboard server
            self.logger.info(f"Starting dashboard server on http://{self.settings.web.host}:{self.settings.web.port}")
            dashboard_task = asyncio.create_task(self.dashboard.start_server())
            
            # Wait for both to complete (or fail)
            await asyncio.gather(platform_task, dashboard_task)
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error starting platform with dashboard: {e}")
            raise
    
    async def _run_platform(self):
        """Run the trading platform"""
        try:
            await self.platform.start()
            self.is_running = True
            
            # Keep platform running
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Platform error: {e}")
            raise
    
    async def stop(self):
        """Stop the platform and dashboard"""
        if self.logger:
            self.logger.info("Stopping platform and dashboard...")
        self.is_running = False
        
        if self.platform:
            await self.platform.stop()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Market Making Platform with Dashboard")
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
        help="Run in simulation mode (no real wagers)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Dashboard port (default: 8000)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Dashboard host (default: 127.0.0.1)"
    )
    
    args = parser.parse_args()
    
    # Load settings
    settings = Settings(args.config)
    
    # Override settings with command line args
    if args.dry_run:
        settings.trading.dry_run = True
    if args.port:
        settings.web.port = args.port
    if args.host:
        settings.web.host = args.host
    
    settings.logging.level = args.log_level
    
    # Validate credentials
    if not settings.prophet_api.access_key or settings.prophet_api.access_key == "your_access_key_here":
        print("❌ No valid Prophet API credentials found!")
        print("Please update config/user_info.json with your API credentials")
        sys.exit(1)
    
    print("🏆 Market Making Platform with Live Dashboard")
    print("=" * 50)
    print(f"📊 Dashboard URL: http://{settings.web.host}:{settings.web.port}")
    print(f"🔧 Configuration: {args.config}")
    print(f"🧪 Dry Run Mode: {settings.trading.dry_run}")
    print(f"📈 Tournaments: {', '.join(settings.prophet_api.tournaments)}")
    print("=" * 50)
    print()
    
    # Create and start the platform with dashboard
    app = PlatformWithDashboard(settings)
    
    try:
        await app.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
        await app.stop()
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        await app.stop()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Shutdown complete")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
