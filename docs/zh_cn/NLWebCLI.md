# NLWeb 配置 CLI 指南

## 介绍

NLWeb 提供了一个命令行界面 （CLI） 来简化应用程序的配置、测试和执行。CLI 可帮助用户浏览各种配置步骤，确保在运行应用程序之前正确设置所有必要的环境变量和设置。

## 开始

要设置 `nlweb` 命令行界面，您需要先获取设置脚本：

```bash
source setup.sh
```

这将暂时将命令添加到您的 `nlweb` PATH 中，并创建一个别名以便于使用。

### NLWeb CLI 具有以下几个优势：

1. **简化配置**：CLI 指导用户选择和配置 LLM 提供程序和检索终端节点，自动检测需要设置哪些环境变量。

2. **首选项管理**：CLI 会记住用户首选项，例如首选 LLM 提供程序和检索终端节点，并将其存储在配置文件中以备将来使用。

3. **环境验证**： 在运行主应用程序之前，CLI 可以检查与 Azure OpenAI、Snowflake 或其他服务的连接，确保一切都已正确配置。

4. **交互式设置**：CLI 提供了一个交互式过程来选择选项并输入必要的凭据，而不是要求用户手动编辑配置文件。

5. **一致的环境**：CLI 确保所有必需的环境变量都已正确设置并保留在 `.env` 文件中。

## CLI 命令

 `nlweb` CLI 提供以下命令：

| 命令 | 描述 |
|---------|-------------|
| `init`  | 配置 LLM 提供程序和检索终端节点 |
| `init-python` | 设置 Python 虚拟环境并安装依赖项 |
| `check` | 验证所选配置和环境变量的连接 |
| `app`   | 运行 Web 应用程序 |
| `run`   | 端到端流：按顺序运行 `init`、 `check` `app`  和|
| `data-load` | 从具有指定站点名称的 RSS 源 URL 加载数据 |

### 常见标志

| 旗 | 描述 |
|------|-------------|
| `-h`、 `--help` | 显示帮助信息 |
| `-d`、 `--debug` | 启用调试输出以进行故障排除 |

## 使用示例

### 完整的工作流程

有关配置、测试和运行应用程序的完整端到端工作流：

```bash
nlweb run
```

### 配置设置

要配置您的环境：

```bash
nlweb init
```

这将指导您选择 LLM 提供商（例如 Azure OpenAI、OpenAI、Anthropic 等）和检索终端节点（例如 Azure Vector Search、Qdrant、Snowflake Cortex 等）。然后，CLI 将提示您输入任何必需的 API 密钥或终端节点。

### 连接测试

要验证您的配置是否可以连接到所需的服务，请执行以下作：

```bash
nlweb check
```

这将运行连接测试，以确保您的环境变量设置正确，并且应用程序可以与所选服务通信。

### 运行应用程序

要启动 Web 应用程序：

```bash
nlweb app
```

## 配置文件

CLI 管理多个 YAML 配置文件：

- `code/config/config_llm.yaml`：LLM 提供程序配置
- `code/config/config_retrieval.yaml`：检索终端节点配置

这些文件存储的设置包括：
- 首选提供商/终端节点
- 型号名称和配置
- API 密钥和终端节点的环境变量名称

## 环境变量

CLI 帮助管理应用程序所需的环境变量，并将其存储在 `.env`.这些通常包括：

- 各种 LLM 提供商（OpenAI、Azure OpenAI、Anthropic 等）的 API 密钥
- 服务终结点（Azure 矢量搜索、Qdrant 等）
- 特定于每个提供商或终端节点的其他配置选项

### 预先存在的环境变量

如果您的 shell 中已设置环境变量，则 CLI 将使用该值，并且不会提示您再次输入。这在以下情况下非常有用：

- 您在 shell 配置文件中设置了环境变量
- 您正在使用具有预配置密钥的 CI/CD 管道
- 您希望编写配置过程的脚本

例如，如果您已经 `AZURE_OPENAI_API_KEY` 在终端会话中设置了：

```bash
export AZURE_OPENAI_API_KEY="your-api-key-here"
nlweb init
```

CLI 将检测此值，并在设置过程中跳过提示。

## 高级用法

### 切换提供商或终端节点

您可以随时通过运行以下命令在不同的 LLM 提供程序或检索终端节点之间切换：

```bash
nlweb init
```

CLI 将更新配置文件中的首选项，并提示输入任何其他必需的环境变量。

### 调试

遇到问题时，请运行带有 debug 标志的命令：

```bash
nlweb run -d
```

这提供了详细的日志记录信息，可帮助识别配置问题。

### Python 虚拟环境设置

要设置 Python 虚拟环境，请执行以下作：

```bash
nlweb init-python
```

这将：
1. 在目录中`venv`创建 Python 虚拟环境 
2. 从 安装所有必需的依赖项 `requirements.txt`

**注意**： `init-python` 从 CLI 运行时，虚拟环境将仅在脚本的执行上下文中激活。命令完成后，您的 shell 将不会保留在已激活的虚拟环境中。

要在当前 shell 会话中激活虚拟环境，您需要获取激活脚本：

```bash
source venv/bin/activate
```

或者，如果您需要一步设置和使用环境，则可以使用：

```bash
nlweb init-python && source venv/bin/activate
```

这将设置 Python 环境并在当前 shell 会话中激活它。

### 数据加载

要从 RSS 源加载数据：

```bash
nlweb data-load
```

此命令将提示您：
- 用于加载数据的 RSS URL
- 加载的数据的站点名称
