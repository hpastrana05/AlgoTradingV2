import requests
from config import API_LINK, API_KEY, API_SECRET

GET_HEADER = {"Authorization": API_KEY}
POST_HEADER = {"Content-Type": "application/json", "Authorization": API_KEY}
AUTHENTICATION = (API_KEY, API_SECRET)

def make_request(method, endpoint, params=None, payload=None):
    url = f"{API_LINK}{endpoint}"
    
    if method == "POST":
        headers = POST_HEADER
    else:        
        headers = GET_HEADER

    response = requests.request(method, url, headers=headers, params=params, json=payload, auth=AUTHENTICATION)
    
    if response.status_code != 200:
        print(f"Error en {endpoint}: {response.status_code} - {response.text}")
        return "ERROR"
    return response.json()