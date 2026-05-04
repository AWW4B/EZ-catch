"""
AI IDE CONTEXT:
This is the main entry point for the host agent. 
It boots the OS monitor thread and provides instructions for starting the mitmproxy interceptor.
"""
import threading
import sys
from interceptors.os_monitor import ArchAuditMonitor

def boot_os_monitor():
    try:
        monitor = ArchAuditMonitor()
        monitor.start_monitoring()
    except PermissionError:
        print("FATAL: OS Monitor requires sudo/root privileges to read audit logs on Arch Linux.")
        sys.exit(1)

if __name__ == "__main__":
    print("Initializing Agent Monitor Prototype...")
    
    # Run OS monitor in background
    os_thread = threading.Thread(target=boot_os_monitor, daemon=True)
    os_thread.start()
    
    print("\n--- INSTRUCTIONS ---")
    print("1. OS Monitoring is running.")
    print("2. To start the network reasoning interceptor, open a new terminal and run:")
    print("   mitmdump -s apps/agent/src/interceptors/network_proxy.py --set confdir=~/.mitmproxy")
    print("3. Ensure your AI agents have their HTTPS_PROXY set to localhost:8080")
    print("--------------------\n")
    
    try:
        while True:
            pass # Keep alive
    except KeyboardInterrupt:
        print("\nShutting down monitor.")