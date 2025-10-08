# app/services/push.py
import os
import logging
from typing import Optional, Dict
from dotenv import load_dotenv

from aioapns import APNs, NotificationRequest
from aioapns.common import PushType

# Load environment variables
load_dotenv()

APNS_KEY_ID = os.getenv("APNS_KEY_ID")
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID")
APNS_AUTH_KEY_PATH = os.getenv("APNS_AUTH_KEY_PATH")
APNS_TOPIC = os.getenv("APNS_TOPIC")  # bundle id
APNS_USE_SANDBOX = os.getenv("APNS_USE_SANDBOX", "true").lower() == "true"

_client: Optional[APNs] = None


def init_apns() -> bool:
    """
    Initialize APNs Token-based client. Returns True if ready.
    """
    global _client
    if not (APNS_KEY_ID and APNS_TEAM_ID and APNS_AUTH_KEY_PATH and APNS_TOPIC):
        logging.warning("APNs ENV incomplete; push disabled.")
        return False

    try:
        _client = APNs(
            key=APNS_AUTH_KEY_PATH,
            key_id=APNS_KEY_ID,
            team_id=APNS_TEAM_ID,
            topic=APNS_TOPIC,
            use_sandbox=APNS_USE_SANDBOX,
        )
        logging.info(f"✅ APNs ready (sandbox={APNS_USE_SANDBOX}, topic={APNS_TOPIC})")
        return True
    except Exception as e:
        logging.error(f"❌ APNs init failed: {e}")
        return False


def is_ready() -> bool:
    return _client is not None


async def push_alert(
    device_token: str,
    title: str,
    body: str,
    *,
    badge: Optional[int] = None,
    sound: Optional[str] = "default",
    thread_id: Optional[str] = None,
    custom: Optional[Dict] = None,
) -> None:
    """
    Sends a visible alert push.
    """
    if not is_ready():
        raise RuntimeError("APNs not initialized")

    alert = {"title": title, "body": body}
    aps = {"alert": alert, "sound": sound}

    if badge is not None:
        aps["badge"] = badge

    if thread_id:
        aps["thread-id"] = thread_id

    payload = {"aps": aps}
    if custom:
        payload.update(custom)

    request = NotificationRequest(
        device_token=device_token,
        message=payload,
        push_type=PushType.ALERT,
    )

    await _client.send_notification(request)


async def push_silent(
    device_token: str,
    *,
    custom: Optional[Dict] = None,
) -> None:
    """
    Sends a background (silent) push (content-available=1).
    Your app must have Background Modes -> Remote notifications enabled.
    """
    if not is_ready():
        raise RuntimeError("APNs not initialized")

    payload = {"aps": {"content-available": 1}}
    if custom:
        payload.update(custom)

    request = NotificationRequest(
        device_token=device_token,
        message=payload,
        push_type=PushType.BACKGROUND,
    )

    await _client.send_notification(request)
