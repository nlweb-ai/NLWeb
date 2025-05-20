# 用户界面小部件

此存储库包含一个小型 javascript 文件库
可用于创建聊天界面。该库是
非常初级，但可用于快速原型设计。

static/index.html 中的脚本，如下所示，带有注释，
是一个非常简单的示例，它将
元素。

主要方法是 'ChatInterface'，它可以初始化
替换为 'site' 和 'mode' 的默认值（请参阅 Rest API 文档）。
它还需要一个 display_mode 参数，该参数可以是 dropdown
（在 static/debug.html 中用于提供更多选项）或 'nlwebsearch'。

<script>document.addEventListener（'DOMContentLoaded'， （） => {
         const searchInput = document.getElementById（'ai-search-input'）;
         我们假设有一个具有该 ID 的搜索输入框
         const searchButton = document.getElementById（'ai-search-button'）;
         我们假设有一个具有该 ID 的搜索按钮
         var chatContainer = document.getElementById（'chat-container'）;
         将显示结果的 div

         searchButton.addEventListener('click', handleSearch);
         searchInput.addEventListener('keypress', (e) => {
              if (e.key === 'Enter') {
                   handleSearch();
              }
         });

         var chat_interface = null;

         function findChatInterface() {
          if (chat_interface) {
              return chat_interface;
          }
          chat_interface = new ChatInterface('', display_mode='nlwebsearch', generate_mode='list');
          return chat_interface;
         }

         function handleSearch() {
              const query = searchInput.value.trim();
              chatContainer.style.display = 'block';
              chat_interface = findChatInterface();
              searchInput.value = '';

              // sendMessage triggers the next chat turn
              chat_interface.sendMessage(query);
              
         }
    });
</script>

流式处理 UI 小组件与 /ask 端点配合使用。

每个项目的表示都可以根据
@type项。一个很好的例子是 static/recipe-renderer.js
用于渲染配方。可以使用这些渲染器
在类似聊天的界面之外。