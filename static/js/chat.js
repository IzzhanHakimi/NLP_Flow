// static/js/chat.js
document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatDisplay = document.getElementById('chat-display');
    const chatDisplayWrapper = document.getElementById('chat-display-wrapper');
    const apiKeyInput = document.getElementById('api_key');
    const userProfileInput = document.getElementById('user_profile');
    const userPersonaInput = document.getElementById('user_persona');

    let lastMessageTimestamp = 0;
    const minDelayBetweenBotMessages = 700; // milliseconds

    function addMessageToDisplay(role, content) {
        const messageBubble = document.createElement('div');
        messageBubble.classList.add('message-bubble', role.toLowerCase());
        const messageContentDiv = document.createElement('div');
        messageContentDiv.classList.add('message-content');
        messageContentDiv.textContent = content;
        messageBubble.appendChild(messageContentDiv);
        chatDisplay.appendChild(messageBubble);
        chatDisplayWrapper.scrollTop = chatDisplayWrapper.scrollHeight;
    }

    async function processCurrentMessage() {
        // ... (same as your working version)
        const messageText = messageInput.value.trim();
        if (!messageText) return;
        const apiKey = apiKeyInput.value;
        const userProfile = userProfileInput.value;
        const userPersona = userPersonaInput.value;
        if (!apiKey) {
            addMessageToDisplay('system', 'Error: Google API Key is required.');
            return;
        }
        addMessageToDisplay('user', messageText);
        messageInput.value = '';
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', },
                body: JSON.stringify({
                    message: messageText, api_key: apiKey,
                    user_profile: userProfile, user_persona: userPersona
                }),
            });
            const data = await response.json();
            if (response.ok) { console.log('Message sent to server buffer:', data); }
            else { 
                console.error('Error sending message to server:', data);
                addMessageToDisplay('system', `Error: ${data.error || 'Could not send message.'}`);
            }
        } catch (error) {
            console.error('Network error sending message:', error);
            addMessageToDisplay('system', 'Error: Network problem, could not send message.');
        }
    }

    sendButton.addEventListener('click', processCurrentMessage);
    messageInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            processCurrentMessage();
        }
    });

    async function pollForBotResponse() {
        try {
            const response = await fetch('/get_bot_response');
            if (!response.ok) return;
            const data = await response.json();

            if (data && data.content) {
                const now = Date.now();
                // Add a small delay if last bot message was very recent, to simulate typing burst
                const delayNeeded = Math.max(0, minDelayBetweenBotMessages - (now - lastMessageTimestamp));
                
                setTimeout(() => {
                    addMessageToDisplay(data.role || 'assistant', data.content);
                    lastMessageTimestamp = Date.now(); // Update timestamp after displaying
                }, delayNeeded);
            }
        } catch (error) { /* console.error('Polling error:', error); */ }
    }

    setInterval(pollForBotResponse, 1200); // Poll a bit faster to catch burst parts

    // Default profile/persona loading (same as before)
    const defaultProfile = document.getElementById('user_profile').placeholder;
    const defaultPersona = document.getElementById('user_persona').placeholder;
    if (userProfileInput.value === "") userProfileInput.value = defaultProfile.startsWith("Alice Wong") ? defaultProfile : "Default profile content here...";
    if (userPersonaInput.value === "") userPersonaInput.value = defaultPersona.startsWith("Alice is a university") ? defaultPersona : "Default persona description here...";
});