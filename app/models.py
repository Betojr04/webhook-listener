from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from .db import Base


def _now():
    return datetime.now(timezone.utc)


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    messages = relationship("Message", back_populates="chat")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String, ForeignKey("chats.id"), nullable=False)
    from_user = Column(String)
    to_user = Column(String)
    text = Column(String)
    timestamp = Column(DateTime, default=_now)
    is_from_me = Column(Boolean, default=False)

    chat = relationship("Chat", back_populates="messages")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)
    is_active = Column(Boolean, default=True)
