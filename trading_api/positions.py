from .base import make_request

def get_all_open_positions(ticker:str):
    """
    Retrieves all open positions
    freq: 1req / 1s
    """
    """
    query = {
      "ticker": "AAPL_US_EQ"
    }
    """
    url_ending = "equity/positions"
    method = "GET"

    query = {
        "ticker": ticker
    }

    return make_request(method, url_ending, payload=query)
