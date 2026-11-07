# Step 2. Chat

import json
import os
from urllib.request import Request, urlopen

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", default="cohere/north-mini-code:free")

while True:
    prompt = input("> ")

    if prompt == "/exit":
        break

    # This is what we ask model to do
    messages = [
        {"role": "user", "content": prompt}
    ]
    req_body = json.dumps({"model": MODEL, "messages": messages}).encode()

    # Call LLM
    req = Request(
        f"{BASE_URL}/chat/completions",
        data=req_body,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json" }
    )
    with urlopen(req) as resp:
        # get the response back
        resp_body = json.loads(resp.read())

    # here is our response
    print(resp_body["choices"][0]["message"]["content"])