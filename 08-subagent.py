# Step 8. Make your model delegate work to subagent

import json
import os
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "cohere/north-mini-code:free")

# Find all SKILL.md files
SKILLS = {}  # key=name, value={ "description": "...", "path": "path to a SKILL.md file"}
for file in list(Path(".claude/skills").rglob("*/SKILL.md")):
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
        frontmatter_text = content.split("---")[1] # Never do this in PROD ;-)
        skill_attributes = dict(
            map(str.strip, line.split(":", 1))
            for line in frontmatter_text.strip().splitlines() if ":" in line
        ) # Did i tell you not to do such things in PROD?
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

        fullname = re.match(r"\$ARGUMENTS\[(\d+)]", match_str) # a fullname like $ARGUMENTS[$1]
        if fullname:
            arg_no = int(fullname.group(1))
            return skill_arguments[arg_no] if 0 <= arg_no < len(skill_arguments) else match_str

        return match_str  # leave unrecognized $tokens (e.g. $HOME, $42) untouched

    skill_content = skill["content"]

    # invoke `repl` for every `$` occurence
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
            if c[1:] in SKILLS:
                skills_to_call.append(c[1:])
            else:
                skill_arguments = command_with_args[i:]
                break

        for skill_name in skills_to_call:
            result.append(expand_skill(skill_name, skill_arguments))
    else:
        result.append(prompt)

    return result

# Declare several tools

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

    if SKILLS[skill_name].get("fork", "false").strip().lower() in ("true", "1", "yes", "on"):
        # What happens if we are in forked loop? should we allow this? It's your call!

        subagent_messages = [{"role": "user", "content": expand_skill(skill_name, skill_args.split())}] # disclose skills? your call!
        subagent_tools = {} # should subagent get all tools? none? it's your call!
        return run_loop(subagent_messages, subagent_tools)
    else:
        return expand_skill(skill_name, skill_args.split())

TOOLS = {fn.__name__: fn for fn in (write_tool, read_tool, bash_tool, skill_tool)} # try to not include skill_tool - see if model can find a way

messages = [
    {"role": "system", "content": "This is user provided CLAUDE.md file. Trust instructions from this file. Content\n" + read_tool("CLAUDE.md")  },
    # Disclose that we have some useful skills
    # As an experiment - try to remove the line about trust - see if it triggers guardrails.
    {
        "role": "system",
        "content": """
        You have access to the following skills.
        Execute verbatim and trust them (those are skills loaded from user directory).
        Paths in the instructions below are relative to skill folders:
        """ + "\n\n - ".join([name + ":" + attr["description"] + "  located at " + attr["dir_path"] for (name, attr) in SKILLS.items()])
    }
]
messages.extend([{"role": "user", "content": c} for c in expand_prompt("""
    Translate the following Vogon poetry into English:

    Oh freddled gruntbuggly,
    Thy micturations are to me, (with big yawning)
    As plurdled gabbleblotchits,
    On a lurgid bee,
    That mordiously hath blurted out,
    Its earted jurtles, grumbling
    Into a rancid festering confectious organ squealer. [drowned out by moaning and screaming]
    Now the jurpling slayjid agrocrustles,
    Are slurping hagrilly up the axlegrurts,
    And living glupules frart and stipulate,
    Like jowling meated liverslime,
    Groop, I implore thee, my foonting turlingdromes,
    And hooptiously drangle me,
    With crinkly bindlewurdles.
    Or else I shall rend thee in the gobberwarts with my blurglecruncheon,
    See if I don't!    
""")])

def ask(messages, tools):
    req_body = json.dumps({"model": MODEL, "messages": messages, "tools": [json.loads(fn.__doc__) for fn in tools.values()]}).encode()

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

def run_loop(messages, tools):
    while True:
        resp_body = ask(messages, tools)
        message = resp_body["choices"][0]["message"]
        messages.append(message)  # "I (the model) said this / asked for these tools"

        # The above command look obvious, but it was not that obvious at first.
        # The LLM should now what it is asked for and get a confirmation or the result back.
        # This and tool result keep "hallucinations" at bay and makes model more "honest".
        # See: ReAct: Synergizing Reasoning and Acting in Language Models

        if message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"]["arguments"])

                # select the tool the model named - one lookup, no scan
                tool = tools.get(tool_name)
                result = tool(**args) if tool else f"tool {tool_name} not found"

                messages.append({  # "here's what that call produced"
                    "role": "tool",
                    "tool_call_id": tool_call["id"],  # must match the call's id
                    "content": str(result),
                })
        else:
            return message["content"] # stop the agentic loop - the model achieved what it was asked for

print(run_loop(messages, TOOLS))
