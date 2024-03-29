from pydantic import BaseModel
from typing import Optional, List


class StreamBase(BaseModel):
    name: str
    stream_key: str
    allow_live: bool
    marathon_name: str

    class Config:
        orm_mode = True


class NewStream(BaseModel):
    name: str
    allow_live: bool


class ShowLiveStream(BaseModel):
    client_id: Optional[int] = None
    region: Optional[str] = None

    class Config:
        orm_mode = True


class ShowStream(StreamBase):
    live_stream: Optional[ShowLiveStream] = None

    class Config:
        orm_mode = True


class MarathonBase(BaseModel):
    name: str

    class Config:
        orm_mode = True


class ShowMarathon(MarathonBase):
    pass


class NewMarathon(MarathonBase):
    pass
