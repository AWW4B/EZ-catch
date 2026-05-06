
import requests
import json
import os

# Set proxy environment variables for this process
os.environ['http_proxy'] = 'http://127.0.0.1:8080'
os.environ['https_proxy'] = 'http://127.0.0.1:8080'

def test_api():
    print("--- Testing API Interception (Targeting Localhost) ---")
    
    # Test POST with reasoning-like content targeting localhost (which is in TARGET_DOMAINS)
    print("\n[POST] http://localhost:8000/health (Simulating LLM request)")
    payload = {
        "model": "gpt-4-test",
        "messages": [
            {"role": "user", "content": "Tell me a secret."}
        ],
        "reasoning": "<thinking>I should probably not tell any real secrets, but I can make one up.</thinking> I have no secrets."
    }
    # Note: /health might not accept POST, but the interceptor should still see it.
    try:
        resp = requests.post("http://localhost:8000/health", json=payload, timeout=5)
        print(f"Status: {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
