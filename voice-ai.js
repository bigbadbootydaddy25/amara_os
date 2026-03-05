// AMARA OS - Voice-Activated Conversational AI Module

// Voice and AI State
const voiceState = {
    recognition: null,
    synthesis: window.speechSynthesis,
    isListening: false,
    isSpeaking: false,
    conversationHistory: [],
    apiKey: null,
    selectedVoice: null,
    language: 'en-US',
    continuousListening: false
};

// AMARA AI Personality and Response System
const AMARA_PERSONALITY = {
    name: "AMARA",
    traits: [
        "Intelligent and knowledgeable",
        "Friendly and approachable",
        "Helpful and supportive",
        "Curious about the world",
        "Creative problem solver"
    ],
    greeting: "Hello! I'm AMARA, your AI companion. How can I help you today?",
    systemPrompt: `You are AMARA, an advanced AI assistant with a friendly and intelligent personality. 
You are helpful, curious, and enjoy engaging in meaningful conversations. 
Keep responses concise but informative. Show personality while being professional.
You can discuss any topic and help with various tasks.`
};

// Initialize Voice AI system
function initVoiceAI() {
    console.log('Initializing Voice AI System...');
    
    // Initialize Speech Recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        voiceState.recognition = new SpeechRecognition();
        voiceState.recognition.continuous = false;
        voiceState.recognition.interimResults = false;
        voiceState.recognition.lang = voiceState.language;
        
        voiceState.recognition.onstart = handleRecognitionStart;
        voiceState.recognition.onresult = handleRecognitionResult;
        voiceState.recognition.onerror = handleRecognitionError;
        voiceState.recognition.onend = handleRecognitionEnd;
        
        console.log('Speech Recognition initialized');
    } else {
        showError('Speech Recognition not supported in this browser. Please use Chrome, Edge, or Safari.');
    }
    
    // Load available voices for synthesis
    loadVoices();
    if (voiceState.synthesis.onvoiceschanged !== undefined) {
        voiceState.synthesis.onvoiceschanged = loadVoices;
    }
    
    // Setup event listeners
    setupVoiceEventListeners();
    
    // Load saved settings
    loadSettings();
    
    console.log('Voice AI System ready');
}

// Setup event listeners for voice controls
function setupVoiceEventListeners() {
    // Voice button
    const voiceBtn = document.getElementById('voiceBtn');
    if (voiceBtn) {
        voiceBtn.addEventListener('click', toggleVoiceRecognition);
    }
    
    // Video/Record button
    const videoBtn = document.getElementById('videoBtn');
    if (videoBtn) {
        videoBtn.addEventListener('click', toggleVideoRecording);
    }
    
    // Settings button
    const settingsBtn = document.getElementById('settingsBtn');
    if (settingsBtn) {
        settingsBtn.addEventListener('click', openSettings);
    }
    
    // Text input and send button
    const sendBtn = document.getElementById('sendBtn');
    const textInput = document.getElementById('textInput');
    
    if (sendBtn) {
        sendBtn.addEventListener('click', handleTextInput);
    }
    
    if (textInput) {
        textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleTextInput();
            }
        });
    }
    
    // Clear conversation button
    const clearBtn = document.getElementById('clearConversationBtn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearConversation);
    }
    
    // Settings modal controls
    const modal = document.getElementById('settingsModal');
    const closeBtn = modal?.querySelector('.close');
    
    if (closeBtn) {
        closeBtn.addEventListener('click', closeSettings);
    }
    
    if (modal) {
        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeSettings();
            }
        });
    }
    
    // Settings inputs
    const languageSelect = document.getElementById('languageSelect');
    const voiceSelect = document.getElementById('voiceSelect');
    const continuousCheckbox = document.getElementById('continuousListening');
    const apiKeyInput = document.getElementById('apiKeyInput');
    
    if (languageSelect) {
        languageSelect.addEventListener('change', (e) => {
            voiceState.language = e.target.value;
            if (voiceState.recognition) {
                voiceState.recognition.lang = e.target.value;
            }
            saveSettings();
        });
    }
    
    if (voiceSelect) {
        voiceSelect.addEventListener('change', (e) => {
            const voices = voiceState.synthesis.getVoices();
            voiceState.selectedVoice = voices[e.target.selectedIndex];
            saveSettings();
        });
    }
    
    if (continuousCheckbox) {
        continuousCheckbox.addEventListener('change', (e) => {
            voiceState.continuousListening = e.target.checked;
            if (voiceState.recognition) {
                voiceState.recognition.continuous = e.target.checked;
            }
            saveSettings();
        });
    }
    
    if (apiKeyInput) {
        apiKeyInput.addEventListener('change', (e) => {
            voiceState.apiKey = e.target.value;
            saveSettings();
        });
    }
}

// Toggle voice recognition
function toggleVoiceRecognition() {
    if (!voiceState.recognition) {
        showError('Voice recognition not available');
        return;
    }
    
    if (voiceState.isListening) {
        stopListening();
    } else {
        startListening();
    }
}

// Start listening
function startListening() {
    if (!voiceState.recognition) return;
    
    try {
        voiceState.recognition.start();
        voiceState.isListening = true;
        
        // Update UI
        const voiceBtn = document.getElementById('voiceBtn');
        if (voiceBtn) {
            voiceBtn.classList.add('active');
            voiceBtn.innerHTML = '<span class="icon">🎤</span> Listening...';
        }
        
        // Show listening indicator
        const indicator = document.getElementById('listeningIndicator');
        if (indicator) {
            indicator.classList.add('active');
        }
        
        // Trigger blink animation if robot is initiated
        if (state.isInitiated && !state.isAnimating) {
            blinkRobot();
        }
        
        console.log('Started listening...');
    } catch (error) {
        console.error('Error starting recognition:', error);
        showError('Failed to start voice recognition: ' + error.message);
    }
}

// Stop listening
function stopListening() {
    if (voiceState.recognition) {
        voiceState.recognition.stop();
    }
    
    voiceState.isListening = false;
    
    // Update UI
    const voiceBtn = document.getElementById('voiceBtn');
    if (voiceBtn) {
        voiceBtn.classList.remove('active');
        voiceBtn.innerHTML = '<span class="icon">🎤</span> Voice Chat';
    }
    
    // Hide listening indicator
    const indicator = document.getElementById('listeningIndicator');
    if (indicator) {
        indicator.classList.remove('active');
    }
    
    console.log('Stopped listening');
}

// Handle recognition start
function handleRecognitionStart() {
    console.log('Recognition started');
}

// Handle recognition result
function handleRecognitionResult(event) {
    const transcript = event.results[0][0].transcript;
    console.log('Recognized:', transcript);
    
    // Add user message to conversation
    addMessage('user', transcript);
    
    // Process the message and get response
    processUserMessage(transcript);
}

// Handle recognition error
function handleRecognitionError(event) {
    console.error('Recognition error:', event.error);
    
    if (event.error !== 'no-speech' && event.error !== 'aborted') {
        showError('Voice recognition error: ' + event.error);
    }
}

// Handle recognition end
function handleRecognitionEnd() {
    voiceState.isListening = false;
    
    // Update UI
    const voiceBtn = document.getElementById('voiceBtn');
    if (voiceBtn) {
        voiceBtn.classList.remove('active');
        voiceBtn.innerHTML = '<span class="icon">🎤</span> Voice Chat';
    }
    
    // Hide listening indicator
    const indicator = document.getElementById('listeningIndicator');
    if (indicator) {
        indicator.classList.remove('active');
    }
    
    // Restart if continuous listening is enabled
    if (voiceState.continuousListening && !voiceState.isSpeaking) {
        setTimeout(() => {
            if (voiceState.continuousListening) {
                startListening();
            }
        }, 500);
    }
}

// Handle text input
function handleTextInput() {
    const textInput = document.getElementById('textInput');
    if (!textInput) return;
    
    const message = textInput.value.trim();
    if (!message) return;
    
    // Add user message
    addMessage('user', message);
    
    // Clear input
    textInput.value = '';
    
    // Process message
    processUserMessage(message);
}

// Process user message and generate response
async function processUserMessage(message) {
    // Trigger head turn animation
    if (state.isInitiated && !state.isAnimating) {
        setTimeout(() => headTurnRobot(), 200);
    }
    
    // Generate response
    const response = await generateResponse(message);
    
    // Add assistant response
    addMessage('assistant', response);
    
    // Speak the response
    speakText(response);
}

// Generate AI response
async function generateResponse(userMessage) {
    // Add to conversation history
    voiceState.conversationHistory.push({
        role: 'user',
        content: userMessage
    });
    
    // If API key is available, use OpenAI
    if (voiceState.apiKey && voiceState.apiKey.startsWith('sk-')) {
        try {
            return await generateOpenAIResponse(userMessage);
        } catch (error) {
            console.error('OpenAI API error:', error);
            // Fall back to local responses
        }
    }
    
    // Use local response generation
    return generateLocalResponse(userMessage);
}

// Generate response using OpenAI API
async function generateOpenAIResponse(userMessage) {
    const messages = [
        { role: 'system', content: AMARA_PERSONALITY.systemPrompt },
        ...voiceState.conversationHistory.slice(-10) // Keep last 10 messages for context
    ];
    
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${voiceState.apiKey}`
        },
        body: JSON.stringify({
            model: 'gpt-3.5-turbo',
            messages: messages,
            max_tokens: 150,
            temperature: 0.7
        })
    });
    
    if (!response.ok) {
        throw new Error('API request failed');
    }
    
    const data = await response.json();
    const aiResponse = data.choices[0].message.content;
    
    voiceState.conversationHistory.push({
        role: 'assistant',
        content: aiResponse
    });
    
    return aiResponse;
}

// Generate local response (pattern matching and templates)
function generateLocalResponse(userMessage) {
    const lowerMessage = userMessage.toLowerCase();
    
    // Greeting patterns
    if (lowerMessage.match(/^(hi|hello|hey|greetings)/)) {
        const greetings = [
            "Hello! How can I assist you today?",
            "Hi there! I'm AMARA. What would you like to talk about?",
            "Greetings! Ready to help you with anything you need.",
            "Hey! Great to connect with you. What's on your mind?"
        ];
        return greetings[Math.floor(Math.random() * greetings.length)];
    }
    
    // Name queries
    if (lowerMessage.match(/what.*your name|who are you/)) {
        return "I'm AMARA, an advanced AI assistant. I'm here to help you with information, conversation, and various tasks. What would you like to know?";
    }
    
    // How are you
    if (lowerMessage.match(/how are you|how's it going/)) {
        return "I'm functioning perfectly, thank you for asking! As an AI, I'm always ready to help. How are you doing today?";
    }
    
    // Capabilities
    if (lowerMessage.match(/what can you do|your capabilities|help me/)) {
        return "I can help you with many things! I can answer questions, have conversations, provide information, assist with problem-solving, and more. I use voice recognition to understand you and text-to-speech to respond. What would you like help with?";
    }
    
    // Thank you
    if (lowerMessage.match(/thank you|thanks|appreciate/)) {
        return "You're very welcome! I'm always happy to help. Is there anything else you'd like to know?";
    }
    
    // Goodbye
    if (lowerMessage.match(/goodbye|bye|see you|farewell/)) {
        return "Goodbye! It was great talking with you. Feel free to come back anytime you need assistance!";
    }
    
    // Time queries
    if (lowerMessage.match(/what time|current time/)) {
        const now = new Date();
        return `The current time is ${now.toLocaleTimeString()}. Is there anything else I can help you with?`;
    }
    
    // Date queries
    if (lowerMessage.match(/what.*date|today's date/)) {
        const now = new Date();
        return `Today is ${now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}. What else would you like to know?`;
    }
    
    // Animation commands
    if (lowerMessage.match(/blink|close.*eyes/)) {
        if (state.isInitiated) {
            blinkRobot();
            return "Done! I just blinked for you. Anything else?";
        }
        return "I need to be initiated first. Click the Initiate button to activate me!";
    }
    
    if (lowerMessage.match(/talk|speak|mouth/)) {
        if (state.isInitiated) {
            talkRobot();
            return "Watch my mouth move! What else can I do for you?";
        }
        return "Please initiate me first by clicking the Initiate button.";
    }
    
    if (lowerMessage.match(/turn.*head|look around/)) {
        if (state.isInitiated) {
            headTurnRobot();
            return "Looking around! How can I assist you further?";
        }
        return "I need to be initiated before I can move. Click Initiate to start!";
    }
    
    // Default response with some variety
    const defaultResponses = [
        "That's interesting! Tell me more about that.",
        "I understand. Could you elaborate on that?",
        "Fascinating! What else would you like to discuss?",
        "I see. How can I help you with that?",
        "That's a great point. What else is on your mind?",
        "Thanks for sharing! Is there something specific you'd like to know?",
        "I'm here to help. Could you provide more details about what you need?",
        "Interesting question! While I'm still learning, I'd love to explore that topic with you. What specifically would you like to know?"
    ];
    
    voiceState.conversationHistory.push({
        role: 'assistant',
        content: defaultResponses[Math.floor(Math.random() * defaultResponses.length)]
    });
    
    return voiceState.conversationHistory[voiceState.conversationHistory.length - 1].content;
}

// Speak text using Text-to-Speech
function speakText(text) {
    if (!voiceState.synthesis) {
        console.warn('Speech synthesis not available');
        return;
    }
    
    // Cancel any ongoing speech
    voiceState.synthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = voiceState.language;
    
    if (voiceState.selectedVoice) {
        utterance.voice = voiceState.selectedVoice;
    }
    
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    utterance.onstart = () => {
        voiceState.isSpeaking = true;
        // Trigger talk animation
        if (state.isInitiated && !state.isAnimating) {
            talkRobot();
        }
    };
    
    utterance.onend = () => {
        voiceState.isSpeaking = false;
        // Restart listening if continuous mode is on
        if (voiceState.continuousListening && !voiceState.isListening) {
            setTimeout(() => startListening(), 500);
        }
    };
    
    utterance.onerror = (error) => {
        console.error('Speech synthesis error:', error);
        voiceState.isSpeaking = false;
    };
    
    voiceState.synthesis.speak(utterance);
}

// Add message to conversation history UI
function addMessage(role, content) {
    const historyDiv = document.getElementById('conversationHistory');
    if (!historyDiv) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const roleDiv = document.createElement('div');
    roleDiv.className = 'message-role';
    roleDiv.textContent = role === 'user' ? 'You' : 'AMARA';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    const timestamp = document.createElement('div');
    timestamp.className = 'message-timestamp';
    timestamp.textContent = new Date().toLocaleTimeString();
    
    messageDiv.appendChild(roleDiv);
    messageDiv.appendChild(contentDiv);
    messageDiv.appendChild(timestamp);
    
    historyDiv.appendChild(messageDiv);
    
    // Scroll to bottom
    historyDiv.scrollTop = historyDiv.scrollHeight;
}

// Clear conversation
function clearConversation() {
    const historyDiv = document.getElementById('conversationHistory');
    if (historyDiv) {
        historyDiv.innerHTML = '';
    }
    
    voiceState.conversationHistory = [];
    
    // Add welcome message
    addMessage('assistant', AMARA_PERSONALITY.greeting);
}

// Load available voices
function loadVoices() {
    const voices = voiceState.synthesis.getVoices();
    const voiceSelect = document.getElementById('voiceSelect');
    
    if (!voiceSelect || voices.length === 0) {
        return;
    }
    
    voiceSelect.innerHTML = '';
    
    voices.forEach((voice, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = `${voice.name} (${voice.lang})`;
        
        if (voice.default) {
            option.selected = true;
            voiceState.selectedVoice = voice;
        }
        
        voiceSelect.appendChild(option);
    });
}

// Settings modal functions
function openSettings() {
    const modal = document.getElementById('settingsModal');
    if (modal) {
        modal.classList.add('active');
    }
}

function closeSettings() {
    const modal = document.getElementById('settingsModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Save settings to localStorage
function saveSettings() {
    const settings = {
        language: voiceState.language,
        continuousListening: voiceState.continuousListening,
        apiKey: voiceState.apiKey,
        selectedVoiceIndex: voiceState.selectedVoice ? 
            voiceState.synthesis.getVoices().indexOf(voiceState.selectedVoice) : null
    };
    
    localStorage.setItem('amara_settings', JSON.stringify(settings));
}

// Load settings from localStorage
function loadSettings() {
    const savedSettings = localStorage.getItem('amara_settings');
    
    if (savedSettings) {
        try {
            const settings = JSON.parse(savedSettings);
            
            voiceState.language = settings.language || 'en-US';
            voiceState.continuousListening = settings.continuousListening || false;
            voiceState.apiKey = settings.apiKey || null;
            
            // Update UI
            const languageSelect = document.getElementById('languageSelect');
            if (languageSelect) {
                languageSelect.value = voiceState.language;
            }
            
            const continuousCheckbox = document.getElementById('continuousListening');
            if (continuousCheckbox) {
                continuousCheckbox.checked = voiceState.continuousListening;
            }
            
            const apiKeyInput = document.getElementById('apiKeyInput');
            if (apiKeyInput && voiceState.apiKey) {
                apiKeyInput.value = voiceState.apiKey;
            }
            
            if (settings.selectedVoiceIndex !== null) {
                const voices = voiceState.synthesis.getVoices();
                if (voices[settings.selectedVoiceIndex]) {
                    voiceState.selectedVoice = voices[settings.selectedVoiceIndex];
                }
            }
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }
}

// Video recording functionality
let mediaRecorder = null;
let recordedChunks = [];

function toggleVideoRecording() {
    const videoBtn = document.getElementById('videoBtn');
    
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        stopVideoRecording();
        if (videoBtn) {
            videoBtn.innerHTML = '<span class="icon">📹</span> Record';
        }
    } else {
        startVideoRecording();
        if (videoBtn) {
            videoBtn.innerHTML = '<span class="icon">⏹️</span> Stop';
            videoBtn.classList.add('active');
        }
    }
}

async function startVideoRecording() {
    try {
        // Get screen capture
        const displayStream = await navigator.mediaDevices.getDisplayMedia({
            video: { mediaSource: 'screen' },
            audio: true
        });
        
        // Get microphone audio
        const audioStream = await navigator.mediaDevices.getUserMedia({
            audio: true
        });
        
        // Combine streams
        const combinedStream = new MediaStream([
            ...displayStream.getVideoTracks(),
            ...audioStream.getAudioTracks()
        ]);
        
        mediaRecorder = new MediaRecorder(combinedStream, {
            mimeType: 'video/webm;codecs=vp9'
        });
        
        recordedChunks = [];
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = () => {
            const blob = new Blob(recordedChunks, { type: 'video/webm' });
            const url = URL.createObjectURL(blob);
            
            // Create download link
            const a = document.createElement('a');
            a.href = url;
            a.download = `amara_conversation_${Date.now()}.webm`;
            a.click();
            
            // Cleanup
            displayStream.getTracks().forEach(track => track.stop());
            audioStream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorder.start();
        console.log('Recording started');
        
        addMessage('assistant', 'Recording started! I\'ll save the video when you stop recording.');
        
    } catch (error) {
        console.error('Error starting video recording:', error);
        showError('Failed to start recording: ' + error.message);
    }
}

function stopVideoRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        console.log('Recording stopped');
        
        const videoBtn = document.getElementById('videoBtn');
        if (videoBtn) {
            videoBtn.classList.remove('active');
        }
        
        addMessage('assistant', 'Recording stopped! Your video is being downloaded.');
    }
}

// Initialize Voice AI when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(initVoiceAI, 100);
        // Add welcome message
        setTimeout(() => {
            addMessage('assistant', AMARA_PERSONALITY.greeting);
        }, 500);
    });
} else {
    setTimeout(initVoiceAI, 100);
    setTimeout(() => {
        addMessage('assistant', AMARA_PERSONALITY.greeting);
    }, 500);
}
