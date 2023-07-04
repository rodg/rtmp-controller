import os
import random
import string
from typing import List, Optional

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models, schemas
from .db import engine, get_db

load_dotenv()
domain = os.environ.get("RTMP_DOMAIN")

schemas.Base.metadata.create_all(engine)

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:9090",
]

app.add_middleware(
    CORSMiddleware, allow_methods=["*"], allow_headers=["*"], allow_origins=["*"]
)


def generate_stream_key():
    return "".join(random.choice(string.ascii_letters) for _ in range(25))


@app.put("/drop/{name}", response_model=models.ShowStream)
async def drop_stream(
    name: str, change_key: Optional[bool] = None, db: Session = Depends(get_db)
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    try:
        stream: schemas.Stream = db.execute(stmt).scalar_one()
    except Exception as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    if not stream.live_stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No livestream to drop!",
        )

    params = {"app": "live", "name": name}
    try:
        response = requests.get(
            f"https://{stream.live_stream.region}.{domain}/control/drop/publisher",
            params=params,
        )
    except:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send control request to RTMP server!",
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bad response from RTMP server when attempting to drop stream!",
        )
    else:
        try:
            db.delete(stream.live_stream)
            db.commit()
        except:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete livestream from DB!",
            )

    print(response.status_code)
    print(change_key)
    if change_key:
        stream.stream_key = generate_stream_key()
        try:
            db.flush()
            db.commit()
            print("Stream key changed")
            return stream
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stream key changing failed!!",
            )
    return stream


@app.get("/marathons", response_model=List[models.ShowMarathon])
async def get_marathons(
    db: Session = Depends(get_db),
):
    return db.execute(select(schemas.Marathon)).scalars().all()


@app.get("/marathons/{thon_name}/streams", response_model=List[models.ShowStream])
async def get_streams(
    thon_name: str,
    db: Session = Depends(get_db),
):
    try:
        marathon = db.execute(
            select(schemas.Marathon).where(schemas.Marathon.name == thon_name)
        ).scalar_one()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marathon not found!",
        )

    return marathon.streams

    stmt = select(schemas.Stream).where(schemas.Stream.marathon_name == thon_name)
    result = db.execute(stmt).scalars().all()
    return result


@app.get(
    "/marathon/{thon_name}/livestreams", response_model=List[models.ShowLiveStream]
)
async def get_live_streams(
    thon_name: str,
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream).where(schemas.Stream.marathon_name == thon_name)
    result = db.execute(stmt).scalars().all()
    ans = []
    for stream in result:
        if stream.live_stream:
            ans.append(stream.live_stream)
    return ans


@app.post("/marathons/{thon_name}/streams", response_model=models.StreamBase)
async def create_stream(
    thon_name: str,
    stream: models.NewStream,
    db: Session = Depends(get_db),
):
    try:
        marathon = db.execute(
            select(schemas.Marathon).where(schemas.Marathon.name == thon_name)
        ).scalar_one()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marathon not found!",
        )
    new_key = generate_stream_key()
    new_stream = schemas.Stream(
        **{"stream_key": new_key, "marathon_name": thon_name, **stream.dict()}
    )
    db.add(new_stream)
    db.commit()
    print(new_stream)
    return new_stream


@app.post("/marathons", response_model=models.ShowMarathon)
async def create_thon(
    thon: models.NewMarathon,
    db: Session = Depends(get_db),
):
    new_thon = schemas.Marathon(**thon.dict())
    db.add(new_thon)
    db.commit()
    print(new_thon)
    return new_thon


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


@app.put("/marathons/{thon_name}/streams/{name}", response_model=models.ShowStream)
async def change_key(
    thon_name: str,
    name: str,
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    try:
        stream = db.execute(stmt).scalar_one()
    except Exception as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if stream.marathon_name != thon_name:
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
