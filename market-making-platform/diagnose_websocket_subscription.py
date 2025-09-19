#!/usr/bin/env python3
"""
WebSocket Subscription Diagnostics
Identify and fix issues with broadcast channel subscription
"""

import asyncio
import json
import sys
import os
import time
from typing import Dict, List

# Add src to Python path  
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from exchanges.prophet_sports_api import ProphetSportsAPI
from config.settings import Settings
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="{time:HH:mm:ss.SSS} | {level} | {message}")

class WebSocketSubscriptionDiagnostics:
    def __init__(self):
        self.issues_found = []
        self.public_channels_found = 0
        self.private_channels_found = 0
        self.total_channels_found = 0
        
    async def diagnose_subscription_issues(self):
        """Diagnose WebSocket subscription issues"""
        print("🔍 WEBSOCKET SUBSCRIPTION DIAGNOSTICS")
        print("=" * 60)
        
        settings = Settings()
        api = ProphetSportsAPI(
            access_key=settings.prophet_api.access_key,
            secret_key=settings.prophet_api.secret_key,
            base_url=settings.prophet_api.base_url
        )
        
        # Step 1: Connect and load data
        print("\n1️⃣ ESTABLISHING CONNECTION...")
        success = await api.login()
        if not success:
            print("❌ Failed to login")
            return
        
        print("✅ Login successful")
        
        # Step 2: Initialize data FIRST
        print("\n2️⃣ LOADING TOURNAMENT DATA...")
        await api.initialize_data()
        
        print(f"✅ Loaded {len(api.my_tournaments)} tournaments:")
        for tid, tournament in api.my_tournaments.items():
            print(f"   🏆 Tournament {tid}: {tournament.name}")
        
        # Step 3: Check header-subscriptions configuration
        print("\n3️⃣ CHECKING SUBSCRIPTION HEADERS...")
        tournament_ids = list(api.my_tournaments.keys())
        
        if len(tournament_ids) == 0:
            self.issues_found.append("No tournaments loaded - cannot subscribe to any channels")
            print("❌ No tournaments available for subscription!")
            return
        
        print(f"✅ Tournament IDs for subscription: {tournament_ids}")
        
        # Step 4: Monkey patch to capture channel subscription details
        original_get_channels = api._get_channels
        original_on_connected = api._on_websocket_connected
        
        def debug_get_channels(socket_id):
            print(f"\n🔍 Getting channels for socket: {socket_id}")
            
            # Show what tournament IDs we're requesting
            expected_header = json.dumps([{"type": "tournament", "ids": tournament_ids}])
            print(f"📋 Requesting tournaments in header: {expected_header}")
            
            channels = original_get_channels(socket_id)
            
            # Analyze returned channels
            self.total_channels_found = len(channels)
            
            public_channels = [ch for ch in channels if 'broadcast' in ch.get('channel_name', '')]
            private_channels = [ch for ch in channels if 'broadcast' not in ch.get('channel_name', '')]
            
            self.public_channels_found = len(public_channels)
            self.private_channels_found = len(private_channels)
            
            print(f"📊 CHANNEL ANALYSIS:")
            print(f"   Total channels returned: {self.total_channels_found}")
            print(f"   📡 Public/broadcast channels: {self.public_channels_found}")
            print(f"   🔒 Private channels: {self.private_channels_found}")
            
            if public_channels:
                print(f"   📡 PUBLIC CHANNELS:")
                for ch in public_channels:
                    print(f"      - {ch.get('channel_name')}")
                    events = ch.get('binding_events', [])
                    if events:
                        event_names = [e.get('name') for e in events]
                        print(f"        Events: {event_names}")
            else:
                self.issues_found.append("No broadcast/public channels returned by API")
                print("   ❌ NO PUBLIC CHANNELS FOUND")
                print("      This means market data updates won't be received!")
            
            if private_channels:
                print(f"   🔒 PRIVATE CHANNELS:")
                for ch in private_channels:
                    print(f"      - {ch.get('channel_name')}")
            
            return channels
        
        def debug_on_connected(data):
            print(f"\n🔌 WebSocket connected, processing subscriptions...")
            
            try:
                result = original_on_connected(data)
                print(f"✅ Connection handler completed successfully")
                return result
            except Exception as e:
                print(f"❌ Error in connection handler: {e}")
                self.issues_found.append(f"Connection handler error: {e}")
                raise
        
        # Apply debug patches
        api._get_channels = debug_get_channels
        api._on_websocket_connected = debug_on_connected
        
        # Step 5: Wait for WebSocket connection to establish
        print(f"\n4️⃣ MONITORING WEBSOCKET CONNECTION...")
        print("⏳ Waiting 15 seconds for connection and subscription...")
        
        # Monitor subscription process
        start_time = time.time()
        while (time.time() - start_time) < 15:
            await asyncio.sleep(1)
            elapsed = int(time.time() - start_time)
            if elapsed % 3 == 0:
                print(f"   ⏱️ {elapsed}s...")
        
        # Step 6: Analysis and recommendations
        print(f"\n📋 FINAL DIAGNOSIS")
        print("=" * 60)
        
        print(f"📊 SUBSCRIPTION STATUS:")
        print(f"   Tournaments loaded: {len(tournament_ids)}")
        print(f"   Total channels: {self.total_channels_found}")
        print(f"   Public channels: {self.public_channels_found}")
        print(f"   Private channels: {self.private_channels_found}")
        
        if len(self.issues_found) > 0:
            print(f"\n❌ ISSUES FOUND:")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"   {i}. {issue}")
        
        # Provide specific diagnosis
        if self.public_channels_found == 0:
            print(f"\n🚨 ROOT CAUSE IDENTIFIED:")
            print(f"   The Prophet API is NOT returning any public/broadcast channels")
            print(f"   for the tournament IDs: {tournament_ids}")
            print(f"")
            print(f"💡 POSSIBLE SOLUTIONS:")
            print(f"   1. Check if tournament IDs are correct and active")
            print(f"   2. Verify API permissions include broadcast channel access")
            print(f"   3. Check if tournaments have active markets")
            print(f"   4. Tournament names might not match expected values")
            print(f"")
            print(f"🔧 IMMEDIATE NEXT STEPS:")
            print(f"   1. Run tournament verification script")
            print(f"   2. Check tournament activity status")
            print(f"   3. Contact Prophet API support if needed")
        
        elif self.public_channels_found > 0:
            print(f"\n✅ PUBLIC CHANNELS ARE AVAILABLE!")
            print(f"   The issue may be in the subscription binding logic")
            print(f"   or in the event handling code.")
        
        # Cleanup
        await api.disconnect()
        
        return self.issues_found

async def main():
    diagnostics = WebSocketSubscriptionDiagnostics()
    issues = await diagnostics.diagnose_subscription_issues()
    
    print(f"\n🏁 DIAGNOSTICS COMPLETE")
    if len(issues) == 0:
        print("✅ No issues found!")
    else:
        print(f"❌ Found {len(issues)} issues to resolve")

if __name__ == "__main__":
    asyncio.run(main())
