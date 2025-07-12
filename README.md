# 🤖 AI Call Backend

The backend service for the AI Calling Agent - a FastAPI-based API that handles phone calls, AI processing, and integrations with various services including Twilio, OpenAI/Groq, Deepgram, and Qdrant vector database.

## 🏗️ Architecture

This backend service provides:
- **☎️ Phone Service**: Handles incoming/outgoing calls via Twilio
- **🗣️ Speech Processing**: Real-time speech-to-text using Deepgram
- **🤖 AI Processing**: LLM conversations with OpenAI GPT-4o or Groq
- **🧠 RAG System**: Vector-based conversation memory using Qdrant
- **📧 Email Integration**: Automated email summaries and notifications
- **🔈 Text-to-Speech**: High-quality voice synthesis
- **⚡ WebSocket Streaming**: Real-time audio streaming for calls

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker (optional)
- Required API keys (see Configuration section)

### Local Development

1. **Clone and setup:**
   ```bash
   git clone <your-repo-url>
   cd ai-call-backend
   
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Initialize Qdrant (if using RAG):**
   ```bash
   python setup_qdrant.py setup
   ```

4. **Run the server:**
   ```bash
   python app.py
   # Or using uvicorn directly:
   uvicorn app:app --host 0.0.0.0 --port 8080 --reload
   ```

5. **Access the API:**
   - API Documentation: http://localhost:8080/docs
   - Health Check: http://localhost:8080/health

### Docker Deployment

1. **Build and run:**
   ```bash
   docker build -t ai-call-backend .
   docker run -p 8080:8080 --env-file .env ai-call-backend
   ```

2. **Using Docker Compose:**
   ```bash
   docker-compose up -d
   ```

## ⚙️ Configuration

### Required Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Server Configuration
SERVER=your-domain.com
PORT=8080

# Twilio (Required for phone functionality)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_twilio_number

# AI Services (Choose one LLM service)
OPENAI_API_KEY=your_openai_key     # For GPT-4o
GROQ_API_KEY=your_groq_key         # For Groq models
ANTHROPIC_API_KEY=your_claude_key  # For Claude

# Speech Services
DEEPGRAM_API_KEY=your_deepgram_key # For STT
ELEVENLABS_API_KEY=your_elevenlabs_key # For TTS (optional)

# Qdrant Vector Database (for RAG)
QDRANT_HOST=your-qdrant-host
QDRANT_API_KEY=your_qdrant_key
```

### Service Selection

Choose your preferred services by setting:

```bash
LLM_SERVICE=groq        # Options: openai, groq, anthropic
TTS_SERVICE=deepgram    # Options: deepgram, elevenlabs
RAG_ENABLED=true        # Enable conversation memory
```

## 📡 API Endpoints

### Core Endpoints

- `POST /incoming` - Twilio webhook for incoming calls
- `POST /start_call` - Initiate outbound calls
- `GET /call_status/{call_sid}` - Get call status
- `POST /end_call` - End active calls
- `GET /transcript/{call_sid}` - Get call transcript
- `GET /all_transcripts` - List all call transcripts

### WebSocket

- `WS /connection` - Real-time audio streaming for Twilio

### Health & Monitoring

- `GET /docs` - API documentation (Swagger UI)
- Health checks available via Docker healthcheck

## 🧠 RAG (Retrieval Augmented Generation)

The backend includes a sophisticated RAG system for conversation memory:

### Features
- **Phone-based Context**: Stores conversation history per phone number
- **Vector Search**: Semantic search through past conversations
- **Smart Retrieval**: Contextually relevant information retrieval
- **Qdrant Integration**: Production-ready vector database

### Setup
```bash
# Initialize Qdrant collection
python setup_qdrant.py setup

# Test RAG functionality
python test_rag_integration.py
```

## 🔧 Integrations

### Twilio Setup
1. Get a Twilio phone number
2. Configure webhook URL:
   ```bash
   twilio phone-numbers:update YOUR_NUMBER --voice-url=https://your-domain.com/incoming
   ```

### Google Services (Optional)
- **Gmail**: For sending email summaries
- **Calendar**: For scheduling integration
- **Search**: Enhanced search capabilities

## 🏗️ Architecture Details

### Services Structure

```
services/
├── call_context.py      # Call session management
├── llm_service.py       # AI/LLM processing
├── rag_service.py       # Vector database operations
├── stream_service.py    # WebSocket streaming
├── transcription_service.py # Speech-to-text
├── tts_service.py       # Text-to-speech
└── email_service.py     # Email integration
```

### Functions (AI Tools)

```
functions/
├── function_manifest.py # Available AI functions
├── add_calendar_event.py
├── send_email_summary.py
├── send_whatsapp_info.py
├── transfer_call.py
└── end_call.py
```

### Event-Driven Architecture

The backend uses an event-driven system for real-time processing:
- Transcription events trigger LLM processing
- LLM responses trigger TTS generation
- Audio generation triggers streaming to caller

## 🔒 Security & Production

### Security Features
- Environment-based configuration
- API key validation
- WebSocket connection security
- Rate limiting (configurable)

### Production Considerations
- Use HTTPS in production
- Set up proper logging and monitoring
- Configure resource limits
- Use a reverse proxy (nginx/Traefik)
- Set up health checks and alerting

### Scaling
- Stateless design allows horizontal scaling
- External Qdrant for shared conversation memory
- Consider Redis for session management at scale

## 🧪 Testing

```bash
# Run all tests
pytest

# Test specific components
python test_email_integration.py
python test_rag_integration.py

# Test Qdrant setup
python setup_qdrant.py test
```

## 📊 Monitoring

### Logs
The application uses structured logging with Loguru:
- Request/response logging
- Error tracking
- Performance metrics
- Call transcription logging

### Health Checks
- Database connectivity
- External API status
- Resource utilization

## 🛠️ Development

### Project Structure
```
backend/
├── app.py                 # FastAPI application
├── logger_config.py       # Logging configuration
├── setup_qdrant.py       # Database initialization
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container definition
├── docker-compose.yml    # Local deployment
├── services/             # Core services
├── functions/            # AI function tools
├── utility/              # Helper utilities
└── tests/               # Test files
```

### Adding New Features
1. Create service in `services/` directory
2. Add function tools in `functions/`
3. Update `function_manifest.py`
4. Add tests
5. Update documentation

## 🔗 Related Projects

- **Frontend**: Streamlit-based UI for call management
- **Qdrant**: Vector database for conversation memory
- **Twilio**: Phone service integration

## 📄 License

[Your License Here]

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For issues and questions:
- Create an issue in the repository
- Check the logs: `docker logs ai-call-backend`
- Review the API documentation at `/docs`
