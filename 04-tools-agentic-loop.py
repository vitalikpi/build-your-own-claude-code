# Step 3. Hook up the tools

import json
import os
import subprocess
from urllib.request import Request, urlopen

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", default="cohere/north-mini-code:free")

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
    return f"written {file_path}"

def read_tool(file_path):
    """
    {
      "type": "function",
      "function": {
        "name": "read_tool",
        "description": "Read and return the contents of a file",
        "parameters": {
          "type": "object",
          "properties": {
            "file_path": {
              "type": "string",
              "description": "The path to the file to read"
            }
          },
          "required": ["file_path"]
        }
      }
    }
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content

def bash_tool(command):
    """
    {
        "type": "function",
        "function": {
            "name": "bash_tool",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute"
                    }
                }
            }
        }
    }
    """
    result = subprocess.run(command, stdout=subprocess.PIPE, shell=True)
    return result.stdout.decode('utf-8')

# Assemble JSON array.
TOOLS = {fn.__name__: fn for fn in (write_tool, read_tool, bash_tool)}

# this is the context
messages = []

while True:
    prompt = input("> ")

    if prompt == "/exit":
        break

    messages.append({"role": "user", "content": prompt})

    while True:
        req_body = json.dumps(
            {"model": MODEL, "messages": messages, "tools": [json.loads(fn.__doc__) for fn in TOOLS.values()]}).encode()

        # Call LLM
        req = Request(
            f"{BASE_URL}/chat/completions",
            data=req_body,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        )
        with urlopen(req) as resp:
            # get the response back
            resp_body = json.loads(resp.read())

        message = resp_body["choices"][0]["message"]
        messages.append(message)  # "I (the model) said this / asked for these tools"


        if message.get("tool_calls"):
            print(f"🔁 {message["content"]}")
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])

                print(f"🔨 {tool_name}")

                # select the tool the model named
                tool = TOOLS.get(tool_name)
                # a tool error becomes feedback, not a crash - the model sees it and self-corrects
                try:
                    result = tool(**args) if tool else f"tool {tool_name} not found"
                except Exception as e:
                    result = f"error running {tool_name}: {e!r}"

                messages.append({  # "here's what that call produced"
                    "role": "tool",
                    "tool_call_id": tool_call["id"],  # must match the call's id
                    "content": str(result),
                })
        else:
            model_response = resp_body["choices"][0]["message"]["content"]
            print(model_response)
            # add the model response back to the context
            messages.append({"role": "assistant", "content": model_response})
            break