#!/usr/bin/env python3
"""
Philips Heater CoAP Debug Test Script

This script tests connectivity to a Philips heater and displays device information.
Useful for debugging connection issues before setting up the Home Assistant integration.

Usage:
    python debug_heater_test.py <IP_ADDRESS>
    
Example:
    python debug_heater_test.py 192.168.1.100
"""

import sys
import asyncio
import logging
from typing import Any

try:
    from aioairctrl import CoAPClient
except ImportError:
    print("Error: aioairctrl library not installed")
    print("Install it with: pip install aioairctrl==0.2.5")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title: str = "") -> None:
    """Print a formatted separator."""
    if title:
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print('=' * 80)
    else:
        print('=' * 80)


def format_value(key: str, value: Any) -> str:
    """Format a key-value pair for display."""
    return f"  {key:25s} : {value}"


async def test_connection(ip_address: str) -> bool:
    """Test connection to Philips heater."""
    
    print_separator("PHILIPS HEATER CoAP CONNECTION TEST")
    print(f"\nTarget IP Address: {ip_address}")
    print(f"Protocol: CoAP (UDP port 5683)")
    
    client = None
    success = False
    
    try:
        # Step 1: Create CoAP client
        print_separator("Step 1: Creating CoAP Client")
        print("Attempting to create CoAP client connection...")
        
        client = await asyncio.wait_for(
            CoAPClient.create(ip_address),
            timeout=15
        )
        
        print("✓ CoAP client created successfully")
        
        # Step 2: Get device status
        print_separator("Step 2: Retrieving Device Status")
        print("Fetching device status and information...")
        
        status, max_age = await asyncio.wait_for(
            client.get_status(),
            timeout=15
        )
        
        print("✓ Status retrieved successfully")
        
        # Step 3: Display device information
        print_separator("Step 3: Device Information")
        
        print("\n📋 Basic Information:")
        print(format_value("Name", status.get("D01S03", status.get("name", "Unknown"))))
        print(format_value("Type", status.get("D01S04", "Unknown")))
        print(format_value("Model ID", status.get("D01S05", status.get("modelid", "Unknown"))))
        print(format_value("Product ID", status.get("ProductId", "Unknown")))
        print(format_value("Device ID", status.get("DeviceId", "Unknown")))
        
        print("\n🔧 Firmware/Version Information:")
        print(format_value("Software Version", status.get("D01S12", "Unknown")))
        print(format_value("WiFi Version", status.get("WifiVersion", "Unknown")))
        print(format_value("Max Age", f"{max_age}s"))
        print(format_value("Runtime", f"{status.get('Runtime', 0) / 1000:.1f}s"))
        print(format_value("RSSI", f"{status.get('rssi', 0)} dBm"))
        print(format_value("Free Memory", f"{status.get('free_memory', 0)} bytes"))
        
        print("\n🌡️ Current Status:")
        print(format_value("Power (D03102)", "ON" if status.get("D03102") == 1 else "OFF"))
        print(format_value("Display Brightness (D03105)", f"{status.get('D03105', 0)}%"))
        
        if "D03224" in status:
            temp_c = status["D03224"] / 10
            print(format_value("Current Temperature (D03224)", f"{temp_c:.1f}°C (raw: {status['D03224']})"))
        if "D0310E" in status:
            print(format_value("Target Temperature (D0310E)", f"{status['D0310E']}°C"))
        if "D0313F" in status:
            heating_status = status["D0313F"]
            status_desc = {
                0: "fan/idle",
                65: "heating high",
                66: "heating low",
                67: "heating medium",
                -16: "auto idle"
            }.get(heating_status, "unknown")
            print(format_value("Heating Status (D0313F)", f"{heating_status} ({status_desc})"))
        if "D0310A" in status:
            mode = status["D0310A"]
            mode_desc = {1: "fan", 2: "circulation", 3: "heating"}.get(mode, "unknown")
            print(format_value("Mode (D0310A)", f"{mode} ({mode_desc})"))
        if "D0310C" in status:
            intensity = status["D0310C"]
            intensity_desc = {
                0: "auto",
                65: "high",
                66: "low",
                -127: "fan only"
            }.get(intensity, "unknown")
            print(format_value("Heating Intensity (D0310C)", f"{intensity} ({intensity_desc})"))
        if "D0310D" in status:
            print(format_value("Fan Speed (D0310D)", status["D0310D"]))
        if "D03106" in status:
            print(format_value("Child Lock (D03106)", "ON" if status["D03106"] == 1 else "OFF"))
        if "D0320F" in status:
            osc = status["D0320F"]
            osc_desc = {0: "off", 17222: "on (command)", 17920: "on (active)"}.get(osc, "unknown")
            print(format_value("Oscillation (D0320F)", f"{osc} ({osc_desc})"))
        if "D03180" in status:
            print(format_value("Timer (D03180)", f"{status['D03180']} minutes" if status['D03180'] > 0 else "OFF"))
        
        print("\n📊 All Status Data:")
        for key, value in sorted(status.items()):
            print(format_value(key, value))
        
        # Step 4: Test observe capability
        print_separator("Step 4: Testing CoAP Observe (Real-time Updates)")
        print("Attempting to observe status updates for 5 seconds...")
        print("(This tests if real-time push updates work)\n")
        
        update_count = 0
        try:
            async def observe_test():
                nonlocal update_count
                async for updated_status in client.observe_status():
                    update_count += 1
                    print(f"  Update #{update_count} received at {asyncio.get_event_loop().time():.2f}s")
                    if update_count >= 3:  # Stop after 3 updates or timeout
                        break
            
            await asyncio.wait_for(observe_test(), timeout=5)
            print(f"\n✓ Observe working! Received {update_count} updates")
            
        except asyncio.TimeoutError:
            if update_count > 0:
                print(f"\n✓ Observe working! Received {update_count} update(s)")
            else:
                print("\n⚠ No observe updates received (this is OK, device may not push frequent updates)")
        
        # Success!
        print_separator("✅ CONNECTION TEST SUCCESSFUL")
        print("\n🎉 All tests passed!")
        print("\nNext steps:")
        print("  1. Add this integration in Home Assistant")
        print("  2. Go to Settings → Devices & Services → Add Integration")
        print("  3. Search for 'Philips Heater (CoAP)'")
        print(f"  4. Enter IP address: {ip_address}")
        
        success = True
        
    except asyncio.TimeoutError:
        print_separator("❌ CONNECTION TEST FAILED")
        print("\n⏱️  Timeout Error")
        print("\nPossible causes:")
        print("  • Device is not reachable on the network")
        print("  • IP address is incorrect")
        print("  • Firewall blocking UDP port 5683")
        print("  • Device is powered off or in standby mode")
        print("\nTroubleshooting:")
        print(f"  1. Ping the device: ping {ip_address}")
        print("  2. Check device is on the same network/VLAN")
        print("  3. Verify IP address in Philips app")
        print("  4. Check firewall/router settings for UDP port 5683")
        
    except ConnectionRefusedError:
        print_separator("❌ CONNECTION TEST FAILED")
        print("\n🚫 Connection Refused")
        print("\nThe device actively refused the connection.")
        print("This usually means:")
        print("  • Wrong IP address")
        print("  • Device doesn't support CoAP protocol")
        print("  • Device firmware is incompatible")
        
    except Exception as err:
        print_separator("❌ CONNECTION TEST FAILED")
        print(f"\n💥 Unexpected Error: {type(err).__name__}")
        print(f"   {err}")
        print("\nDebug information:")
        logger.exception("Full error details:")
        
    finally:
        # Cleanup
        if client:
            print("\n🔌 Closing connection...")
            try:
                await client.shutdown()
                print("✓ Connection closed cleanly")
            except Exception as err:
                print(f"⚠ Error during cleanup: {err}")
    
    print_separator()
    return success


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python debug_heater_test.py <IP_ADDRESS>")
        print("\nExample:")
        print("  python debug_heater_test.py 192.168.1.100")
        sys.exit(1)
    
    ip_address = sys.argv[1]
    
    # Validate IP format (basic check)
    parts = ip_address.split('.')
    if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        print(f"Error: '{ip_address}' is not a valid IP address")
        sys.exit(1)
    
    # Run the test
    try:
        success = asyncio.run(test_connection(ip_address))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
