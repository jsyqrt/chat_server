import time
from sqlalchemy.orm import relationship
from zchat.db import db
from zchat.models.user import User

class ChatSession(db.Model):
    """聊天会话模型"""
    __tablename__ = 'CHAT_SESSION'

    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False, default='general')  # 会话类型，如general, project, etc.
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    created_at = db.Column(db.REAL, default=time.time())
    updated_at = db.Column(db.REAL, default=time.time(), onupdate=time.time)
    is_archived = db.Column(db.Boolean, default=False)  # 是否已归档
    session_metadata = db.Column(db.JSON, default={})  # 存储会话元数据
    roadmap_id = db.Column(db.String, nullable=True)  # 关联的roadmap id

    # 关系
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        db.Index('index_CHAT_SESSION_title', 'title', unique=False),
        db.Index('index_CHAT_SESSION_type', 'type', unique=False),
        db.Index('index_CHAT_SESSION_user_id', 'user_id', unique=False),
        db.Index('index_CHAT_SESSION_created_at', 'created_at', unique=False),
        db.Index('index_CHAT_SESSION_updated_at', 'updated_at', unique=False),
        db.Index('index_CHAT_SESSION_is_archived', 'is_archived', unique=False),
        db.Index('index_CHAT_SESSION_roadmap_id', 'roadmap_id', unique=False),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_archived": self.is_archived,
            "session_metadata": self.session_metadata,
            "message_count": len(self.messages) if self.messages else 0,
            "roadmap_id": self.roadmap_id
        }


class ChatMessage(db.Model):
    """聊天消息模型"""
    __tablename__ = 'CHAT_MESSAGE'

    id = db.Column(db.String, primary_key=True)
    session_id = db.Column(db.String, db.ForeignKey('CHAT_SESSION.id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)  # 'user' 或 'ai'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.REAL, default=time.time())
    message_metadata = db.Column(db.JSON, default={})  # 存储消息元数据

    # 关系
    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        db.Index('index_CHAT_MESSAGE_session_id', 'session_id', unique=False),
        db.Index('index_CHAT_MESSAGE_sender_type', 'sender_type', unique=False),
        db.Index('index_CHAT_MESSAGE_timestamp', 'timestamp', unique=False),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "sender_type": self.sender_type,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.message_metadata
        }