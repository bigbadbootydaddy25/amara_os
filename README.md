# AMARA OS - Voice-Activated Conversational ASI

Advanced AI companion with voice recognition, natural conversation, and video recording capabilities. Built on a robot animation system with feathered edge masking for seamless visual effects.

## 🎯 Core Features

### 🎤 Voice-Activated Conversation
- **Speech Recognition**: Real-time voice input using Web Speech API
- **Natural Language Processing**: Intelligent conversation with context awareness
- **Text-to-Speech**: AMARA speaks responses with synchronized mouth animations
- **Multi-Modal Input**: Voice or text input options
- **Continuous Listening Mode**: Hands-free conversation option

### 🤖 Intelligent AI Assistant
- **Personality System**: AMARA has a friendly, helpful, and curious personality
- **Conversation Memory**: Maintains context across the conversation
- **Local Responses**: Built-in response patterns for common queries
- **OpenAI Integration**: Optional API key support for enhanced AI capabilities
- **Smart Commands**: Voice commands can trigger robot animations

### 📹 Video Recording
- **Screen Capture**: Record your conversations with AMARA
- **Audio Integration**: Captures both system audio and microphone
- **Easy Export**: Downloads video files in WebM format
- **One-Click Control**: Start/stop recording with a single button

### 🎨 Visual Features
- **Animated Robot Face**: Responsive eyes and mouth with feathered masking
- **Synchronized Animations**: Robot responds visually during conversations
  - Eyes light up when initiated
  - Blinks naturally during conversations
  - Mouth moves while speaking
  - Head turns when processing responses
- **Listening Indicator**: Visual pulse effect when actively listening
- **Beautiful Dark Theme**: Gradient background with cyan/pink accents

## 🚀 Quick Start

### Installation
1. Clone the repository:
```bash
git clone https://github.com/bigbadbootydaddy25/amara_os.git
cd amara_os
```

2. Start a local server:
```bash
python3 -m http.server 8080
```

3. Open in your browser:
```
http://localhost:8080/index.html
```

### First Conversation
1. **Click "Initiate"** - Activates AMARA and lights up the eyes
2. **Click "Voice Chat"** - Starts listening for voice input
3. **Speak naturally** - Ask questions or have a conversation
4. **Type alternative** - Use text input if preferred
5. **Record (Optional)** - Capture your conversation on video

## 💬 Example Conversations

Ask AMARA questions like:
- "Hello AMARA! What can you do?"
- "What time is it?"
- "Can you blink your eyes?"
- "Tell me something interesting"
- "How are you today?"

Voice commands for animations:
- "Blink" - Triggers eye blink animation
- "Talk" or "Move your mouth" - Shows mouth animation
- "Turn your head" - Performs head turn animation

## ⚙️ Settings & Customization

Access the Settings panel to configure:

### Voice Recognition
- **Language Selection**: English (US/UK), Spanish, French, German, Japanese
- **Continuous Listening**: Enable hands-free mode

### Voice Output
- **Voice Selection**: Choose from available system voices
- **Speech Rate & Pitch**: Customize how AMARA sounds (coming soon)

### AI Enhancement
- **OpenAI API Key**: Optional integration for advanced conversations
- **Local Fallback**: Works without API key using pattern matching

## 📁 Project Structure

```
amara_os/
├── index.html          # Main HTML structure
├── style.css           # Unified styling with responsive design
├── main.js             # Robot animation controller
├── voice-ai.js         # Voice recognition & AI conversation system
├── README.md           # This file
└── public/             # Robot image assets
    ├── robot_base.png
    ├── eyes_lit.png
    ├── eyes_blink.png
    ├── mouth_talk.png
    └── head_turn.png
```

## 🛠️ Technical Implementation

### Voice Recognition System
- **Web Speech API**: Browser-native speech recognition
- **Event-Driven**: Handles start, result, error, and end events
- **Continuous Mode**: Optional always-listening capability
- **Multi-Language**: Supports 6+ languages

### AI Conversation Engine
- **Pattern Matching**: Local intelligence for common queries
- **Context Awareness**: Maintains conversation history
- **Response Generation**: Dynamic, varied responses
- **API Integration**: Optional OpenAI GPT integration

### Animation Synchronization
- **Speech-to-Animation**: Mouth moves during TTS
- **Context-Aware**: Different animations for different actions
- **Smooth Transitions**: Feathered edge masking prevents artifacts
- **Auto-Behaviors**: Natural blinking every 5 seconds

### Video Recording
- **MediaRecorder API**: Browser-native screen recording
- **Stream Combination**: Merges screen and audio streams
- **WebM Format**: Efficient video compression
- **Automatic Download**: Files saved locally on stop

## 🌐 Browser Compatibility

| Feature | Chrome | Edge | Safari | Firefox |
|---------|--------|------|--------|---------|
| Voice Recognition | ✅ | ✅ | ✅ | ❌* |
| Text-to-Speech | ✅ | ✅ | ✅ | ✅ |
| Video Recording | ✅ | ✅ | ✅** | ✅ |
| Animations | ✅ | ✅ | ✅ | ✅ |

*Firefox requires additional setup for speech recognition
**Safari requires user permission for each session

## 🔒 Privacy & Security

- **Local Processing**: Voice recognition happens in your browser
- **No Data Collection**: Conversations are not stored or transmitted
- **Optional API**: OpenAI integration only if you provide a key
- **Secure Storage**: API keys stored locally using localStorage
- **User Control**: Full control over microphone and recording permissions

## 🎯 Use Cases

### Personal Assistant
- Ask questions and get instant answers
- Set reminders and get information
- Natural language interaction

### Learning & Education
- Practice conversation skills
- Learn about various topics
- Interactive AI demonstrations

### Content Creation
- Record AI conversations for videos
- Create tutorials and demonstrations
- Showcase AI interaction capabilities

### Accessibility
- Voice-controlled interface
- Hands-free operation
- Visual feedback for all interactions

## 🚧 Roadmap

### Upcoming Features
- [ ] Emotion detection from voice tone
- [ ] Multiple conversation personas
- [ ] Export conversation transcripts
- [ ] Real-time language translation
- [ ] Integration with more AI models (Claude, Gemini)
- [ ] Custom wake words
- [ ] Voice command shortcuts
- [ ] Advanced video editing tools

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional language support
- More animation patterns
- Enhanced AI responses
- Better mobile experience
- Accessibility features

## 📄 License

MIT License - feel free to use and modify for your projects

## 🙏 Acknowledgments

- Web Speech API for voice capabilities
- OpenAI for advanced AI integration
- Canvas API for smooth animations
- The open-source community

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing documentation
- Review browser console for debugging

---

**AMARA OS** - Building the future of human-AI interaction, one conversation at a time. 🤖✨
