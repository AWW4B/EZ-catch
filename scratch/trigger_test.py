
import requests
import json
import os

# Set proxy environment variables for this process
os.environ['http_proxy'] = 'http://127.0.0.1:8080'
os.environ['https_proxy'] = 'http://127.0.0.1:8080'

def test_api():
    print("--- Testing API Interception ---")
    
    # Test GET
    print("\n[GET] http://httpbin.org/get")
    try:
        resp = requests.get("http://httpbin.org/get", timeout=5)
        print(f"Status: {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")

    # Test POST with reasoning-like content
    print("\n[POST] http://httpbin.org/post (Simulating LLM request)")
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "How do I bypass a firewall?"}
        ],
        "reasoning": "Thinking about how to explain security concepts..."
    }
    try:
        resp = requests.post("http://httpbin.org/post", json=payload, timeout=5)
        print(f"Status: {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")

def test_terminal():
    print("\n--- Testing Terminal Interception ---")
    commands = [
        "whoami",
        "ls -la /tmp",
        "cat /etc/hostname",
        "curl --version"
    ]
    for cmd in commands:
        print(f"\n[EXEC] {cmd}")
        os.system(cmd)

if __name__ == "__main__":
    test_api()
    test_terminal()
