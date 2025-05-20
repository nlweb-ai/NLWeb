# 你好，世界  

## 入门指南  

在本地启动并运行您的NLWeb服务器。  

本指南将帮助您使用本地向量数据库和RSS订阅源快速上手（我们已在下文提供了一些示例链接）。后续您可以替换为自己的数据库。  

## 环境准备  

本教程要求您已在本地安装Python 3.10或更高版本。

## 终端操作指南  
1. 克隆或下载代码库  
```bash  
git clone https://github.com/microsoft/NLWeb  
cd NLWeb  
```  

2. 创建并激活Python虚拟环境  
```bash  
python -m venv myenv  
source myenv/bin/activate  # Linux/Mac系统  
# 或Windows系统: myenv\Scripts\activate  
```  

3. 进入NLWeb的'code'目录安装依赖包  
（注：这将自动安装本地向量数据库所需组件，无需单独安装）  
```bash  
cd code  
pip install -r requirements.txt  
```  

4. 复制环境变量模板文件并配置API密钥  
- 将`.env.template`复制为新的`.env`文件  
- 更新您选择的LLM终端API密钥（本地Qdrant数据库变量已预设）  
- 注意：无需填写文件中所有服务商配置，下文将具体解释  
```bash  
cp .env.template .env  
```

5. 更新配置文件（位于`code/config`目录）  
- **config_llm.yaml**：  
  将首行LLM服务商名称修改为`.env`文件中配置的提供商（默认为Azure OpenAI）。您可在此调整调用的模型名称，默认使用`4.1`和`4.1-mini`版本。  
- **config_embedding.yaml**：  
  更新首行嵌入模型提供商（默认为Azure OpenAI的`text-embedding-3-small`）。  
- **config_retrieval.yaml**：  
  本练习需修改为`qdrant_local`（默认为Azure AI Search）。  

6. 向本地向量数据库加载测试数据  
我们提供以下RSS订阅源供选择（可重复加载多个源构建多站点搜索，默认搜索全部站点，如需限定范围可在`config_nlweb.yaml`中配置）：  
（请确保当前位于`code`目录）  

**加载命令格式**：  
```bash  
python -m tools.db_load <RSS链接> <站点名称>  
```  

**示例数据源**：  
- Kevin的《Behind the Tech》播客：  
```bash  
python -m tools.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech  
```  
- The Verge的《Decoder》播客：  
```bash  
python -m tools.db_load https://feeds.megaphone.fm/recodedecode Decoder  
```  

更多数据格式（非RSS）可访问此[OneDrive文件夹](https://1drv.ms/f/c/6c6197aa87f7f4c4/EsT094eql2EggGxlBAAAAAABajQiZ5unf_Ri_OWksR8eNg?e=I4z5vw)  
（注：若提示登录，请重试链接，该文件夹为公开权限）

6. 启动NLWeb服务器（仍在'code'目录下执行）：
```bash
python app-file.py
```

7. 在浏览器中访问：
```
http://localhost:8000/
```

8. 现在您应该可以看到可用的搜索功能了！

您还可以通过以下方式尝试不同的示例UI界面（在本地主机路径后添加'static/<html文件名>'）：
```
http://localhost:8000/static/search.html
http://localhost:8000/static/chat.html
```

小提示：
- 服务启动后终端会显示运行日志
- 按Ctrl+C可停止服务器
- 如需修改端口号，可在app-file.py中调整