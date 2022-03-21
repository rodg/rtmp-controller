import requests
from typing import Optional, List
from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
import random, string

from . import schemas, models
from .db import engine, get_db

domain = "popola.dev"

schemas.Base.metadata.create_all(engine)

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generate_stream_key():
    return "".join(random.choice(string.ascii_letters) for _ in range(25))


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/drop/{name}", response_model=models.ShowStream)
async def drop_stream(
    name: str, change_key: Optional[bool] = None, db: Session = Depends(get_db)
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    try:
        stream = db.execute(stmt).scalar_one()
    except Exception as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    params = {"app": "live", "name": name}
    response = requests.get(
        f"https://{stream.live_stream.region}.{domain}/control/drop/publisher",
        params=params,
    )
    print(response.status_code)
    if change_key:
        stream.stream_key = generate_stream_key()
        try:
            db.commit()
            return stream
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stream key changing failed!!",
            )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to communicate with RTMP!",
        )
    return stream


@app.get("/streams", response_model=List[models.ShowStream])
async def get_streams(
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream)
    result = db.execute(stmt).scalars().all()
    print(result[0])
    return result


@app.get("/livestreams", response_model=List[models.ShowLiveStream])
async def get_live_streams(
    db: Session = Depends(get_db),
):
    stmt = select(schemas.LiveStream)
    result = db.execute(stmt).scalars().all()
    return result


@app.post("/streams", response_model=models.StreamBase)
async def create_stream(
    stream: models.NewStream,
    db: Session = Depends(get_db),
):
    new_key = generate_stream_key()
    new_stream = schemas.Stream(**{"stream_key": new_key, **stream.dict()})
    db.add(new_stream)
    db.commit()
    print(new_stream)
    return new_stream


@app.delete("/streams/{name}")
async def delete_stream(
    name: str,
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    try:
        stream = db.execute(stmt).scalar_one()
    except Exception as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if stream.live_stream:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't delete a stream that is currently live!",
        )
    else:
        db.delete(stream)
        db.commit()
    return


@app.put("/streams/{name}", response_model=models.ShowStream)
async def change_key(
    name: str,
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    try:
        stream = db.execute(stmt).scalar_one()
    except Exception as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if stream.live_stream:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't change the stream key of a stream that is currently live!",
        )
    else:
        stream.stream_key = generate_stream_key()
        db.commit()
    return stream


@app.post("/publish")
async def on_publish(
    request: Request,
    name: str = Form(...),
    addr: str = Form(...),
    clientid: int = Form(...),
    tcurl: str = Form(...),
    streamkey: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    stream: schemas.Stream = db.execute(stmt).scalar_one()
    body = await request.form()
    print(body)
    if stream.allow_live and stream.stream_key == streamkey:
        db.add(
            schemas.LiveStream(
                stream_id=stream.id, client_id=clientid, region=tcurl[7:9]
            )
        )
        db.commit()
        print(f"Add stream with client id: {clientid} in Region: {tcurl[7:9]}")
        return
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@app.post("/done")
async def on_done(
    request: Request,
    name: str = Form(...),
    addr: str = Form(...),
    streamkey: Optional[str] = Form(None),
    clientid: str = Form(...),
    db: Session = Depends(get_db),
):
    stmt = delete(schemas.LiveStream).where(schemas.LiveStream.client_id == clientid)
    result = db.execute(stmt)
    print(result)
    db.commit()
    body = await request.form()
    print(body)

    # if streamkey == "twitch":
    #     ip_addr = socket.gethostbyname("remote")
    #     raise HTTPException(
    #         status_code=308, headers={"Location": f"rtmp://{ip_addr}/live/"}
    #     )
    # else:
    #     return {"It": "worked"}
