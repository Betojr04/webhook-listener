# app/bots.py
"""
Bot definitions and routing for AI Agents platform
"""

import os
import logging
import httpx
from typing import Optional

# Daisy+ configuration (when available)
DAISY_API_URL = os.getenv("DAISY_API_URL")
DAISY_API_KEY = os.getenv("DAISY_API_KEY")

# Gemini configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Bot definitions - these will be sent to the frontend
BOTS = [
    {
        "id": "daisy-plus",
        "name": "Daisy+",
        "emoji": "🌼",
        "description": "Your intelligent personal assistant",
        "color": "#FF6B9D",
        "use_daisy_api": True,  # Will use Daisy+ API when available
        "system_prompt": "You are Daisy+, an intelligent and friendly personal assistant. You help users with tasks, answer questions, and provide helpful information. Be warm, professional, and concise.",
    },
    {
        "id": "code-assistant",
        "name": "Code Assistant",
        "emoji": "👨‍💻",
        "description": "Expert help with coding and debugging",
        "color": "#007AFF",
        "use_daisy_api": False,
        "system_prompt": "You are a senior software engineer and coding expert. Help users debug code, explain programming concepts, write clean code, and solve technical problems. Be precise, thorough, and include code examples when helpful.",
    },
    {
        "id": "research-bot",
        "name": "Research Bot",
        "emoji": "🔬",
        "description": "Deep research and analysis",
        "color": "#34C759",
        "use_daisy_api": False,
        "system_prompt": "You are a research assistant specializing in deep analysis and factual information. Provide well-researched, detailed answers with sources when possible. Be thorough, accurate, and objective.",
    },
    {
        "id": "task-planner",
        "name": "Task Planner",
        "emoji": "📅",
        "description": "Schedule and organize your tasks",
        "color": "#FF9500",
        "use_daisy_api": False,
        "system_prompt": "You are a productivity assistant specializing in task management and organization. Help users break down projects, set priorities, create schedules, and stay organized. Be practical and actionable.",
    },
    {
        "id": "writer",
        "name": "Creative Writer",
        "emoji": "✍️",
        "description": "Professional writing assistance",
        "color": "#AF52DE",
        "use_daisy_api": False,
        "system_prompt": "You are a professional writing assistant. Help users write emails, blog posts, social media content, and creative writing. Focus on clarity, engagement, and proper grammar.",
    },
    {
        "id": "business-advisor",
        "name": "Business Advisor",
        "emoji": "💼",
        "description": "Strategic business guidance",
        "color": "#5856D6",
        "use_daisy_api": False,
        "system_prompt": "You are a business consultant with expertise in strategy, operations, and growth. Help users make informed business decisions, solve problems, and identify opportunities. Be strategic and data-driven.",
    },
]

DEFAULT_BOT_ID = "daisy-plus"


def get_bot(bot_id: str) -> Optional[dict]:
    """Get bot configuration by ID"""
    for bot in BOTS:
        if bot["id"] == bot_id:
            return bot
    return None


def get_all_bots() -> list[dict]:
    """Get all available bots"""
    return BOTS


async def route_message_to_bot(bot_id: str, user_message: str) -> str:
    """
    Route user message to the appropriate bot handler
    Returns the bot's response
    """
    bot = get_bot(bot_id)
    if not bot:
        bot = get_bot(DEFAULT_BOT_ID)

    # If bot uses Daisy+ API and it's configured, use it
    if bot.get("use_daisy_api") and DAISY_API_URL and DAISY_API_KEY:
        try:
            response = await call_daisy_api(user_message)
            return response
        except Exception as e:
            logging.warning(f"⚠️ Daisy+ API failed, falling back to Gemini: {e}")
            # Fall through to Gemini

    # Otherwise use Gemini with bot-specific system prompt
    return await call_gemini(user_message, bot["system_prompt"])


async def call_daisy_api(question: str) -> str:
    """Call Daisy+ API for response"""
    if not DAISY_API_URL:
        raise ValueError("DAISY_API_URL not configured")

    try:
        headers = {"Content-Type": "application/json"}
        if DAISY_API_KEY:
            headers["Authorization"] = f"Bearer {DAISY_API_KEY}"

        payload = {"question": question}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                DAISY_API_URL, json=payload, headers=headers, timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            # Extract the result from Daisy response
            result = data.get("result", "")
            return result.strip() or "(empty Daisy+ reply)"

    except Exception as e:
        logging.error(f"❌ Daisy+ error: {e}")
        raise


async def call_gemini(question: str, system_prompt: str = None) -> str:
    """Call Gemini API with optional system prompt"""
    if not GEMINI_API_KEY:
        return "(missing GEMINI_API_KEY)"

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

        # Combine system prompt with user question if provided
        if system_prompt:
            full_prompt = f"{system_prompt}\n\nUser: {question}\n\nAssistant:"
        else:
            full_prompt = question

        payload = {"contents": [{"parts": [{"text": full_prompt}]}]}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            return text.strip() or "(empty Gemini reply)"
    except Exception as e:
        logging.error(f"❌ Gemini error: {e}")
        return f"(AI error: {e})"
