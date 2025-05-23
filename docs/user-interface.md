# User Interface Widgets

This repository contains a small library of javascript files that can be used to create a chat interface. The library is very rudimentary, but can be useful for quick prototyping.

The script in static/index.html, given below, with comments, is a very simple example of pulling together the basic elements of an interface with session level memory.

The main method is 'ChatInterface', which can be initialized with a default value for 'site' and 'mode' (see Rest API documentation). It also takes a display_mode argument, which can either be dropdown (which is used in static/debug.html to give more options) or 'nlwebsearch'.

<script>
    document.addEventListener('DOMContentLoaded', () => {
         const searchInput = document.getElementById('ai-search-input');
         // we assume there is a search input box with that id
         const searchButton = document.getElementById('ai-search-button');
         // we assume there is a search button with that id
         var chatContainer = document.getElementById('chat-container');
         // the div where the results will be presented

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

The streaming UI widgets work with the /ask endpoint.

The presentation of each item can be specialized, based on the @type of the item. A good example of this is in static/recipe-renderer.js which is used to render recipes. These renderers can be used outside of a chat like interface as well.
