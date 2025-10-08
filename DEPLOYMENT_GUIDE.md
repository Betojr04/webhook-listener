# Deployment Guide

This guide will walk you through deploying your iMessage AI Backend and Dashboard to production.

## Prerequisites

1. **GitHub Account** - Create a free account at https://github.com
2. **Render Account** - Create a free account at https://render.com (for backend)
3. **Vercel Account** - Create a free account at https://vercel.com (for frontend)

---

## Part 1: Push Code to GitHub

### Backend Repository

```bash
cd /Users/albertovaltierrajr/Desktop/webhook-listener

# Create a new repository on GitHub at https://github.com/new
# Name it: imessage-ai-backend

# Add the remote and push
git remote add origin https://github.com/YOUR_USERNAME/imessage-ai-backend.git
git branch -M main
git push -u origin main
```

### Frontend Repository

```bash
cd /Users/albertovaltierrajr/Desktop/dashboard

# Create a new repository on GitHub at https://github.com/new
# Name it: imessage-ai-dashboard

# Add the remote and push
git remote add origin https://github.com/YOUR_USERNAME/imessage-ai-dashboard.git
git branch -M main
git push -u origin main
```

---

## Part 2: Deploy Backend to Render

1. **Go to Render Dashboard**: https://dashboard.render.com/
2. **Click "New +"** → **"Web Service"**
3. **Connect your GitHub account** and select the `imessage-ai-backend` repository
4. **Configure the service:**
   - **Name**: `imessage-ai-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Select **Free**
5. **Add Environment Variables:**
   - Click "Advanced" → "Add Environment Variable"
   - Add each of these:
     ```
     GEMINI_API_KEY = AIzaSyCp8tsV1tatOL1onecqQGWmlQHSyZ67WIY
     JWT_SECRET_KEY = your-super-secret-key-change-this-in-production-please
     MY_IMESSAGE_NUMBER = +14803187213
     IMESSAGE_API_URL = http://127.0.0.1:1234
     WEBHOOK_SECRET = change-me
     ```
6. **Click "Create Web Service"**
7. **Wait 5-10 minutes** for the deployment to complete
8. **Copy your backend URL** - It will look like: `https://imessage-ai-backend.onrender.com`

---

## Part 3: Deploy Frontend to Vercel

1. **Go to Vercel Dashboard**: https://vercel.com/dashboard
2. **Click "Add New..."** → **"Project"**
3. **Import your GitHub repository** `imessage-ai-dashboard`
4. **Configure the project:**
   - **Framework Preset**: Next.js (auto-detected)
   - **Build Command**: `npm run build` (auto-filled)
   - **Output Directory**: `.next` (auto-filled)
5. **Add Environment Variables:**
   - Click "Environment Variables"
   - Add:
     ```
     NEXT_PUBLIC_API_URL = https://imessage-ai-backend.onrender.com/api/v1
     ```
   - **IMPORTANT**: Replace the URL with YOUR actual Render backend URL from Part 2, step 8
6. **Click "Deploy"**
7. **Wait 2-3 minutes** for the deployment to complete
8. **Copy your frontend URL** - It will look like: `https://imessage-ai-dashboard.vercel.app`

---

## Part 4: Test Your Deployed Application

1. **Visit your frontend URL**: `https://imessage-ai-dashboard.vercel.app`
2. **Sign up for a new account**
3. **Log in and test the chat interface**
4. **Send a message** from the web dashboard

**Note**: The iMessage phone integration won't work in production because:
- The polling service requires access to your Mac's local Messages database
- The iMessage API (port 1234) runs on your Mac
- These services can't be deployed to cloud hosting

**What WILL work**:
- ✅ Web chat interface
- ✅ User authentication
- ✅ AI responses via web chat
- ✅ Real-time message streaming

**What WON'T work**:
- ❌ Texting yourself from your phone
- ❌ iMessage polling service
- ❌ Sending messages via AppleScript

---

## Part 5: Share Your App

Your app is now live! Share your frontend URL with anyone:

**Live URL**: `https://imessage-ai-dashboard.vercel.app`

They can:
- Sign up for an account
- Chat with AI in real-time
- View message history

---

## Troubleshooting

### Backend deployment fails
- Check Render logs for errors
- Verify all environment variables are set correctly
- Make sure `requirements.txt` is in the root directory

### Frontend can't connect to backend
- Verify `NEXT_PUBLIC_API_URL` is set correctly in Vercel
- Make sure it ends with `/api/v1`
- Check that backend deployment is successful and running

### CORS errors
- Backend should automatically allow all origins
- Check browser console for specific error messages

---

## Next Steps

To make the iMessage phone integration work, you would need to:
1. Keep the polling service running on your Mac
2. Use a tunneling service like ngrok to expose your backend
3. Configure the polling service to send webhooks to your deployed backend

**However**, for sharing with someone to showcase the web interface, the current deployment is perfect!
