class AlpacaConfig:
    API_KEY = 'AKRAINZ32JOP7FJYVIRL'
    SECRET_KEY = 'IoFuFohIVySK4gOo3zVNUYBmB9QioPqDfn5YuiWS'

    """ If no endpoint is specified, the following paper trading
    endpoint will be used by default"""
    ENDPOINT = "https://paper-api.alpaca.markets"

    VERSION = "v2"  # By default v2
    USE_POLYGON = False  # By dfault set to False


class InteractiveBrokersConfig:
    SOCKET_PORT = 7497
    CLIENT_ID = "your Master API Client ID three digit number"
    IP = "127.0.0.1"


class AlphaVantageConfig:
    API_KEY = "YOUR ALPHA VANTAGE API KEY"
