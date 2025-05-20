# 数据库加载工具指南
-----------------------------------------------------------------

## 开始

在 'code/tools' 文件夹中，你会找到 'db_load.py' 工具。此工具允许您：
- 计算嵌入并将数据加载到向量数据库中
- 从现有数据库中删除文件
- 从现有数据库中删除具有关联文件的站点

## 先决条件

我们假设你已经克隆了仓库并设置了你的NLWeb环境，如[HelloWorld](../../HelloWorld.md)中所述，尽管你可能正在使用不同的提供商或数据库设置。 我们将在下面讨论不同的选项。

数据必须采用以下格式之一：
    1. 每行两列，由选项卡分隔：URL 和 JSON
    2. 一列：仅限 JSON（将从 JSON 中提取 URL）
    3. 包含标题的 CSV 文件
    4. RSS/Atom 源
    5. 指向上述任何类型的 URL

## 将数据加载到 Vector Database 中

使用此命令，将按以下顺序发生三件事：
1. 指向包含结构化数据的现有数据源（有关支持的数据格式，请参阅上文）。该工具将加载/抓取数据。
2. 然后，该工具使用您首选的嵌入提供程序（在 code/config_embedding.yaml 中配置）计算嵌入
3. 然后，该工具将嵌入向量加载到向量数据库（在 code/config_retrieval.yaml 文件中设置）。 请注意，如果您使用的是云服务（如 Azure AI Search），则必须具有对数据库具有写入权限的密钥。

此命令结构如下 - 在虚拟 `myenv` 环境中从 'code' 文件夹运行此命令：
```
python db_load.py <file-path> <site-name>  
```

'file-path' 可以是 URL 或本地路径。 如果要确定搜索范围（在 code/config_nlweb.yaml 中）或需要删除站点和/或条目，则数据源的名称为“site-name”。  

示例如下所示：
```
python -m tools.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
```

## 删除数据库条目

加载数据后，您可能希望删除站点的数据库条目，而不删除站点本身（例如，如果您在配置中设置了站点范围，但想要更改数据库中的条目）。 为此，请使用以下参数并再次从 'code' 文件夹运行：
```
python -m tools.db_load --only-delete delete-site <site-name>
```

对于数据加载步骤中的示例，删除条目将如下所示：
```
python -m tools.db_load --only-delete delete-site Behind-the-Tech
```

<!-- ## 删除站点和数据库条目
评论说明：在测试期间，这表示它需要一个路径而不是站点名称。db load 的第 1074 行与 CLI 中的行为不匹配


如果要删除站点和与站点关联的数据，请使用以下命令，从 'code' 文件夹运行：
```
python -m tools.db_load --delete-site <site-name>
```

同样，对于数据加载步骤中的示例，删除整个网站和数据将如下所示：
```
python -m tools.db_load --delete-site Behind-the-Tech -->
```
## 可选参数

- ** 使用与配置中设置不同的数据库： ** 附加 '--database <preferred endpoint>' 此处，'preferred endpoint' 是指 code/config_retrieval.yaml 中设置的数据库。例如，如果您已将首选终端节点发送到“qdrant-local”，则可以覆盖此终端节点，并使用以下内容写入另一个已配置（但不是首选）检索提供程序，例如“azure-ai-search”：
```
python -m tools.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech --database azure-ai-search
```

- ** 要加载的 URL 很多： ** 在这种情况下，更快的方法是在一个文件中列出这些 URL，以便对单个站点进行批处理。 例如，如果要加载 10 个 RSS 源，则可以创建一个每行 1 个 URL 的 .txt 文件。将 '--url-list' 附加到命令中以执行此作。
```
python -m tools.db_load /some-folder/my-podcast-list.txt Podcast-List --url-list
```

- 更改批处理大小：** 您可能会注意到，在加载数据时，默认情况下，数据会分批到 100 个组中。 如果要将批处理大小更改为不同的项目数，请将 '--batch-size <batch size>' 附加到命令中。以下示例会将批处理大小更改为 200，而不是默认值 100。

```
python -m tools.db_load /some-folder/my-podcast-list.txt Podcast-List --url-list --batch-size 200
```

<!-- 
 --force-recompute - need example use case  -->