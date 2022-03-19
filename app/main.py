import requests
from typing import Optional, List
from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from . import schemas, models
from .db import engine, get_db

domain = "rtmp"

schemas.Base.metadata.create_all(engine)

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/drop/{name}")
async def drop_stream(name: str, db: Session = Depends(get_db)):
    # TODO get stream from DB to resolve region
    params = {"app": "live", "name": name}
    response = requests.get(f"http://{domain}/control/drop/publisher", params=params)
    print(response.status_code)
    return


@app.get("/streams", response_model=List[models.ShowStream])
async def get_streams(
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream)
    result = db.execute(stmt).scalars().all()
    print(result)
    return result


@app.post("/streams")
async def create_stream(
    stream: models.NewStream,
    db: Session = Depends(get_db),
):
    new_stream = schemas.Stream(**stream.dict())
    db.add(new_stream)
    db.commit()
    print(new_stream)
    return


@app.delete("/streams/{name}")
async def delete_stream(
    name: str,
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    stream = db.execute(stmt).scalar_one()
    if stream.live_stream:
        print("Stream is live can't delete!")
    else:
        db.delete(stream)
        db.commit()
    return


@app.put("/streams/{name}")
async def change_key(
    name: str,
    stream_key: str,
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    stream: schemas.Stream = db.execute(stmt).scalar_one()
    if stream.live_stream:
        print("Stream is live can't delete!")
    else:
        stream.stream_key = stream_key
        db.commit()
    return


@app.post("/publish")
async def on_publish(
    request: Request,
    name: str = Form(...),
    addr: str = Form(...),
    clientid: int = Form(...),
    streamkey: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    stmt = select(schemas.Stream).where(schemas.Stream.name == name)
    stream: schemas.Stream = db.execute(stmt).scalar_one()
    body = await request.form()
    print(body)
    if stream.allow_live and stream.stream_key == streamkey:
        db.add(schemas.LiveStream(stream_id=stream.id, client_id=clientid))
        db.commit()
        print(f"Add stream with client id: {clientid}")
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
    db.execute(stmt)
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
