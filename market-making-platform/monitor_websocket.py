#!/usr/bin/env python3
"""
WebSocket Message Monitor - 2 Minute Capture
Monitor and display all WebSocket messages coming from Prophet API
"""
import asyncio
import json
import time
import base64
from datetime import datetime
import sys
sys.path.append('src')
from src.config.settings import Settings
from src.exchanges.prophet_sports_api import ProphetSportsAPI

class WebSocketMonitor:
    def __init__(self):
        self.message_count = 0
        self.market_updates = 0
        self.private_updates = 0
        self.start_time = time.time()
        self.last_update = time.time()
        
    def log_message(self, msg_type, data, decoded_data=None):
        self.message_count += 1
        current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        elapsed = time.time() - self.start_time
        
        print(f'\n[{current_time}] #{self.message_count} ({elapsed:.1f}s) - {msg_type}')
        
        if decoded_data:
            try:
                parsed = json.loads(decoded_data) if isinstance(decoded_data, str) else decoded_data
                # Truncate very long messages
                json_str = json.dumps(parsed, indent=2)
                if len(json_str) > 800:
                    print(f'  📊 Data: {json_str[:800]}...')
                else:
                    print(f'  📊 Data: {json_str}')
            except Exception as e:
                print(f'  📊 Raw Data: {str(decoded_data)[:300]}...')
                print(f'  ⚠️  Parse Error: {e}')
        else:
            print(f'  📊 Event Data: {str(data)[:200]}...')

async def main():
    monitor = WebSocketMonitor()
    print('🔍 WEBSOCKET MESSAGE MONITOR - 2 MINUTE CAPTURE')
    print('=' * 70)
    print(f'⏰ Started at: {datetime.now().strftime("%H:%M:%S")}')
    print('📡 Connecting to Prophet API and monitoring WebSocket messages...')
    
    # Load settings and connect
    settings = Settings()
    api = ProphetSportsAPI(
        access_key=settings.prophet_api.access_key,
        secret_key=settings.prophet_api.secret_key,
        base_url=settings.prophet_api.base_url
    )
    
    # Patch the WebSocket handlers to capture messages
    original_handle_public = api._handle_public_event
    original_handle_private = api._handle_private_event
    
    def capture_public_event(*args, **kwargs):
        try:
            if args and len(args) > 0:
                event_data = json.loads(args[0]) if isinstance(args[0], str) else args[0]
                payload = event_data.get('payload', '')
                
                if payload:
                    try:
                        decoded_data = base64.b64decode(payload).decode('utf-8')
                        monitor.log_message('📈 PUBLIC/MARKET', event_data, decoded_data)
                        monitor.market_updates += 1
                    except Exception as e:
                        monitor.log_message('📈 PUBLIC/MARKET (decode error)', event_data)
                        print(f'  ⚠️  Decode error: {e}')
                        monitor.market_updates += 1
                else:
                    monitor.log_message('📈 PUBLIC/MARKET (no payload)', event_data)
                    monitor.market_updates += 1
            
            # Call original handler
            return original_handle_public(*args, **kwargs)
        except Exception as e:
            print(f'❌ Error in public handler: {e}')
    
    def capture_private_event(*args, **kwargs):
        try:
            if args and len(args) > 0:
                event_data = json.loads(args[0]) if isinstance(args[0], str) else args[0]
                payload = event_data.get('payload', '')
                
                if payload:
                    try:
                        decoded_data = base64.b64decode(payload).decode('utf-8')
                        monitor.log_message('💰 PRIVATE/WAGER', event_data, decoded_data)
                        monitor.private_updates += 1
                    except Exception as e:
                        monitor.log_message('💰 PRIVATE/WAGER (decode error)', event_data)
                        print(f'  ⚠️  Decode error: {e}')
                        monitor.private_updates += 1
                else:
                    monitor.log_message('💰 PRIVATE/WAGER (no payload)', event_data)
                    monitor.private_updates += 1
            
            # Call original handler
            return original_handle_private(*args, **kwargs)
        except Exception as e:
            print(f'❌ Error in private handler: {e}')
    
    # Replace handlers
    api._handle_public_event = capture_public_event
    api._handle_private_event = capture_private_event
    
    try:
        # Connect and initialize
        await api.login()
        await api.initialize_data()
        
        print(f'✅ Connected! Monitoring for 120 seconds...')
        print('-' * 70)
        
        # Monitor for 2 minutes
        end_time = time.time() + 120
        last_stats_time = time.time()
        
        while time.time() < end_time:
            await asyncio.sleep(1)
            
            # Show periodic stats every 20 seconds
            if time.time() - last_stats_time > 20:
                elapsed = time.time() - monitor.start_time
                rate = monitor.message_count / elapsed if elapsed > 0 else 0
                print(f'\n📊 [STATS at {elapsed:.1f}s] Total: {monitor.message_count} | Market: {monitor.market_updates} | Private: {monitor.private_updates} | Rate: {rate:.2f}/sec')
                last_stats_time = time.time()
        
        # Final summary
        elapsed = time.time() - monitor.start_time
        print('\n' + '=' * 70)
        print('🏁 MONITORING COMPLETE')
        print(f'⏱️  Duration: {elapsed:.1f} seconds')
        print(f'📊 Total Messages: {monitor.message_count}')
        print(f'📈 Market Updates: {monitor.market_updates}')
        print(f'💰 Private Updates: {monitor.private_updates}')
        print(f'🔄 Average Rate: {monitor.message_count/elapsed:.2f} messages/sec' if elapsed > 0 else 'N/A')
        
        if monitor.message_count == 0:
            print('\n⚠️  WARNING: No WebSocket messages received!')
            print('   This could indicate:')
            print('   • WebSocket connection issues')
            print('   • No active market activity during monitoring')
            print('   • Authentication/subscription problems')
        
    except KeyboardInterrupt:
        elapsed = time.time() - monitor.start_time
        print(f'\n\n🛑 Monitoring stopped by user after {elapsed:.1f} seconds')
        print(f'📊 Messages captured: {monitor.message_count}')
    except Exception as e:
        print(f'\n❌ Error during monitoring: {e}')
    finally:
        await api.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
