#!/usr/bin/env python3
"""
Test Market Depth - Show all odds levels from Prophet API

This script demonstrates how the updated market data manager now captures
all available odds levels for each selection, not just the "best" odds.
This gives us true market depth visibility.
"""

import asyncio
import json
import sys
import os
from loguru import logger

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from exchanges.prophet_sports_api import ProphetSportsAPI
from data.market_data_manager import MarketDataManager
from config.settings import Settings

logger.add("logs/market_depth_test.log", rotation="10 MB", level="DEBUG")

async def test_market_depth():
    """Test comprehensive market depth extraction"""
    
    # Load settings and initialize API
    settings = Settings()
    api = ProphetSportsAPI(
        access_key=settings.prophet_api.access_key,
        secret_key=settings.prophet_api.secret_key,
        base_url=settings.prophet_api.base_url
    )
    
    # Log into the platform
    logger.info("Logging into Prophet Sports API...")
    success = await api.login()
    
    if not success:
        logger.error("Failed to login to Prophet Sports API")
        return
    
    logger.info("Login successful!")
    
    # Initialize data (loads tournaments and events)
    logger.info("Loading market data...")
    await api.initialize_data()
    
    # Initialize market data manager
    manager = MarketDataManager(api)
    await manager.initialize_order_books()
    
    # Find the Athletics vs Red Sox game
    target_event_id = 10076583
    target_event = None
    
    for event_id, event in api.sport_events.items():
        if event_id == target_event_id:
            target_event = event
            break
    
    if not target_event:
        logger.error(f"Event {target_event_id} not found")
        return
    
    logger.info(f"Found target event: {target_event.name}")
    
    # Get order books for this event
    order_books = manager.get_event_order_books(target_event_id)
    logger.info(f"Found {len(order_books)} order books for event {target_event_id}")
    
    # Display comprehensive market depth for each market type
    for order_book in order_books:
        market_type = order_book.market_type
        logger.info(f"\n=== MARKET DEPTH: {market_type.upper()} ===")
        logger.info(f"Market ID: {order_book.market_id}")
        logger.info(f"Total Selections: {len(order_book.selections)}")
        logger.info(f"Total Volume: ${order_book.total_volume:.2f}")
        logger.info(f"Spread: {order_book.spread}")
        
        if not order_book.selections:
            logger.info("No selections available")
            continue
        
        # Group selections by name to show depth
        selections_by_name = {}
        for selection in order_book.selections.values():
            name = selection.selection_name
            if name not in selections_by_name:
                selections_by_name[name] = []
            selections_by_name[name].append(selection)
        
        # Display depth for each selection
        for sel_name, levels in selections_by_name.items():
            logger.info(f"\n  Selection: {sel_name}")
            logger.info(f"  Available Levels: {len(levels)}")
            
            # Sort levels by odds for better display
            valid_levels = [l for l in levels if l.odds is not None]
            if valid_levels:
                # Sort positive odds high-to-low, negative odds by absolute value low-to-high
                valid_levels.sort(key=lambda x: (
                    x.odds if x.odds > 0 else 1000 + abs(x.odds)
                ), reverse=True)
                
                for i, level in enumerate(valid_levels):
                    implied_prob = calculate_implied_probability(level.odds)
                    logger.info(f"    Level {i+1}: {level.odds:+4d} (${level.size:6.2f}) [{implied_prob:5.1f}%]")
            else:
                null_levels = [l for l in levels if l.odds is None]
                logger.info(f"    {len(null_levels)} levels with null odds (${sum(l.size for l in null_levels):.2f} total)")
    
    logger.info(f"\n=== RAW API DATA SAMPLE ===")
    
    # Show raw market data for comparison
    if target_event.markets:
        sample_market = target_event.markets[0]
        logger.info(f"Sample market raw structure:")
        logger.info(json.dumps(sample_market, indent=2, default=str))

def calculate_implied_probability(american_odds: int) -> float:
    """Calculate implied probability from American odds"""
    if american_odds > 0:
        return 100 / (american_odds + 100) * 100
    else:
        return abs(american_odds) / (abs(american_odds) + 100) * 100

if __name__ == "__main__":
    asyncio.run(test_market_depth())
