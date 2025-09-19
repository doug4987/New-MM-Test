#!/usr/bin/env python3
"""
Bet Update Monitor
==================
This script specifically monitors for matched_bet messages and highlights bet activity.
"""

import asyncio
import json
import time
from datetime import datetime
from src.exchanges.prophet_sports_api import ProphetSportsAPI
from src.data.market_data_manager import MarketDataManager
from src.config.settings import Settings

class BetUpdateMonitor:
    def __init__(self):
        self.bet_count = 0
        self.dodgers_bets = 0
        self.start_time = time.time()
        
    def process_bet_message(self, data):
        """Process and highlight matched_bet messages"""
        
        # Extract metadata
        meta = data.get('_meta', {})
        change_type = meta.get('change_type', 'unknown')
        timestamp = meta.get('timestamp', 0)
        
        # Skip non-bet messages
        if change_type != 'matched_bet':
            return
            
        self.bet_count += 1
        
        # Extract bet information
        info = data.get('info', {})
        event_id = info.get('sport_event_id')
        market_id = info.get('market_id')
        matched_stake = info.get('matched_stake', 0)
        matched_odds = info.get('matched_odds', 0)
        line = info.get('line', 'N/A')
        outcome_id = info.get('outcome_id')
        aggressive = info.get('aggressive', False)
        line_id = info.get('line_id', '')
        
        # Convert timestamp
        if timestamp:
            bet_time = datetime.fromtimestamp(timestamp / 1_000_000_000).strftime('%H:%M:%S.%f')[:-3]
        else:
            bet_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        # Check if this is the Dodgers game
        is_dodgers = event_id == 10076606
        if is_dodgers:
            self.dodgers_bets += 1
            
        # Display bet information
        print(f"\n{'='*80}")
        print(f"🎯 BET DETECTED #{self.bet_count} at {bet_time}")
        print(f"{'='*80}")
        
        if is_dodgers:
            print(f"🏟️  >>> DODGERS GAME BET! <<<")
        
        print(f"📊 Event ID: {event_id}")
        print(f"📊 Market ID: {market_id}")
        print(f"📊 Outcome ID: {outcome_id}")
        print(f"💰 Stake: ${matched_stake}")
        print(f"📈 Odds: {matched_odds}")
        print(f"📏 Line: {line}")
        print(f"🎯 Line ID: {line_id[:20]}...")
        print(f"⚡ Aggressive: {'YES' if aggressive else 'NO'} ({'Taker' if aggressive else 'Maker'})")
        
        # Try to determine market type
        if market_id == 258:
            print(f"🎲 Market Type: TOTAL RUNS")
        elif 'moneyline' in str(market_id).lower():
            print(f"🎲 Market Type: MONEYLINE")
        else:
            print(f"🎲 Market Type: UNKNOWN (ID: {market_id})")
            
        print(f"{'='*80}")
        
        return {
            'event_id': event_id,
            'market_id': market_id,
            'stake': matched_stake,
            'odds': matched_odds,
            'line': line,
            'is_dodgers': is_dodgers,
            'aggressive': aggressive,
            'timestamp': bet_time
        }

async def main():
    print("🎯 Bet Update Monitor - Live Detection")
    print("=" * 60)
    print("This will specifically highlight matched_bet messages")
    print("Place bets and watch for detection!")
    print("=" * 60)
    print()
    
    # Load configuration
    settings = Settings("config/default.yaml")
    
    # Create API client
    api = ProphetSportsAPI(
        access_key=settings.prophet_api.access_key,
        secret_key=settings.prophet_api.secret_key,
        base_url=settings.prophet_api.base_url
    )
    
    # Set API tournaments
    api.tournaments_interested = settings.prophet_api.tournaments
    
    # Create monitor
    monitor = BetUpdateMonitor()
    
    print("🔑 Logging in...")
    await api.login()
    print("✅ Login successful")
    
    print("📊 Initializing data and WebSocket...")
    await api.initialize_data()
    print("✅ WebSocket connected")
    
    print("🏗️  Creating MarketDataManager...")
    market_manager = MarketDataManager(api)
    
    print("📈 Initializing order books...")
    await market_manager.initialize_order_books()
    print("✅ Setup complete")
    print()
    
    # Store bet history
    bet_history = []
    
    # Handler that focuses only on bet detection
    async def bet_detection_handler(data):
        bet_info = monitor.process_bet_message(data)
        if bet_info:
            bet_history.append(bet_info)
        
        # Also let MarketDataManager process it
        try:
            await market_manager.process_update(data)
        except Exception as e:
            print(f"❌ MarketDataManager error: {e}")
    
    # Subscribe to market data updates
    api.subscribe_market_data(bet_detection_handler)
    
    print("🎯 Starting bet detection monitoring...")
    print("💡 Place your moneyline bets now!")
    print("🔍 Looking specifically for matched_bet messages...")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        # Run monitoring loop
        start_time = time.time()
        last_summary = start_time
        
        while True:
            await asyncio.sleep(5)
            current_time = time.time()
            
            # Summary every 30 seconds
            if current_time - last_summary >= 30:
                elapsed = current_time - start_time
                print(f"\n📊 BET MONITOR SUMMARY after {elapsed:.0f}s:")
                print(f"   Total bets detected: {monitor.bet_count}")
                print(f"   Dodgers game bets: {monitor.dodgers_bets}")
                if monitor.bet_count > 0:
                    print(f"   Recent bets:")
                    for i, bet in enumerate(bet_history[-5:]):  # Last 5 bets
                        marker = "🏟️ " if bet['is_dodgers'] else "   "
                        print(f"     {marker}#{len(bet_history)-4+i}: ${bet['stake']} @ {bet['odds']} (Event {bet['event_id']})")
                print()
                last_summary = current_time
            
    except KeyboardInterrupt:
        elapsed = time.time() - monitor.start_time
        print(f"\n🔴 Stopped bet monitoring")
        print(f"📊 FINAL BET ANALYSIS:")
        print(f"   Runtime: {elapsed:.0f}s") 
        print(f"   Total bets detected: {monitor.bet_count}")
        print(f"   Dodgers game bets: {monitor.dodgers_bets}")
        print(f"   Bet detection rate: {monitor.bet_count / (elapsed/60):.1f}/min")
        
        if bet_history:
            print(f"\n🎲 BET BREAKDOWN:")
            dodgers_total_stake = sum(bet['stake'] for bet in bet_history if bet['is_dodgers'])
            all_total_stake = sum(bet['stake'] for bet in bet_history)
            print(f"   Dodgers game total stake: ${dodgers_total_stake}")
            print(f"   All games total stake: ${all_total_stake}")
            
            if monitor.dodgers_bets > 0:
                print(f"\n🏟️  DODGERS GAME BETS:")
                for i, bet in enumerate([b for b in bet_history if b['is_dodgers']]):
                    role = "Taker" if bet['aggressive'] else "Maker"
                    print(f"     #{i+1}: ${bet['stake']} @ {bet['odds']} ({role}) at {bet['timestamp']}")
        
        print(f"\n🔍 CONCLUSION: Did we successfully detect your moneyline bets?")

if __name__ == "__main__":
    asyncio.run(main())
