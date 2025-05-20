<!-- Multi-Language Navigation -->
<p align="center">
  <table>
    <tr>
      <td><a href="README.md">English</a></td>
      <td><a href="README_cn.md">简体中文</a></td>
    </tr>
  </table>
</p>

# 什么是 NLWeb


为网站构建对话式界面并非易事。NLWeb 致力于让网站能够轻松实现这一目标。此外，由于 NLWeb 天生支持 MCP，同样的自然语言 API 也可供人类和智能代理共同使用。Schema.org 及类似的半结构化格式（如 RSS）已被超过一亿个网站采用，不仅成为事实上的内容聚合机制，也成为了 Web 的语义层。NLWeb 利用这些，使创建自然语言接口变得更加简单高效。

NLWeb 是一套开放协议及其相关开源工具的集合，其核心目标是为 AI Web 奠定基础层，就像 HTML 曾经彻底改变文档共享一样。为实现这一愿景，NLWeb 提供了实用的代码实现，并非作为最终解决方案，而是作为概念验证的示范，展示一种可行的方法。我们期望并鼓励社区开发出更多多样化、创新性的实现，超越我们的示例。这也正如 Web 自身的发展历程，从最初 NCSA http 服务器中的 ‘htdocs’ 文件夹，到如今的数据中心基础设施，无一不是凭借共享协议实现无缝通信。

AI 有潜力提升每一次 Web 交互，但要实现这一愿景，需要如同 Web 早期“合力搭建谷仓”般的协作精神。成功不仅依赖于共享协议、示例实现，更离不开社区的广泛参与。NLWeb 将协议、Schema.org 格式与示例代码相结合，帮助网站快速构建这些端点，为人类带来对话式界面体验，为机器实现智能代理间的自然交互。

欢迎加入我们，共同构建这个连通的智能代理网络。


# 工作原理
NLWeb包含两个核心组成部分：  

1. **协议层**  
   采用极简设计，通过自然语言与网站交互，并利用json和schema.org格式返回结构化数据。  
   具体技术细节请参阅[REST API文档](/docs/zh_cn/RestAPI.md)。  

2. **实现层**  
   基于协议层构建的轻量级实现方案，适用于商品、菜谱、景点、评论等列表型内容的网站。  
   配套提供系列交互组件，开发者可快速为网站部署对话式界面。  
   完整交互流程详见[聊天查询生命周期](docs/zh_cn/LifeOfAChatQuery.md)技术文档。  


# NLWeb 和 MCP
 MCP（模型上下文协议）是一种新兴的聊天机器人和 AI 助手协议
 以与工具交互。每个 NLWeb 实例也是一个 MCP 服务器，它支持一个核心方法
 <code>ask</code>，用于以自然语言向网站提问。返回的响应
 利用 schema.org，这是一种广泛使用的用于描述 Web 数据的词汇。粗略地说，
 MCP 是 NLWeb，就像 Http 是 HTML 一样。


# NLWeb 和平台
NLWeb 具有高度平台无关性：  
- **跨平台支持**：已在 Windows、MacOS、Linux 等系统通过验证  
- **向量存储兼容**：支持 Qdrant、Snowflake、Milvus、Azure AI Search 等多种引擎  
- **大模型中立**：适配 OpenAI、Deepseek、Gemini、Anthropic、Inception 等主流模型  
- **弹性架构**：从云端集群到本地笔记本均可部署，即将扩展至移动端  

# 代码仓库内容  
本仓库包含以下核心组件：  

- **核心服务引擎**：处理自然语言查询，支持功能扩展与定制  
- **主流模型连接器**：集成多款LLM和向量数据库的对接模块  
- **数据注入工具**：支持将schema.org jsonl、RSS等格式的数据导入目标向量库  
- **轻量级服务架构**：内置Web服务器实现一体化部署  
- **基础查询界面**：提供通过Web服务的简易查询功能  

**生产环境建议**：  
- 推荐使用定制化UI界面  
- 建议将代码集成至现有应用环境（而非独立部署NLWeb服务）  
- 优先对接实时数据库（避免数据拷贝导致时效性问题）  


# 文档

## 开始    
- [笔记本电脑上的 Hello world](HelloWorld_cn.md)
- [在 Azure 上运行它](docs/zh_cn/Azure.md)
- 在 GCP 上运行它...即将推出
- 运行 AWS ...即将推出

## NLWeb 系列
- [聊天查询的生命周期](docs/zh_cn/LifeOfAChatQuery.md)
- [通过更改提示来修改行为](docs/zh_cn/Prompts.md)
- [修改控制流](docs/zh_cn/ControlFlow.md)
- [修改用户界面](/docs/zh_cn/UserInterface.md)
- [REST 接口](docs/zh_cn/RestAPI.md)
- [向 NLWeb 接口添加内存](/docs/zh_cn/Memory.md)



-----------------------------------------------------------------

## 许可证 

NLWeb 使用 [MIT 许可证](LICENSE)。


## 部署 （CI/CD）

_目前，存储库不使用持续集成，也不会生成网站、构件或部署的任何内容。_

## 访问

有关此 GitHub 项目的问题，请联系 [NLWeb 支持](mailto:NLWebSup@microsoft.com)。

## 贡献

有关更多信息，请参阅 [贡献指南](CONTRIBUTING.md) 。

## 商标

本项目可能包含项目、产品或服务的商标或徽标。Microsoft 的授权使用
商标或徽标受
[Microsoft的商标和品牌指南](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general)。
在本项目的修改版本中使用 Microsoft 商标或徽标不得引起混淆或暗示 Microsoft 赞助。
对第三方商标或徽标的任何使用均受这些第三方政策的约束。
