# NLWeb Azure 设置指南
-----------------------------------------------------------------

## 开始

使用这些说明将 NLWeb 配置为在 Azure 中运行 - 下面我们提供了以下说明：

<!-- - [Deploying NLWeb to Azure via the Azure Portal](#deploying-nlweb-via-the-azure-portal) -->
- [通过 Azure CLI 将 NLWeb 部署到 Azure](#deploying-nlweb-via-the-azure-cli)
- [Azure OpenAI 终结点创建和获取 API 密钥](#azure-openai-endpoint-creation)
- [提高 Azure OpenAI 配额和费率](#increasing-your-azure-openai-quota-and-rates)
- [Azure WebApp 监控和故障排除](#azure-webapp-monitoring-and-troubleshooting)

## 先决条件

这些说明假定你有 [Azure 订阅](https://go.microsoft.com/fwlink/?linkid=2227353&clcid=0x409&l=en-us&icid=nlweb)、 [本地安装了 Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)，并且在本地安装了 Python 3.10+。

<!--评论我们的，直到我们可以在公开 repo 后进行测试。#
## 通过 Azure 门户部署 NLWeb

1.  [在 Azure 门户中创建 WebApp](https://portal.azure.com/?feature.msaljs=true#view/WebsitesExtension/AppServiceWebAppCreateV3Blade)：
   - 创建新的资源组和实例名称。  
   - 发布： 代码
   - 选择 Python 3.13 作为运行时堆栈
   - 选择 Linux 作为作系统
   - 选择“East US 2”或“Sweden Central”作为区域
   - 选择“Premium V3 P1V3 （195 min ACU/vCPU， 8 GB memory， 2 vCPU）” 作为定价计划
   - 不需要数据库。  

2. 设置部署源：
   - 选择 GitHub 或 Azure DevOps
   - 连接到存储库
   - 设置持续部署

3. 配置应用程序设置：
   - 添加 `.env.template`
   - 设置 `WEBSITE_RUN_FROM_PACKAGE=1`
   - 设置 `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
   - 添加所有应用程序设置后，不要忘记单击“应用”以保存您的更改！  

4. 将 startup 命令配置为：
   ```
   startup.sh
   ```
   这可以在 “Configuration” 部分的 “Settings” 下找到。 它位于默认的“常规设置”选项卡中。 同样，不要忘记在完成保存更改后单击 “Save”。  

   ![Startup Command 可以在 General settings 选项卡下的 Configuration 窗格中找到。](../images/StartupCommand.jpg) -->

## 通过 Azure CLI 部署 NLWeb

1. 登录到 Azure：
   ```bash
   az login
   ```

2. 创建资源组（如果需要）- 如果您已经有要使用的资源组，请跳至下一步：
   ```bash
   az group create --name yourResourceGroup --location eastus2
   ```

3. 创建应用服务计划：
   ```bash
   az appservice plan create --name yourAppServicePlan --resource-group yourResourceGroup --sku P1v3 --is-linux
   ```

4. 创建 Web 应用程序：
   ```bash
   az webapp create --resource-group yourResourceGroup --plan yourAppServicePlan --name yourWebAppName --runtime "PYTHON:3.13"
   ```

5. 配置环境变量;修改以下命令以包括 .env 中的所有环境变量：
   ```bash
   az webapp config appsettings set --resource-group yourResourceGroup --name yourWebAppName --settings \
   AZURE_VECTOR_SEARCH_ENDPOINT="https://TODO.search.windows.net" \
   AZURE_VECTOR_SEARCH_API_KEY="TODO" \
   AZURE_OPENAI_ENDPOINT="https://TODO.openai.azure.com/" \
   AZURE_OPENAI_API_KEY="TODO" \
   WEBSITE_RUN_FROM_PACKAGE=1 \
   SCM_DO_BUILD_DURING_DEPLOYMENT=true \
   NLWEB_OUTPUT_DIR=/home/data \
   ```

6. 设置启动命令：
   ```bash
   az webapp config set --resource-group yourResourceGroup --name yourWebAppName --startup-file "startup.sh"
   ```

7. 使用 ZIP 部署部署代码。在克隆的 NLWeb 文件夹中执行此作，确保在执行此作之前已在 'code/config' 文件夹中设置了要使用的首选提供程序。 如果您不使用 'main' 分支，请将其替换为要使用的分支名称。
   ```bash
   git archive --format zip --output ./app.zip main
   
   ```

8. 使用 ZIP 部署部署代码：

   ```bash 
   az webapp deployment source config-zip --resource-group yourResourceGroup --name yourWebAppName --src ./app.zip
   ```

## Azure WebApp 监控和故障排除

### 原木
在 Azure 门户中或使用 Azure CLI 查看日志：
```bash
az webapp log tail --name yourWebAppName --resource-group yourResourceGroup
```
### 诊断工具
Azure 应用服务在 Azure 门户中提供诊断工具：
1. 转到您的 Web 应用程序
2. 导航到 “诊断和解决问题”
3. 从可用的诊断工具中进行选择

### 健康检查
该应用程序包括一个运行状况终端节点，该终端节点 `/health` 返回指示服务运行状况的 JSON 响应。


## Azure OpenAI 端点创建

如果您还没有 LLM 终端节点，可以按照以下说明使用 Azure OpenAI 部署新终端节点：

1. 通过门户创建 Azure OpenAI 资源[](https://portal.azure.com/#create/Microsoft.CognitiveServicesOpenAI)。 根据需要使用这些[说明](https://learn.microsoft.com/azure/cognitive-services/openai/how-to/create-resource)作为指南。
    > 笔记：
    > - 确保选择要使用的模型可用的区域。 有关更多信息，请参阅 [AOAI 模型摘要表和区域可用性](https://learn.microsoft.com/azure/ai-services/openai/concepts/models?tabs=global-standard%2Cstandard-chat-completions#model-summary-table-and-region-availability)。 要在 config_llm.yaml 中使用 Azure OAI 默认值 4.1 和 4.1-mini[](code\config\config_llm.yaml)，我们建议使用 `eastus2` 或 `swedencentral`。
    > - 如果要在本地调用此终端节点，请在网络设置步骤中使终端节点可从 Internet 访问。

2. 创建 AOAI 资源后，您需要在该资源中部署模型。 这是从 Azure AI Foundry 的 部署中完成的[](https://ai.azure.com/resource/deployments)。可以在 [Azure AI Foundry - 部署模型中查看相关说明](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#deploy-a-model)。
   > 笔记：
   > - 确保您在上一步中创建的资源显示在屏幕左上角的下拉列表中。
   > - 您需要重复此步骤 **3** 次才能部署三个基本模型： `gpt-4.1`、 `gpt-4.1-mini`和 `text-embedding-3-small`。

3. 您需要将 Azure OpenAI 终端节点和密钥添加到 .env 文件中，请参阅 [README 文件中](/README.md)本地设置的步骤 5。可以在 Azure 门户中找到上面创建的 Azure OpenAI 资源的终结点 API 密钥[](https://portal.azure.com/?feature.msaljs=true#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/OpenAI)，而不是在部署模型的 [Azure AI Foundry](https://ai.azure.com) 中找到。 单击 Azure OpenAI 资源，然后在左侧边栏中的“资源管理”下，选择“密钥和端点”。  

![Azure 门户中“资源管理”下的“密钥和终结点”的屏幕截图](../../images/AOAIKeysAndEndpoint.jpg)

## 提高 Azure OpenAI 速率限制

如果您看到很多超时问题，则可能需要提高 AOAI 速率限制。

1. 转到 Azure AI Foundry [部署选项卡](https://ai.azure.com/resource/deployments) ，其中显示了已部署的模型。 您需要对 3 个模型/嵌入中的每一个重复这些说明。

2. 单击模型模型左侧的无线电拨盘。（或者，您可以单击模型以查看配置的完整页面。

3. 单击模型列表顶部的 'Edit'。（如果您单击模型，则“Edit”（编辑）位于下一页的左上角。

4. 在弹出窗口中，滚动到底部显示“每分钟令牌数速率限制”的位置，然后将滑块拖动到更高的值。 

![编辑弹出窗口的屏幕截图](../../images/Azure_token_rate_increase.jpg)

