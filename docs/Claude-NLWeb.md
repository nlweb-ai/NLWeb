# Setting up Claude to talk to NLWeb
-----------------------------------------------------------------

## Getting Started

Since NLWeb includes an MCP server by default, you can configure Claude for Desktop to talk to NLWeb!

## Prerequisites

Assumes you have [Claude for Desktop](https://claude.ai/download).  Currently this is only working on macOS.

## Setup Steps

1. If you do not already have it, install MCP:
```bash
pip install mcp
```

2. Next, configure your Claude MCP server.  If you don't have the config file already, you can create the file at the following locations

- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
# - Windows: %APPDATA%\Claude\claude_desktop_config.json

The default MCP JSON file looks like this for Mac, with changes in the comments:

```bash
{
  "mcpServers": {
    "filesystem": {                       # filesystem --> ask_nlw
      "command": "npx",                   # npx --> path of your myenv python file 
      "args": [
        "-y",                             # remove this line
        "@modelcontextprotocol/server-filesystem",   # replace with "<full path of ..NLWeb/code/chatbot_interface.py>",
        "/Users/username/Desktop",        # replace with "--server"
                                          # new line with "http://localhost:8000",
        "/Users/username/Downloads"       # replace with "--endpoint",
                                          # new line with "/mcp",
      ],
                                          # new line with "cwd": "<full path to NLWeb/Code>" 
    }
  }
}
```

This would look something like this:
```bash
{
  "mcpServers": {
    "ask_nlw": {
      "command": "Users/yourname/NLWeb/myenv/bin/python", 
      "args": [
        "Users/yourname/NLWeb/code/chatbot_interface.py",
        "--server",
        "http://localhost:8000",
        "--endpoint",
        "/mcp",
      ],
      "cwd": "Users/yourname/NLWeb/code" 
    }
  }
}
```

3.  From your code folder, enter your venv and start your NLWeb local server.  Make sure it is configured to access the data you would like to ask about from Claude.
```bash
source ../myenv/bin/activate
python app-file.py
```

4.  Open Claude Desktop. It should ask you to trust the 'ask_nlw' external connection if it is configured correctly.  After clicking yes and the welcome page appears, you should see 'ask_nlw' in the bottom right '+' options.  Select it to start a query.

![alt text](../images/Claude-ask_nlw-Option.png)

5.  Voilà! When you ask a question and want to query NLWeb, just type 'ask_nlw' in your prompt to Claude.  You'll notice that you also get the full JSON script for your results. Remember, you have to have your local NLWeb server started to use this option.