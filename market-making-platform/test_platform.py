#!/usr/bin/env python3
"""
Test script for Market Making Platform
Tests basic functionality without placing real wagers
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.config.settings import Settings
from src.exchanges.prophet_sports_api import ProphetSportsAPI
from src.utils.logger import setup_logger


async def test_prophet_connection():
    """Test connection to Prophet API"""
    print("Testing Prophet API connection...")
    
    # Setup logging
    logger = setup_logger("INFO", "logs/test.log")
    
    # Load settings
    settings = Settings("config/default.yaml")
    
    # Validate credentials
    if not settings.prophet_api.access_key or settings.prophet_api.access_key == "your_access_key_here":
        print("❌ No valid Prophet API credentials found!")
        print("Please update config/user_info.json with your API credentials")
        return False
    
    print(f"✅ Loaded configuration")
    print(f"   - Base URL: {settings.prophet_api.base_url}")
    print(f"   - Tournaments: {settings.prophet_api.tournaments}")
    
    # Test API connection
    try:
        api = ProphetSportsAPI(
            access_key=settings.prophet_api.access_key,
            secret_key=settings.prophet_api.secret_key,
            base_url=settings.prophet_api.base_url
        )
        
        # Login
        success = await api.login()
        if not success:
            print("❌ Failed to login to Prophet API")
            return False
        
        print("✅ Successfully logged in to Prophet API")
        
        # Get balance
        balance = await api.get_balance()
        print(f"✅ Account balance: ${balance.balance:.2f}")
        
        # Initialize data
        await api.initialize_data()
        print(f"✅ Loaded {len(api.my_tournaments)} tournaments")
        print(f"✅ Loaded {len(api.sport_events)} events")
        
        # List some events
        if api.sport_events:
            print("\nAvailable Events:")
            for i, (event_id, event) in enumerate(api.sport_events.items()):
                if i >= 3:  # Show only first 3
                    break
                print(f"   - {event.name} (ID: {event_id}, Markets: {len(event.markets)})")
        
        # Disconnect
        await api.disconnect()
        print("✅ Disconnected from Prophet API")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Prophet API: {e}")
        return False


async def test_platform_components():
    """Test platform component initialization"""
    print("\nTesting platform components...")
    
    try:
        settings = Settings("config/default.yaml")
        
        # Test settings validation (will fail without valid credentials, but that's expected)
        print("✅ Settings system working")
        
        # Test configuration structure
        print(f"✅ Trading config: dry_run={settings.trading.dry_run}")
        print(f"✅ Risk config: max_daily_loss=${settings.risk.max_daily_loss}")
        print(f"✅ Strategy config: {settings.strategy.strategy_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing platform components: {e}")
        return False


async def main():
    """Main test function"""
    print("=== Market Making Platform Test ===\n")
    
    # Test components
    components_ok = await test_platform_components()
    
    # Test API connection
    api_ok = await test_prophet_connection()
    
    print("\n=== Test Summary ===")
    print(f"Platform Components: {'✅ PASS' if components_ok else '❌ FAIL'}")
    print(f"Prophet API Connection: {'✅ PASS' if api_ok else '❌ FAIL'}")
    
    if api_ok and components_ok:
        print("\n🎉 All tests passed! Platform is ready to run.")
        print("\nTo start the platform:")
        print("  python src/main.py --dry-run")
    else:
        print("\n⚠️  Some tests failed. Check configuration and credentials.")
        
    return api_ok and components_ok


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
