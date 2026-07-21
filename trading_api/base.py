import requests
import config


def make_request(method, endpoint, params=None, payload=None):
    """Call Trading212 using the currently selected demo/live credentials."""
    if not config.API_KEY or not config.API_SECRET:
        print(f"Error en {endpoint}: missing API credentials for current mode")
        return "ERROR"

    url = f"{config.API_LINK}{endpoint}"
    auth = (config.API_KEY, config.API_SECRET)

    if method == "POST":
        headers = {"Content-Type": "application/json", "Authorization": config.API_KEY}
    else:
        headers = {"Authorization": config.API_KEY}

    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=payload,
        auth=auth,
    )

    if response.status_code != 200:
        print(f"Error en {endpoint}: {response.status_code} - {response.text}")
        return "ERROR"
    return response.json()
