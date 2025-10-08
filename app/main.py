# app/main.py
import os
import logging
import asyncio
import uuid
import re
import time
import httpx
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Header, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from dotenv import load_dotenv
import google.generativeai as genai

# DB + Models
from .db import AsyncSessionLocal, init_db
from .models import Chat, Message, User
from .schemas import ChatSchema, MessageSchema
from sqlalchemy.future import select

# Push notifications
from .services import push as push_service

# Auth
from .auth import hash_password, verify_password, create_access_token, get_current_user

# 🔧 Compatibility shim (fixes MutableSet issue in Python 3.11+)
import collections, collections.abc

if not hasattr(collections, "MutableSet"):
    collections.MutableSet = collections.abc.MutableSet

load_dotenv()

app = FastAPI()

# Enable CORS for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)

# -----------------------
# ENV config
# -----------------------
API_KEY = os.getenv("IMESSAGE_API_KEY")
IMESSAGE_API_URL = os.getenv("IMESSAGE_API_URL")
MY_IMESSAGE_NUMBER = os.getenv("MY_IMESSAGE_NUMBER")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
ALLOWED_NUMBER = os.getenv("ALLOWED_NUMBER")
# Whitelist of allowed recipients (your number/email only)
ALLOWED_RECIPIENTS = [
    MY_IMESSAGE_NUMBER,
    ALLOWED_NUMBER,
    os.getenv("MY_APPLE_ID_EMAIL"),  # Add your Apple ID email if needed
]
ALLOWED_RECIPIENTS = [r for r in ALLOWED_RECIPIENTS if r]  # Remove None values

# Gemini (active)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
if GEMINI_API_KEY:
    logging.info(f"✅ Gemini ready (AI Studio, model={GEMINI_MODEL})")

# Daisy (commented out - chatflows broken, uncomment when fixed)
# DAISY_API_URL = os.getenv("DAISY_API_URL")
# DAISY_API_KEY = os.getenv("DAISY_API_KEY")
# if DAISY_API_URL:
#     logging.info(f"✅ Daisy ready (URL={DAISY_API_URL})")
# else:
#     logging.warning("⚠️ Daisy not configured (missing DAISY_API_URL)")

# Device tokens storage (in production, store in database)
device_tokens: dict[str, str] = {}  # user_id -> device_token


# -----------------------
# Helpers
# -----------------------
async def send_imessage(to: str, text: str) -> bool:
    """
    Send message via iMessage API with safety check.
    Only sends to whitelisted recipients.
    """
    if to not in ALLOWED_RECIPIENTS:
        logging.warning(f"🚫 Blocked attempt to send to non-whitelisted number: {to}")
        return False

    if not IMESSAGE_API_URL or not API_KEY:
        logging.error("❌ iMessage API not configured")
        return False

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                f"{IMESSAGE_API_URL}/send/",
                json={"number": to, "text": text},  # Changed "to" to "number"
                headers={"X-API-Key": API_KEY},  # Changed to X-API-Key
                timeout=10.0
            )
            response.raise_for_status()
            logging.info(f"✅ Sent iMessage to {to}")
            return True
    except Exception as e:
        logging.error(f"❌ Failed to send iMessage: {e}")
        return False


async def send_push_notification(user_id: str, title: str, body: str, chat_id: str = None):
    """Send push notification to user's device if APNs is configured"""
    if not push_service.is_ready():
        logging.debug("APNs not configured, skipping push notification")
        return

    device_token = device_tokens.get(user_id)
    if not device_token:
        logging.debug(f"No device token found for user {user_id}")
        return

    try:
        custom_data = {"chatId": chat_id} if chat_id else {}
        await push_service.push_alert(
            device_token=device_token,
            title=title,
            body=body,
            thread_id=chat_id,
            custom=custom_data,
        )
        logging.info(f"📱 Sent push notification to {user_id}")
    except Exception as e:
        logging.error(f"❌ Failed to send push notification: {e}")


async def save_message(chat_id, from_, to, text, is_from_me: bool):
    """Save message + chat in DB (normalize IDs)"""
    norm_id = chat_id.strip().lower().replace(" ", "-")

    async with AsyncSessionLocal() as session:
        chat = await session.get(Chat, norm_id)
        if not chat:
            chat = Chat(id=norm_id, name=chat_id)
            session.add(chat)
            await session.commit()

        msg = Message(
            chat_id=norm_id,
            from_user=from_,
            to_user=to,
            text=text,
            is_from_me=is_from_me,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)

        # Broadcast using schema encoding
        asyncio.create_task(_broadcast(jsonable_encoder(msg, by_alias=True)))

        # Send push notification for incoming messages
        if not is_from_me:
            asyncio.create_task(send_push_notification(
                user_id=to,
                title=f"Message from {from_}",
                body=text[:100],  # Truncate long messages
                chat_id=norm_id
            ))

        return msg


# -----------------------
# SSE
# -----------------------
subscribers: list[asyncio.Queue] = []


async def _broadcast(msg: Message):
    """Broadcast a Message ORM object to all SSE subscribers using schema serialization"""
    from .schemas import MessageSchema

    payload = MessageSchema.model_validate(msg).model_dump(by_alias=True, mode='json')
    logging.info(f"📡 Broadcasting to SSE subscribers: {payload}")
    bad = []
    for q in subscribers:
        try:
            await q.put(payload)
        except Exception:
            bad.append(q)
    for q in bad:
        try:
            subscribers.remove(q)
        except ValueError:
            pass


@app.get("/api/v1/stream")
async def stream_messages():
    async def event_generator(q: asyncio.Queue):
        try:
            while True:
                msg = await q.get()
                yield f"data: {json_dumps(msg)}\n\n"
        finally:
            try:
                subscribers.remove(q)
            except ValueError:
                pass

    q = asyncio.Queue()
    subscribers.append(q)
    return StreamingResponse(event_generator(q), media_type="text/event-stream")


def json_dumps(obj):
    import json

    return json.dumps(obj, default=str, separators=(",", ":"))


# -----------------------
# AI
# -----------------------
# Gemini (active)
async def ai_reply(question: str, metadata: dict | None = None) -> str:
    if not GEMINI_API_KEY:
        return "(missing GEMINI_API_KEY)"
    try:
        # Use REST API directly with v1beta and gemini-2.5-flash
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [{"text": question}]
            }]
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip() or "(empty Gemini reply)"
    except Exception as e:
        logging.error(f"❌ Gemini error: {e}")
        return f"(AI error: {e})"

# Daisy (commented out - chatflows broken, uncomment when fixed)
# async def ai_reply(question: str, metadata: dict | None = None) -> str:
#     # Daisy integration
#     if not DAISY_API_URL:
#         return "(missing DAISY_API_URL)"
#
#     try:
#         headers = {"Content-Type": "application/json"}
#         # Add auth header only if API key is provided
#         if DAISY_API_KEY:
#             headers["Authorization"] = f"Bearer {DAISY_API_KEY}"
#
#         payload = {"question": question}
#
#         async with httpx.AsyncClient() as client:
#             response = await client.post(DAISY_API_URL, json=payload, headers=headers, timeout=30.0)
#             response.raise_for_status()
#             data = response.json()
#
#             # Extract the result from Daisy response
#             result = data.get("result", "")
#             return result.strip() or "(empty Daisy reply)"
#
#     except Exception as e:
#         logging.error(f"❌ Daisy error: {e}")
#         return f"(Daisy error: {e})"


# -----------------------
# REST: Send message
# -----------------------
@app.post("/api/v1/messages/send")
async def send_message(payload: dict = Body(...), current_user: str = Depends(get_current_user)):
    logging.info(f"📨 Received send request: {payload}")
    chat_id = payload.get("chatId")
    to = payload.get("to")
    text = payload.get("text", "")
    logging.info(f"📨 Extracted - chatId: {chat_id}, to: {to}, text: {text}")
    if not chat_id or not to or not text:
        raise HTTPException(status_code=400, detail="chatId, to, text required")

    # Send via iMessage API first (with whitelist check)
    sent = await send_imessage(to, text)
    if not sent:
        raise HTTPException(status_code=403, detail="Recipient not in whitelist or send failed")

    # Save your message to database
    user_msg = await save_message(chat_id, MY_IMESSAGE_NUMBER or "me", to, text, True)

    # Generate AI reply in background
    async def handle_ai():
        try:
            reply = await ai_reply(text, metadata={"chatId": chat_id, "from": to})
            if reply:
                await save_message(chat_id, "agent", to, reply, False)
                # Note: AI reply saved to DB but not auto-sent via iMessage
                # (webhook will handle sending when response comes back)
        except Exception as e:
            logging.error(f"❌ AI reply error: {e}")

    asyncio.create_task(handle_ai())

    return {"ok": True, "message": MessageSchema.model_validate(user_msg).model_dump(by_alias=True, mode='json')}


# -----------------------
# Webhook
# -----------------------
@app.post("/new-message")
async def new_message(request: Request, x_webhook_secret: str = Header(None)):
    if x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    text = body.get("text", "")
    from_number = body.get("from")
    chat_id = body.get("chatId", from_number)
    is_from_me = body.get("is_from_me", body.get("isFromMe", False))

    logging.info(f"📩 Received webhook event: {body}")

    if not text:
        return {"status": "ignored", "reason": "empty"}

    await save_message(
        chat_id, from_number, MY_IMESSAGE_NUMBER or "me", text, bool(is_from_me)
    )

    # Generate AI reply for all human messages (including your own!)
    # Only skip if the message is FROM the AI agent itself (to avoid loops)
    if from_number != "agent":
        try:
            reply = await ai_reply(
                text, metadata={"chatId": chat_id, "from": from_number}
            )
        except Exception as e:
            logging.error(f"❌ AI reply error: {e}")
            reply = f"(AI error: {e})"

        if reply:
            # Save AI reply to database
            await save_message(chat_id, "agent", MY_IMESSAGE_NUMBER, reply, False)

            # Send reply back via iMessage
            # If texting yourself, send to your own number
            reply_to = from_number if from_number else MY_IMESSAGE_NUMBER
            await send_imessage(reply_to, reply)

            return {"status": "ok", "stored": True, "reply": reply}

    return {"status": "ok", "stored": True}


# -----------------------
# AUTH Endpoints
# -----------------------
from .auth import hash_password, verify_password, create_access_token
from .models import User
from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    phone: str = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


@app.post("/api/v1/auth/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """Create a new user account"""
    async with AsyncSessionLocal() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == request.email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create new user
        hashed_password = hash_password(request.password)
        new_user = User(
            email=request.email,
            phone=request.phone,
            password_hash=hashed_password
        )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        # Create access token
        access_token = create_access_token(data={"sub": new_user.id})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "phone": new_user.phone
            }
        }


@app.post("/api/v1/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login to existing account"""
    async with AsyncSessionLocal() as session:
        # Find user by email
        result = await session.execute(select(User).where(User.email == request.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password"
            )

        # Create access token
        access_token = create_access_token(data={"sub": user.id})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "phone": user.phone
            }
        }


# -----------------------
# REST: Chats & Messages (Protected)
# -----------------------
from .auth import get_current_user

@app.get("/api/v1/chats", response_model=list[ChatSchema])
async def list_chats(current_user: str = Depends(get_current_user)):
    """Get all chats for authenticated user"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()
        return chats


@app.get("/api/v1/messages", response_model=list[MessageSchema])
async def list_messages(chatId: str, limit: int = 50, current_user: str = Depends(get_current_user)):
    """Get messages for a chat (authenticated users only)"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Message).where(Message.chat_id == chatId).order_by(Message.timestamp)
        )
        msgs = result.scalars().all()
        return msgs[-limit:]


@app.post("/api/v1/chats", response_model=ChatSchema)
async def create_chat(payload: dict = Body(...), current_user: str = Depends(get_current_user)):
    """Create a new chat"""
    phone_number = payload.get("phoneNumber")
    if not phone_number:
        raise HTTPException(status_code=400, detail="phoneNumber is required")

    async with AsyncSessionLocal() as session:
        # Check if chat already exists
        result = await session.execute(select(Chat).where(Chat.name == phone_number))
        existing_chat = result.scalar_one_or_none()

        if existing_chat:
            return existing_chat

        # Create new chat
        new_chat = Chat(
            id=str(uuid.uuid4()),
            name=phone_number
        )
        session.add(new_chat)
        await session.commit()
        await session.refresh(new_chat)
        return new_chat


@app.delete("/api/v1/chats/{chat_id}")
async def delete_chat(chat_id: str, current_user: str = Depends(get_current_user)):
    """Delete a chat and all its messages"""
    async with AsyncSessionLocal() as session:
        # Delete all messages first
        await session.execute(
            select(Message).where(Message.chat_id == chat_id)
        )
        messages = (await session.execute(
            select(Message).where(Message.chat_id == chat_id)
        )).scalars().all()

        for msg in messages:
            await session.delete(msg)

        # Delete the chat
        result = await session.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()

        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        await session.delete(chat)
        await session.commit()

        return {"status": "deleted", "chatId": chat_id}


# -----------------------
# APNs Device Registration
# -----------------------
@app.post("/api/v1/device/register")
async def register_device(payload: dict = Body(...)):
    """Register iOS device token for push notifications"""
    user_id = payload.get("userId")
    device_token = payload.get("deviceToken")

    if not user_id or not device_token:
        raise HTTPException(status_code=400, detail="userId and deviceToken required")

    device_tokens[user_id] = device_token
    logging.info(f"📱 Registered device token for user {user_id}")

    return {"ok": True, "message": "Device registered for push notifications"}


@app.delete("/api/v1/device/unregister")
async def unregister_device(payload: dict = Body(...)):
    """Unregister device token (e.g., on logout)"""
    user_id = payload.get("userId")

    if user_id in device_tokens:
        del device_tokens[user_id]
        logging.info(f"📱 Unregistered device token for user {user_id}")

    return {"ok": True, "message": "Device unregistered"}


# -----------------------
# Startup: seed demo chat
# -----------------------
@app.on_event("startup")
async def on_startup():
    await init_db()

    # Initialize APNs
    if push_service.init_apns():
        logging.info("📱 APNs initialized successfully")
    else:
        logging.info("📱 APNs not configured (push notifications disabled)")

    demo_chat_id = "swift-demo"
    async with AsyncSessionLocal() as session:
        exists = await session.get(Chat, demo_chat_id)
        if not exists:
            session.add(Chat(id=demo_chat_id, name="Swift Demo"))
            await session.commit()
            await save_message(
                demo_chat_id, "system", "user", "Welcome to the demo chat!", False
            )
    logging.info("💬 Seeded demo chat for simulator")
