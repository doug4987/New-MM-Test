#!/usr/bin/env python3
"""
Tournament Status Verification
Check tournament status and WebSocket channel requirements
"""

import asyncio
import json
import sys
import os
import requests
from urllib.parse import urljoin

# Add src to Python path  
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from exchanges.prophet_sports_api import ProphetSportsAPI
from config.settings import Settings
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="{time:HH:mm:ss.SSS} | {level} | {message}")

class TournamentVerifier:
    def __init__(self):
        self.api = None
        
    async def verify_tournaments_and_channels(self):
        """Verify tournament status and channel subscription requirements"""
        print("🏆 TOURNAMENT STATUS VERIFICATION")
        print("=" * 60)
        
        settings = Settings()
        self.api = ProphetSportsAPI(
            access_key=settings.prophet_api.access_key,
            secret_key=settings.prophet_api.secret_key,
            base_url=settings.prophet_api.base_url
        )
        
        # Step 1: Login
        print("\n1️⃣ LOGGING IN...")
        success = await self.api.login()
        if not success:
            print("❌ Failed to login")
            return
        
        print("✅ Login successful")
        
        # Step 2: Check ALL tournaments
        print("\n2️⃣ LOADING ALL TOURNAMENTS...")
        await self.api._load_tournaments()
        
        print(f"📊 TOURNAMENT SUMMARY:")
        print(f"   All tournaments available: {len(self.api.all_tournaments)}")
        print(f"   My tournaments (filtered): {len(self.api.my_tournaments)}")
        
        # Show all available tournaments
        print(f"\n📋 ALL AVAILABLE TOURNAMENTS:")
        for tournament in self.api.all_tournaments[:20]:  # Show first 20
            in_my_list = "✅" if tournament.id in self.api.my_tournaments else "❌"
            sport_str = str(tournament.sport)[:10] if tournament.sport else "N/A"
            print(f"   {in_my_list} ID: {tournament.id:3d} | Sport: {sport_str:10s} | Name: {tournament.name}")
        
        if len(self.api.all_tournaments) > 20:
            print(f"   ... and {len(self.api.all_tournaments) - 20} more")
        
        # Step 3: Test different channel subscription approaches
        print(f"\n3️⃣ TESTING CHANNEL SUBSCRIPTION APPROACHES...")
        
        # Approach 1: Empty tournament list (original broken approach)
        await self.test_channel_subscription("Empty tournament list", [])
        
        # Approach 2: Our filtered tournaments
        tournament_ids = list(self.api.my_tournaments.keys())
        await self.test_channel_subscription("Our filtered tournaments", tournament_ids)
        
        # Approach 3: First few tournaments from all list
        first_few_ids = [t.id for t in self.api.all_tournaments[:3]]
        await self.test_channel_subscription("First 3 all tournaments", first_few_ids)
        
        # Approach 4: Try without tournament filter (might get all channels)
        await self.test_channel_subscription("No tournament filter", None)
        
        # Step 4: Check events for our tournaments
        print(f"\n4️⃣ CHECKING EVENTS FOR OUR TOURNAMENTS...")
        await self.api._load_events_and_markets()
        
        if len(self.api.sport_events) > 0:
            print(f"✅ Found {len(self.api.sport_events)} sport events")
            
            # Show some examples
            for i, (event_id, event) in enumerate(self.api.sport_events.items()):
                if i >= 5:  # Show first 5
                    break
                market_count = len(event.markets) if event.markets else 0
                print(f"   Event {event_id}: {event.name} ({market_count} markets)")
        else:
            print(f"⚠️ No sport events found - tournaments might be inactive")
        
        print(f"\n🔍 DIAGNOSIS & RECOMMENDATIONS:")
        
        if len(self.api.my_tournaments) == 0:
            print(f"❌ Problem: No tournaments match our filter criteria")
            print(f"   Current filter: {self.api.tournaments_interested}")
            print(f"   💡 Solution: Update tournament filter to match available tournaments")
        
        if len(self.api.sport_events) == 0:
            print(f"❌ Problem: No events found for tournaments")
            print(f"   This could mean tournaments are inactive or out of season")
            print(f"   💡 Solution: Use active tournaments with upcoming events")
        
        # Cleanup
        await self.api.disconnect()
    
    async def test_channel_subscription(self, approach_name, tournament_ids):
        """Test channel subscription with different tournament ID approaches"""
        print(f"\n🧪 Testing: {approach_name}")
        
        try:
            # Mock the socket_id for testing
            mock_socket_id = "test_socket_123"
            
            # Prepare headers similar to _get_channels method
            auth_url = urljoin(self.api.base_url, self.api.urls['mm_auth'])
            
            if tournament_ids is None:
                # No tournament filter - don't include header-subscriptions
                headers = {
                    'Authorization': f'Bearer {self.api.mm_session["access_token"]}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                print(f"   📋 Headers: No tournament filter")
            else:
                headers = {
                    'Authorization': f'Bearer {self.api.mm_session["access_token"]}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'header-subscriptions': json.dumps([{"type": "tournament", "ids": tournament_ids}])
                }
                print(f"   📋 Tournament IDs: {tournament_ids}")
            
            response = requests.post(
                auth_url,
                data={'socket_id': mock_socket_id},
                headers=headers,
                timeout=10
            )
            
            print(f"   📡 Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                channels = result.get('data', {}).get('authorized_channel', [])
                
                public_channels = [ch for ch in channels if 'broadcast' in ch.get('channel_name', '')]
                private_channels = [ch for ch in channels if 'broadcast' not in ch.get('channel_name', '')]
                
                print(f"   ✅ SUCCESS: {len(channels)} total channels")
                print(f"      📡 Public: {len(public_channels)}")
                print(f"      🔒 Private: {len(private_channels)}")
                
                if len(public_channels) > 0:
                    print(f"      🎯 Found public channels! This approach works.")
                    for ch in public_channels[:3]:  # Show first 3
                        print(f"         - {ch.get('channel_name')}")
                
            elif response.status_code == 500:
                print(f"   ❌ FAILED: 500 Internal Server Error")
                print(f"      This approach causes server-side issues")
                
            else:
                print(f"   ❌ FAILED: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"      Error: {error_data}")
                except:
                    print(f"      Response: {response.text[:200]}")
        
        except requests.exceptions.Timeout:
            print(f"   ⏰ TIMEOUT: Request took too long")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

async def main():
    verifier = TournamentVerifier()
    await verifier.verify_tournaments_and_channels()

if __name__ == "__main__":
    asyncio.run(main())
