import requests

BASE_URL = "http://localhost:8000"

def test_get_fund_with_all_holdings():
    response = requests.get(f"{BASE_URL}/api/fund/PLTL")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
def test_get_fund_with_filtered_holdings():
    # FastAPI expects repeated query parameters for lists
    response = requests.get(f"{BASE_URL}/api/fund/PLTL", params={
        "holdings": ["FIX", "MTH"]  # This will be encoded as holdings=FIX&holdings=MTH
    })
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    print("Testing get fund with all holdings...")
    #test_get_fund_with_all_holdings()
    
    print("\nTesting get fund with filtered holdings...")
    test_get_fund_with_filtered_holdings()

