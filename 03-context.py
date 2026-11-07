# Step 3. Context

import json
import os
from urllib.request import Request, urlopen

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-5.5")

# this is the context
messages = []

while True:
    prompt = input("> ")

    if not prompt:
        continue

    if prompt == "/exit":
        break

    messages.append({"role": "user", "content": prompt})

    req_body = json.dumps({"model": MODEL, "messages": messages}).encode()

    # Call the model
    req = Request(
        f"{BASE_URL}/chat/completions",
        data=req_body,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )
    with urlopen(req) as resp:
        # get the response back
        resp_body = json.loads(resp.read())

    # here is our response
    model_response = resp_body["choices"][0]["message"]["content"]
    print(model_response)

    # add the model response back to the context
    messages.append({"role": "assistant", "content": model_response})
