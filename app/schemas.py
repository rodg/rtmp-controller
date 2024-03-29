from typing import List
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String)
    password = Column(String)


class Marathon(Base):
    __tablename__ = "marathon"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, unique=True)
    password = Column(String)

    streams: List["Stream"] = relationship("Stream")


class Stream(Base):
    __tablename__ = "streams"
    __table_args__ = (UniqueConstraint("name"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    stream_key = Column(String)
    allow_live = Column(Boolean)
    marathon_name = Column(String, ForeignKey("marathon.name"))

    marathon: Marathon = relationship("Marathon", back_populates="streams")
    live_stream: "LiveStream" = relationship(
        "LiveStream", back_populates="stream", cascade="delete", uselist=False
    )


class LiveStream(Base):
    __tablename__ = "live_streams"
    __table_args__ = (UniqueConstraint("stream_id"),)
    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id"))
    client_id = Column(Integer)
    region = Column(String)

    stream: "Stream" = relationship(
        "Stream", back_populates="live_stream", uselist=False
    )
