from fastapi import FastAPI, Form, Request
from pyngrok import ngrok
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import nest_asyncio
from starlette.responses import FileResponse
from fastapi import FastAPI, File, UploadFile

app = FastAPI()

templates = Jinja2Templates(directory = "templates")

@app.get('/', response_class=HTMLResponse)
async def home(request : Request) :
    return templates.TemplateResponse("input2.html", context={"request": request})

@app.post("/info")
async def info(file : bytes = File(...)):

    import requests
    import uuid
    import time
    import json

    with open('./data/api_url.txt','r') as api_url :
        api_url = api_url.readline()

    with open('./data/secret_key.txt','r') as secret_key :
        secret_key = secret_key.readline()

    image_file = './data/...'
    output_file = './output.json'

    request_json = {
        'images': [
            {
                'format': 'png',
                'name': 'demo',
                'templateIds': [11112]
            }
        ],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000))
    }

    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    files = [
      ('file', open(image_file,'rb'))
    ]
    headers = {
      'X-OCR-SECRET': secret_key
    }

    response = requests.request("POST", api_url, headers=headers, data = payload, files = files)

    res = json.loads(response.text.encode('utf8'))


    with open(output_file, 'w', encoding='utf-8') as outfile:
        json.dump(res, outfile, indent=4, ensure_ascii=False)

    # 데이터 프레임 만들기
    # 날짜
    date = res['images'][0]['fields'][0]['inferText'].split('\n')

    # 시간
    time = res['images'][0]['fields'][1]['inferText'].split('\n')

    # 수집동의
    checkbox = res['images'][0]['fields'][2]['inferText'].split('\n')

    # 시군구
    sigungu = res['images'][0]['fields'][3]['inferText'].split('\n')

    # 전화번호
    tel = res['images'][0]['fields'][4]['inferText'].split('\n')

    # 비고
    extra = res['images'][0]['fields'][5]['inferText'].split('\n')

    # max length
    length = 0
    li = [date, time, checkbox, sigungu, tel, extra]
    for i in li :
        length = max(len(i), length)


    # 패딩 맞춰주기
    import numpy as np
    df_li = []
    for i in li :
         df_li.append(np.pad(i, (0,length - len(i)), 'constant', constant_values=0))

    import pandas as pd
    df = pd.DataFrame(df_li).transpose()
    df.columns = ['date', 'time', 'checkbox', 'sigungu', 'tel', 'extra']

    # 공백 및 특수문자 제거
    for col in ['date', 'time', 'checkbox', 'sigungu', 'tel', 'extra'] :
        df[col]= df[col].str.replace(' ', '')
        df[col]= df[col].str.replace('.', '')

    # 체크박스 형식 통일
    df.loc[(df['checkbox']=='v'), 'checkbox'] = 'V'
    df.to_csv('covid19.csv')

    return FileResponse('./covid19.csv', media_type='application/octet-stream',filename='covid19')


ngrok_tunnel = ngrok.connect(8000)
print ('Public URL:', ngrok_tunnel.public_url)
nest_asyncio.apply()
uvicorn.run(app, host='0.0.0.0', port=8000)
