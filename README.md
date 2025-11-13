# Form with AI

An intelligent form-filling application powered by AI that enables conversational form completion through voice and text interactions. The system supports multilingual conversations (English and Gujarati) and provides a natural, user-friendly way to collect form data.

## 🌟 Features

- **AI-Powered Conversations**: Natural language form filling using Google's Gemini AI
- **Voice & Text Input**: Seamlessly switch between voice and text interactions
- **Multilingual Support**: English and Gujarati language support with automatic translation
- **Dynamic Form Builder**: Create custom forms with various field types
- **Text-to-Speech**: Real-time audio responses in multiple languages using Google TTS
- **Speech-to-Text**: Advanced voice recognition with Faster Whisper
- **Phone Call Mode**: Simplified interface mimicking phone call experience
- **Session Management**: Track and manage individual form-filling sessions
- **Real-time Form Preview**: See your form data update in real-time as you chat

## 🏗️ Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Uvicorn**: ASGI server
- **Google Generative AI (Gemini)**: LLM for conversational intelligence
- **Faster Whisper**: Speech-to-text processing
- **Google Cloud Text-to-Speech**: Multilingual voice synthesis
- **pyttsx3**: Offline text-to-speech fallback

### Frontend
- **React 19**: Modern UI library
- **Vite**: Fast build tool and dev server
- **Tailwind CSS 4**: Utility-first styling
- **QR Code**: Generate QR codes for easy form sharing

## 📋 Prerequisites

Before running this project, ensure you have the following installed:

- **Python 3.8+** with pip
- **Node.js 16+** with npm
- **Google Cloud API credentials** (for TTS)
- **Google Gemini API key**

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/ompatel22/Form-with-AI.git
cd Form-with-AI
```

### 2. Set Up Environment Variables

Create `.env` files for both backend and frontend:

#### Backend (.env)
Create `/app/server/.env` with the following variables:

```env
# Google Gemini API Key
GOOGLE_API_KEY=your_gemini_api_key_here

# Google Cloud TTS credentials
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/google-cloud-credentials.json

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

#### Frontend (.env)
Create `/app/Form-with-AI-Frontend/.env` with:

```env
VITE_BACKEND_URL=http://127.0.0.1:8000
```

### 3. Backend Setup

Navigate to the server directory and set up a Python virtual environment:

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Install required dependencies:

```bash
pip install -r requirements.txt
```

### 4. Frontend Setup

Navigate to the frontend directory:

```bash
cd ../Form-with-AI-Frontend
```

Install dependencies:

```bash
npm install
```

## 🎯 Running the Application

### Start the Backend Server

Open a terminal, navigate to the server directory, and run:

```bash
cd server
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The backend will be available at `http://127.0.0.1:8000`

### Start the Frontend Development Server

Open another terminal, navigate to the frontend directory, and run:

```bash
cd Form-with-AI-Frontend
npm run dev
```

The frontend will typically be available at `http://localhost:5173` (Vite will display the exact URL)

## 📱 Using ngrok (Optional)

For public access or testing on mobile devices, you can use ngrok:

```bash
# Install ngrok if you haven't already
# Then run the start script
python start_with_ngrok.py
```

Or use the shell script:

```bash
chmod +x start_all.sh
./start_all.sh
```

## 🎮 Usage

1. **Create a Form**: Use the Form Manager to create custom forms with various field types (text, date, number, email, etc.)

2. **Start a Conversation**: Click "Start Chat" to begin an AI-powered conversation

3. **Fill the Form**: 
   - Use text input or voice recording
   - The AI will guide you through each field
   - Switch between English and Gujarati using the language selector

4. **Review & Submit**: View your completed form data in real-time and submit when ready

## 📁 Project Structure

```
.
├── server/                          # Backend FastAPI application
│   ├── app/
│   │   ├── main.py                 # Main FastAPI app with routes
│   │   ├── config.py               # Configuration management
│   │   ├── llm.py                  # Gemini LLM integration
│   │   ├── stt.py                  # Speech-to-text processing
│   │   ├── google_tts.py           # Text-to-speech service
│   │   ├── memory.py               # Session memory management
│   │   ├── form_builder.py         # Form schema and management
│   │   ├── enhanced_dynamic_chat.py # Conversational logic
│   │   ├── enhanced_date_parser.py # Date parsing utilities
│   │   └── language_support.py     # Multilingual support
│   ├── requirements.txt            # Python dependencies
│   └── server.py                   # Uvicorn entry point
│
├── Form-with-AI-Frontend/          # Frontend React application
│   ├── src/
│   │   ├── App.jsx                 # Main app component
│   │   ├── components/             # React components
│   │   │   ├── ChatSide.jsx       # Chat interface
│   │   │   ├── FormSide.jsx       # Form display
│   │   │   ├── FormBuilder.jsx    # Form creation tool
│   │   │   ├── FormManager.jsx    # Form management
│   │   │   ├── DynamicFormRenderer.jsx
│   │   │   ├── EnhancedChatSide.jsx
│   │   │   └── LanguageSwitcher.jsx
│   │   └── main.jsx               # React entry point
│   ├── package.json               # Node dependencies
│   └── vite.config.js            # Vite configuration
│
├── start_with_ngrok.py           # Ngrok startup script
├── start_all.sh                  # Shell startup script
└── README.md                     # This file
```

## 🔧 API Endpoints

### Form Management
- `GET /api/forms` - List all forms
- `POST /api/forms` - Create a new form
- `GET /api/forms/{form_id}` - Get a specific form
- `DELETE /api/forms/{form_id}` - Delete a form

### Conversation
- `POST /api/chat/message` - Send a message (text or audio)
- `POST /api/chat/reset` - Reset conversation session
- `GET /api/chat/status` - Get conversation status

## 🐛 Troubleshooting

### Backend Issues
- Ensure all API keys are correctly set in `.env`
- Check that the virtual environment is activated
- Verify Python dependencies are installed: `pip list`
- Check logs at `server/form_agent.log`

### Frontend Issues
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Ensure backend is running and accessible
- Check browser console for errors
- Verify `VITE_BACKEND_URL` is correctly set in `.env`

### Audio Issues
- Grant microphone permissions in your browser
- Check Google Cloud TTS credentials are valid
- Ensure audio codecs are supported in your browser
