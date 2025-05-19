import { ChatInterface } from './streaming.js';

// Make ChatInterface available globally
window.ChatInterface = ChatInterface;

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('ai-search-input');
    const searchButton = document.getElementById('ai-search-button');
    var chatContainer = document.getElementById('chat-container');
    searchButton.addEventListener('click', handleSearch);
    searchInput.addEventListener('keypress', (e) => {
         if (e.key === 'Enter') {
              handleSearch();
         }
    });

    var chat_interface = null;

    window.findChatInterface = function() {
        if (chat_interface) {
            return chat_interface;
        }
        chat_interface = new ChatInterface('', 'nlwebsearch', 'list');
        return chat_interface;
    }

    function handleSearch() {
        const query = searchInput.value.trim();
        
        chatContainer.style.display = 'block';
        chat_interface = findChatInterface();
        searchInput.value = '';
        chat_interface.sendMessage(query);
    }
});