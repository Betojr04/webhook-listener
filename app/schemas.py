# app/schemas.py
from pydantic import BaseModel, Field, field_serializer
from datetime import datetime


class MessageSchema(BaseModel):
    id: str
    chat_id: str = Field(alias="chatId")
    from_user: str = Field(alias="from")
    to_user: str = Field(alias="to")
    text: str
    timestamp: datetime
    is_from_me: bool = Field(alias="isFromMe")

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat(timespec="microseconds") + "Z"

    class Config:
        from_attributes = True  # Pydantic v2
        populate_by_name = True  # Pydantic v2


class ChatSchema(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True  # Pydantic v2
