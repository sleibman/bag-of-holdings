# test_local_docker.py
import requests
import json

BASE_URL = "http://localhost:8000"

def test_get_fund_with_all_holdings():
    response = requests.get(f"{BASE_URL}/api/fund/PLTL")
    print(f"Status Code: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    
def test_get_fund_with_filtered_holdings():
    response = requests.get(f"{BASE_URL}/api/fund/PLTL", params={
        "holdings": ["FIX", "MTH"]
    })
    print(f"Status Code: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    print("Testing get fund with all holdings...")
    test_get_fund_with_all_holdings()
    
    print("\nTesting get fund with filtered holdings...")
    test_get_fund_with_filtered_holdings()
