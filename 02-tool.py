# Step 2. Tools. Delegate LLm a job to do

import json
import os
from urllib.request import Request, urlopen

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-4.5")

# This is a simple tool the model can use to write files
# The docstring describes the tool to the model
def write_tool(file_path, content):
    """
    {
        "type": "function",
        "function": {
            "name": "write_tool",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "required": ["file_path", "content"],
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path of the file to write to"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file"
                    }
                }
            }
        }
    }
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

# Tell the LLM to do something on machine
messages = [
    {"role": "user", "content": "Write the answer to the Ultimate Question of Life, the Universe, and Everything to a file named `meaning.txt`"},
]
# Note the new key - tools
req_body = json.dumps({"model": MODEL, "messages": messages, "tools": [json.loads(write_tool.__doc__)]}).encode()

# Call LLM
req = Request(
    f"{BASE_URL}/chat/completions",
    data=req_body,
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json" }
)
with urlopen(req) as resp:
    # get the response back
    resp_body = json.loads(resp.read())

# When model have tools it can respond two ways
# 1. call a tool
# 2. message you back
message = resp_body["choices"][0]["message"]
if message.get("tool_calls"):
    for tool_call in message["tool_calls"]:
        args = json.loads(tool_call["function"]["arguments"])
        write_tool(args["file_path"], args["content"])
        print(f"wrote {args['file_path']}")
else:
    print(message["content"])