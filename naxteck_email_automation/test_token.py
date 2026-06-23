import os
import requests
from dotenv import load_dotenv

# Load .env
load_dotenv(override=True)
import os
print("ENV TOKEN:", os.environ.get("META_ACCESS_TOKEN"))

token = os.getenv("META_ACCESS_TOKEN", "").strip()

print("=" * 50)
print("TOKEN FOUND :", bool(token))
print("TOKEN LENGTH:", len(token))
print("TOKEN START :", token[:20])
print("=" * 50)

url = "https://graph.facebook.com/v23.0/me"

response = requests.get(
    url,
    params={
        "access_token": token
    }
)

print("STATUS CODE:", response.status_code)
print("RESPONSE:")
print(response.text)