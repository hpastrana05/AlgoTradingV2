import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

IS_DEMO = True

API_VER = "api/v0/"
#LINKS
DEMO_LINK = f"https://demo.trading212.com/{API_VER}" 
LIVE_LINK = f"https://live.trading212.com/{API_VER}"

# API KEYS
if IS_DEMO:
    API_KEY=os.getenv("API_KEY_DEMO")
    API_SECRET=os.getenv("API_SECRET_DEMO")
    API_LINK = DEMO_LINK
else:
    API_KEY=os.getenv("API_KEY_LIVE")
    API_SECRET=os.getenv("API_SECRET_LIVE")
    API_LINK = LIVE_LINK



