# Ngrok Setup Guide for Form Builder Application

This guide explains how to set up and run the Form Builder Application with ngrok tunnels for external access.

## Prerequisites

### 1. Install Ngrok
```bash
# Download and install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Or download directly
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin
```

### 2. Get Ngrok Auth Token
1. Sign up at [https://ngrok.com](https://ngrok.com)
2. Go to [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Copy your auth token
4. Run: `ngrok authtoken YOUR_AUTH_TOKEN`

## Running the Application

### Option 1: Using Python Script (Recommended)
```bash
cd /app
python3 start_with_ngrok.py
```

### Option 2: Using Bash Script
```bash
cd /app
./start_all.sh
```

### Option 3: Manual Setup
```bash
# Terminal 1: Start Backend
cd /app/server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start Frontend
cd /app/Form-with-AI-Frontend
npm install
npm run dev

# Terminal 3: Start Backend Tunnel
ngrok http 8000

# Terminal 4: Start Frontend Tunnel
ngrok http 5173
```

## What Happens When You Start

1. **Backend Server** starts on `localhost:8000`
2. **Frontend Server** starts on `localhost:5173`
3. **Ngrok Tunnels** are created:
   - Backend tunnel: `https://xxxxx.ngrok.io` → `localhost:8000`
   - Frontend tunnel: `https://yyyyy.ngrok.io` → `localhost:5173`
4. **Frontend .env** is automatically updated with the backend tunnel URL
5. **Application URLs** are displayed in the console

## Expected Output

```
🎯 Starting Form Builder Application with Ngrok
==================================================
🚀 Starting backend server...
✅ Backend server started successfully on port 8000
🚀 Starting frontend server...
✅ Frontend server started successfully on port 5173
🌐 Starting ngrok tunnels...
✅ Ngrok tunnels started successfully!
🔗 Backend URL: https://abc123.ngrok.io
🔗 Frontend URL: https://def456.ngrok.io

============================================================
🎉 APPLICATION READY!
============================================================
📱 Access your app at: https://def456.ngrok.io
🔧 Backend API at: https://abc123.ngrok.io
============================================================
```

## Accessing Your Application

- **Main App**: Use the Frontend URL shown in the output
- **API Documentation**: Visit `{Backend URL}/docs` for FastAPI docs
- **Ngrok Dashboard**: Visit `http://localhost:4040` for tunnel management

## Features Available

### 1. Dynamic Form Fields ✅
- Create forms with conditional logic
- Radio button selections show different fields
- Example: Patient form with "New Patient" vs "Existing Patient" options

### 2. Multilingual Support ✅
- Gujarati speech input with English form storage
- Language switching between English and Gujarati
- Proper STT handling for both languages

### 3. External Access via Ngrok ✅
- Both frontend and backend accessible externally
- Automatic URL configuration
- Health monitoring and restart capabilities

## Configuration Files

- `/app/ngrok_config.py` - Ngrok tunnel management
- `/app/start_with_ngrok.py` - Python startup script
- `/app/start_all.sh` - Bash startup script
- `/app/Form-with-AI-Frontend/.env` - Auto-updated with backend URL

## Troubleshooting

### Ngrok Authentication Issues
```bash
# Check if authenticated
ngrok authtoken --help

# Re-authenticate
ngrok authtoken YOUR_NEW_TOKEN
```

### Port Already in Use
```bash
# Kill processes on ports
sudo lsof -ti:8000 | xargs kill -9
sudo lsof -ti:5173 | xargs kill -9
```

### Frontend Not Loading Backend
1. Check if `.env` file has correct `VITE_BACKEND_URL`
2. Verify backend tunnel is working: `curl {Backend URL}/health`
3. Check CORS settings in backend

### Tunnels Not Starting
1. Check ngrok auth: `cat ~/.config/ngrok/ngrok.yml`
2. Check ngrok limits (free plan has restrictions)
3. Try restarting ngrok: `pkill ngrok && sleep 2`

## Sharing Your Application

Once running, you can share the frontend URL with anyone:
- `https://def456.ngrok.io` - Anyone can access your form builder
- Forms work with voice input and AI assistance
- Multiple languages supported (English/Gujarati)

## Stopping the Application

Press `Ctrl+C` in the terminal where you started the application. This will:
1. Stop the backend server
2. Stop the frontend server  
3. Close all ngrok tunnels
4. Clean up processes

## Advanced Usage

### Custom Ngrok Configuration
Create `~/.config/ngrok/ngrok.yml`:
```yaml
authtoken: YOUR_AUTH_TOKEN
tunnels:
  form-backend:
    proto: http
    addr: 8000
    subdomain: myapp-api  # requires paid plan
  form-frontend:
    proto: http
    addr: 5173
    subdomain: myapp  # requires paid plan
```

### Production Deployment
For production, consider:
1. Using a reverse proxy (nginx)
2. Setting up proper domain names
3. SSL certificates
4. Environment-specific configurations
5. Docker containers for scalability

## Environment Variables

### Backend (.env)
```
ENV=dev
PORT=8000
GEMINI_API_KEY=your_key_here
GOOGLE_APPLICATION_CREDENTIALS=./google-credentials.json
```

### Frontend (.env)
```
VITE_BACKEND_URL=https://your-backend-tunnel.ngrok.io
```

## Security Considerations

1. **Auth Tokens**: Keep ngrok auth tokens secure
2. **API Keys**: Don't expose API keys in frontend
3. **Tunnels**: Free ngrok tunnels are public - use auth for sensitive data
4. **HTTPS**: Ngrok provides HTTPS by default
5. **Rate Limits**: Be aware of ngrok and API rate limits

## Support

For issues:
1. Check the logs: `tail -f /tmp/backend.log` and `tail -f /tmp/frontend.log`
2. Visit ngrok dashboard: `http://localhost:4040`
3. Check application health endpoints
4. Review this documentation for troubleshooting steps