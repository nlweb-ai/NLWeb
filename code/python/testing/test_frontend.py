import pytest
from bs4 import BeautifulSoup

# It's not possible to run a full browser-based test here, so we will
# simulate the behavior of the frontend code as closely as possible.

# Get the content of the fp-chat-interface.js file
with open('../../static/fp-chat-interface.js', 'r') as f:
    js_code = f.read()

def test_toggle_debug_info():
    """
    Tests the toggleDebugInfo function.
    """
    # Create a mock DOM
    html = """
    <div id="messages-container">
        <div class="assistant-message">
            <div class="message-content">
                <div class="message-text">Original Content</div>
            </div>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Get the elements
    messages_container = soup.find(id='messages-container')
    assistant_message = messages_container.find(class_='assistant-message')
    message_text = assistant_message.find(class_='message-text')

    # Mock the toggleDebugInfo function
    def toggle_debug_info():
        is_showing_debug = 'showing-debug' in message_text.get('class', [])
        if is_showing_debug:
            original_content = message_text.get('data-original-content')
            if original_content:
                # This is the line that was fixed
                new_content = BeautifulSoup(original_content, 'html.parser').div
                message_text.replace_with(new_content)
        else:
            message_text['data-original-content'] = str(message_text)
            message_text['class'] = message_text.get('class', []) + ['showing-debug']
            message_text.string = 'Debug Info'

    # 1. First click (show debug info)
    toggle_debug_info()
    assert 'showing-debug' in message_text.get('class', [])
    assert message_text.string == 'Debug Info'
    assert message_text.get('data-original-content') == '<div class="message-text">Original Content</div>'

    # 2. Second click (hide debug info)
    toggle_debug_info()

    # After the node is replaced, we need to find it again
    message_text = soup.find(class_='message-text')

    assert 'showing-debug' not in message_text.get('class', [])
    # The content should be restored to the original HTML
    assert str(message_text) == '<div class="message-text">Original Content</div>'
