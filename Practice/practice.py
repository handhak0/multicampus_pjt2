from fastapi import FastAPI, Form, Request
from pyngrok import ngrok
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import nest_asyncio
from starlette.responses import FileResponse
from fastapi import FastAPI, File, UploadFile
from typing import List
import os


app = FastAPI()

templates = Jinja2Templates(directory = "templates")

@app.get('/', response_class=HTMLResponse)
async def home(request : Request) :
    return templates.TemplateResponse("input2.html", context={"request": request})


@app.post("/files")
async def image(request : Request, FileName: UploadFile = File(...)):
    return {"filename": FileName.filename}



ngrok_tunnel = ngrok.connect(8000)
print ('Public URL:', ngrok_tunnel.public_url)
nest_asyncio.apply()
uvicorn.run(app, host='0.0.0.0', port=8000)