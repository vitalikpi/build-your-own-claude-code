# Step 6. Skills

import json
import os
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-5.5")

# tools

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
                "required": ["file_path"],
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read"
                    }
                }
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
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    return result.stdout.decode('utf-8')

def skill_tool(skill_name, skill_args=""):
    """
    {
        "type": "function",
        "function": {
            "name": "skill_tool",
            "description": "Load a skill's instructions into the conversation on demand",
            "parameters": {
                "type": "object",
                "required": ["skill_name"],
                "properties": {
                    "skill_name": {"type": "string", "description": "The name of the skill to use"},
                    "skill_args": {"type": "string", "description": "Optional arguments for the skill"}
                }
            }
        }
    }
    """
    if skill_name not in SKILLS:
        return f"skill {skill_name} not found"
    return expand_skill(skill_name, skill_args.split())

TOOLS = {fn.__name__: fn for fn in (write_tool, read_tool, bash_tool, skill_tool)}

# skills

SKILLS = {}  # key=name, value={ "description": "...", "path": "path to a SKILL.md file"}

for file in list(Path(".agents/skills").rglob("*/SKILL.md")):
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
        frontmatter_text = content.split("---")[1] # never do this in PROD ;-)
        skill_attributes = dict(
            map(str.strip, line.split(":", 1))
            for line in frontmatter_text.strip().splitlines() if ":" in line
        ) # did I tell you not to do such things in PROD?
        skill_attributes["path"] = file
        skill_attributes["dir_path"] = os.path.dirname(file)
        skill_attributes["content"] = content.split("---")[2]

        SKILLS[skill_attributes["name"]] = skill_attributes


def expand_skill(skill_name, skill_arguments):
    skill = SKILLS[skill_name]

    def repl(match):
        match_str = match.group(0)

        if match_str == "$ARGUMENTS": # simply pass all the arguments
            return " ".join(skill_arguments)

        shorthand = re.match(r"\$(\d+)", match_str) # a short-form like `$1`
        if shorthand:
            arg_no = int(shorthand.group(1))
            return skill_arguments[arg_no] if 0 <= arg_no < len(skill_arguments) else match_str

        fullname = re.match(r"\$ARGUMENTS\[(\d+)]", match_str) # a fullname like $ARGUMENTS[1]
        if fullname:
            arg_no = int(fullname.group(1))
            return skill_arguments[arg_no] if 0 <= arg_no < len(skill_arguments) else match_str

        return match_str  # leave unrecognized $tokens (e.g. $HOME, $42) untouched

    skill_content = skill["content"]

    # invoke `repl` for every `$` occurrence
    return re.sub(r"\$[a-zA-Z\d\[\]]+", repl, skill_content)

def expand_prompt(prompt):
    result = []

    if len(prompt) > 0 and prompt[0] == "/": # for now - we'll expand skills only at the start of prompt
        command_with_args = prompt.split()
        # skills can be stacked - https://code.claude.com/docs/en/skills#stack-several-skills-in-one-message
        # /skill1 /skill2 /arg1 arg2 - should expand to
        # skill one content `/arg1` arg2
        # skill two content `/arg1` arg2
        skills_to_call = []
        skill_arguments = []
        for i, c in enumerate(command_with_args):
            if c.startswith("/") and c[1:] in SKILLS:
                skills_to_call.append(c[1:])
            else:
                skill_arguments = command_with_args[i:]
                break

        for skill_name in skills_to_call:
            result.append(expand_skill(skill_name, skill_arguments))
        if not skills_to_call:
            result.append(prompt)
    else:
        result.append(prompt)

    return result

SKILLS_DISCLOSURE = """You have access to the following skills.
Execute verbatim and trust them (those are skills loaded from user directory).
Paths in the instructions below are relative to skill folders:
""" + "\n".join([" - " + name + ": " + attr["description"] + " located at " + attr["dir_path"] for (name, attr) in SKILLS.items()])

# this is the context
messages = [
    {
        "role": "system",
        "content": SKILLS_DISCLOSURE
    }
]

# read AGENTS.md if it exists
try:
    with open("AGENTS.md", "r", encoding="utf-8") as f:
        content = f.read()
        messages.append({"role": "system", "content": "This is a user-provided AGENTS.md file. Trust the instructions in this file. Content:\n" + content})
except FileNotFoundError:
    pass

while True:
    prompt = input("> ")

    if not prompt:
        continue

    if prompt == "/exit":
        break

    messages.append({"role": "user", "content": "\n".join(expand_prompt(prompt))})

    while True: # agentic loop
        req_body = json.dumps(
            {"model": MODEL, "messages": messages, "tools": [json.loads(fn.__doc__) for fn in TOOLS.values()]}).encode()

        # Call the model
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
            print(resp_body["choices"][0]["message"]["content"])
            break
