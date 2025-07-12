# Backend Deployment Guide

## 🚀 Quick Deploy

### Local Development
```bash
# Setup
cp .env.example .env
# Edit .env with your credentials

# Install dependencies
pip install -r requirements.txt

# Initialize Qdrant
python setup_qdrant.py setup

# Run
python app.py
```

### Docker Deployment
```bash
# Build and run
docker build -t ai-call-backend .
docker run -p 3000:3000 --env-file .env ai-call-backend

# Or with Docker Compose
docker-compose up -d
```

## 🔧 Configuration Required

1. **Twilio**: Account SID, Auth Token, Phone Number
2. **AI Service**: OpenAI/Groq/Anthropic API key
3. **Speech**: Deepgram API key
4. **Qdrant**: Host, API key (already configured for cloud)
5. **Email**: SMTP settings for notifications

## 🌐 Production Setup

1. Set `SERVER` to your production domain
2. Configure Twilio webhook: `https://your-domain.com/incoming`
3. Use HTTPS with reverse proxy
4. Set up monitoring and logging

## 📊 Endpoints

- `POST /incoming` - Twilio webhook
- `POST /start_call` - Start calls
- `GET /docs` - API documentation
- `WS /connection` - Audio streaming

## 🔍 Health Check

```bash
curl http://localhost:3000/docs
```
