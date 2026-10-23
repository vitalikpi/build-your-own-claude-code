# Step 3. Let the model know the outcome.

import json
import os
from urllib.request import Request, urlopen

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "cohere/north-mini-code:free")

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

TOOLS = [write_tool]

# Tell the LLM to do something on machine
messages = [
    {"role": "user", "content": "Write the answer to the Ultimate Question of Life, the Universe, and Everything to a file named `meaning.txt`. If file write is successful - respond 'Don't Panic'"},
]

def ask(messages):
    req_body = json.dumps({"model": MODEL, "messages": messages, "tools": [json.loads(fn.__doc__) for fn in TOOLS]}).encode()

    # Call LLM
    req = Request(
        f"{BASE_URL}/chat/completions",
        data=req_body,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json" }
    )
    with urlopen(req) as resp:
        # get the response back
        return json.loads(resp.read())


# Core lesson here - model does not remember anything
# it does not remember what it told you (response) or asked to do (tool call)
# it does not remember what you asked for
# every call is like asking Einstein who has severe amnesia
# so our two-step instruction will only execute write but will not have a chance to proceed
# let's fix it by making an "agentic loop"

while True:
    resp_body = ask(messages)
    message = resp_body["choices"][0]["message"]
    messages.append(message)  # "I (the model) said this / asked for these tools"

    # The above command look obvious, but it was not that obvious at first.
    # The LLM should now what it is asked for and get a confirmation or the result back.
    # This and tool result keep "hallucinations" at bay and makes model more "honest".
    # See: ReAct: Synergizing Reasoning and Acting in Language Models

    if message.get("tool_calls"):
        for tool_call in message["tool_calls"]:
            args = json.loads(tool_call["function"]["arguments"])
            write_tool(args["file_path"], args["content"])

            messages.append({  # "here's what that call produced"
                "role": "tool",
                "tool_call_id": tool_call["id"],  # must match the call's id
                "content": f"wrote {args['file_path']}",
            })
    else:
        print(message["content"])
        break # stop the agentic loop - the model achieved what it was asked for