# 设置 Claude 与 NLWeb 对话
-----------------------------------------------------------------

## 开始

由于 NLWeb 默认包含一个 MCP 服务器，因此您可以配置 Claude for Desktop 以与 NLWeb 通信！

## 先决条件

假设您拥有 [Claude for Desktop](https://claude.ai/download)。这适用于 macOS 和 Windows。

## 设置步骤

1. 如果你还没有，请在你的 venv 中安装 MCP：
```bash
pip install mcp
```

2. 接下来，配置 Claude MCP 服务器。如果您还没有配置文件，可以在以下位置创建该文件：

- macOS 版本： `~/Library/Application Support/Claude/claude_desktop_config.json`
- 窗户： `%APPDATA%\Claude\claude_desktop_config.json`

默认的 MCP JSON 文件需要修改，如下所示：

### macOS 示例配置

```json
{
  "mcpServers": {
    "ask_nlw": {
      "command": "/Users/yourname/NLWeb/myenv/bin/python", 
      "args": [
        "/Users/yourname/NLWeb/code/chatbot_interface.py",
        "--server",
        "http://localhost:8000",
        "--endpoint",
        "/mcp"
      ],
      "cwd": "/Users/yourname/NLWeb/code" 
    }
  }
}
```

### Windows 示例配置

```json
{
  "mcpServers": {
    "ask_nlw": {
      "command": "C:\\Users\\yourusername\\NLWeb\\myenv\\Scripts\\python",
      "args": [
        "C:\\Users\\yourusername\\NLWeb\\code\\chatbot_interface.py",
        "--server",
        "http://localhost:8000",
        "--endpoint",
        "/mcp"
      ],
      "cwd": "C:\\Users\\yourusername\\NLWeb\\code"
    }
  }
}
```

> **注意：**对于 Windows 路径，您需要使用双反斜杠 （） `\\`来转义 JSON 中的反斜杠字符。

3. 从您的代码文件夹中，输入您的虚拟环境并启动 NLWeb 本地服务器。确保将其配置为访问您想向 Claude 询问的数据。

```bash
# On macOS
source ../myenv/bin/activate
python app-file.py

# On Windows
..\myenv\Scripts\activate
python app-file.py
```

4. 打开 Claude Desktop。如果配置正确，它应该要求您信任 'ask_nlw' 外部连接。单击“是”并出现欢迎页面后，您应该会在右下角的“+”选项中看到“ask_nlw”。选择它以启动查询。

![Claude ask_nlw 选项](../../images/Claude-ask_nlw-Option.png)

5. 瞧！当您提出问题并想查询 NLWeb 时，只需在 Claude 的提示符中键入 'ask_nlw' 即可。您会注意到，您还可以获得结果的完整 JSON 脚本。请记住，您必须让本地 NLWeb 服务器启动才能使用此选项。

## 故障 排除

如果您在 Claude 连接到 NLWeb 时遇到问题，您可以启用开发人员模式来帮助诊断问题：

### 在 Claude Desktop 中启用开发人员模式

1. 打开 Claude Desktop 应用程序
2. 菜单 -> 帮助 -> 启用开发人员模式
3. 重新启动 Claude Desktop 以应用调试设置

### 检查 Claude 日志文件

Claude 存储有关 MCP 连接的详细日志，这些日志可能有助于故障排除：

#### 日志文件位置
- **macOS：** `~/Library/Logs/Claude/`
- **Windows （窗口**）： `%APPDATA%\Claude\logs\`

#### 重要日志文件
- `mcp.log` - 包含有关 MCP 连接和连接失败的常规日志记录
- `mcp-server-ask_nlw.log` - 包含来自 NLWeb MCP 服务器的错误 （stderr） 日志记录

#### 查看日志文件
您可以使用以下命令查看最近的日志并实时监控它们：

```bash
# macOS/Linux
tail -n 20 -f ~/Library/Logs/Claude/mcp*.log

# Windows
type "%APPDATA%\Claude\logs\mcp*.log"
```

### 常见问题

- 如果 Claude 没有显示 'ask_nlw' 选项，请检查您的配置文件是否位于正确的位置和正确的格式
- 在尝试连接之前，请验证 NLWeb 服务器是否正在运行
- 确保你已经在你的 venv 中安装了 mcp
- 检查开发人员控制台是否存在连接错误或文件路径问题
- 确保配置中的所有文件路径都使用适用于您的作系统的正确格式
- 确保 Claude 桌面完全关闭（菜单 -> 文件 -> 退出）以读取对配置的更改

对于持续存在的问题，您可以尝试重新启动 NLWeb 服务器和 Claude Desktop 应用程序。