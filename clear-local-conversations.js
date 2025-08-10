// Script to clear all local conversations from browser localStorage
// Run this in the browser console to clear conversations

(function clearLocalConversations() {
  // Clear conversations
  localStorage.removeItem('nlweb_conversations');
  
  // Clear current conversation state
  localStorage.removeItem('currentConversationId');
  localStorage.removeItem('wsConversationId');
  
  // Optional: Clear other related data
  // localStorage.removeItem('userInfo');
  // localStorage.removeItem('authToken');
  // localStorage.removeItem('nlweb_sites');
  
  console.log('✅ Local conversations cleared');
  console.log('Remaining localStorage keys:', Object.keys(localStorage));
  
  // Reload the page to reset the UI
  if (confirm('Conversations cleared. Reload the page to reset the UI?')) {
    location.reload();
  }
})();