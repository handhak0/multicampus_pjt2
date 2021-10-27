'''모듈 불러오기'''
from fastapi import FastAPI, File, UploadFile, Request, Form
from typing import List # 파일 여러 개 받기
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn

import requests
import uuid
import time
import json

import numpy as np
import pandas as pd


'''전처리 함수'''
def making_df(li, col_names, include_extra = None) :

    # max length
    length = 0
    for i in li:
        length = max(len(i), length)

    # 패딩 맞춰주기
    df_li = []
    for i in li:
        df_li.append(np.pad(i, (0, length - len(i)), 'constant', constant_values=0))

    df = pd.DataFrame(df_li).transpose()
    df.columns = col_names

    df['extra'] = '-'

    try :
        for i in df[df[include_extra].str.contains('외')].index:
            # '외'이후를 extra에 저장
            df.extra[i] = '외' + df[df[include_extra].str.contains('외')][include_extra][i].split('외')[1]

            # tel에서 '외'이후 버림
            df[include_extra][i] = df[df[include_extra].str.contains('외')][include_extra][i].split('외')[0]
    except :
        pass

    # 공백 및 특수문자 제거
    for col in col_names:
        df[col] = df[col].str.replace(' ', '')
        df[col] = df[col].str.replace('.', '')


    # 전화번호 형식 통일
    for kiho in ['-', ',', '~', '.'] :
        df['tel'] = df['tel'].str.replace(kiho, '')

    # 010 미표기 처리
    for i in range(len(df)):
        if df['tel'][i].startswith('010'):
            df['tel'][i] = df['tel'][i][3:]
        df['tel'][i] = '010' + '-' + df['tel'][i][0:4] + '-' + df['tel'][i][4:]



    try :
        # 체크박스 형식 통일
        for i in ['v', 'r', 'o', 'O', '0', 'ㅇ','○','b','6','9','·','q','a']:
            df.loc[(df['checkbox'] == i), 'checkbox'] = 'V'
    except : pass


    # ' " ' 처리
    df.replace({'11':'"', '1/':'"', '//':'"', '/1':'"', '〃':'"'}, inplace = True)

    for i in range(len(df)):
        for col in df.columns:
            if df[col][i] == '"':
                df[col][i] = df[col][i - 1]


    # 숫자형식 컬럼에 한글 처리
    for col in ['date', 'dtime', 'tel'] :
        df[col] = df[col].str.replace('나', '4')
        df[col] = df[col].str.replace('이', '9')
        df[col] = df[col].str.replace('o', '0')
        df[col] = df[col].str.replace('O', '0')
        df[col] = df[col].str.replace('ㅇ', '0')



    # 시간 형식 통일
    df['dtime'] = df['dtime'].str.replace('.', '')

    for i in range(len(df)):
        if df['dtime'][i].find(':') < 0:
            if len(df['dtime'][i]) == 2:
                df['dtime'][i] = df['dtime'][i][0] + ':' + df['dtime'][i][1]
            elif len(df['dtime'][i]) == 3:
                df['dtime'][i] = df['dtime'][i][0] + ':' + df['dtime'][i][1:]
            else:
                df['dtime'][i] = df['dtime'][i][0:2] + ':' + df['dtime'][i][2:]

    # 날짜 형식 통일
    df['date'] = df['date'].str.replace(',', '')

    for i in range(df.shape[0]) :
        if len(df['date'][i])>=6 :
            df['date'][i] = df['date'][i][2:]
        if len(df['date'][i]) >= 5 and df['date'][i][2] == '1':
            df['date'][i] = df['date'][i][:2] + df['date'][i][3:]



    for i in range(len(df)):
        if df['date'][i].find('/') < 0:
            if len(df['date'][i]) == 2:
                df['date'][i] = df['date'][i][0] + '/' + df['date'][i][1]
            elif len(df['date'][i]) == 3 and df['date'][i][0] != 1 :
                df['date'][i] = df['date'][i][0] + '/' + df['date'][i][1:]
            elif len(df['date'][i]) == 3 and df['date'][i][0] == 1 and df['date'][i][1] == df['date'][i-1][1]:
                df['date'][i] = df['date'][i][0:2] + '/' + df['date'][i][2]
            elif len(df['date'][i]) == 3 and df['date'][i][0] == 1 and df['date'][i][1] != df['date'][i-1][1]:
                df['date'][i] = df['date'][i][0] + '/' + df['date'][i][1:]
            else:
                df['date'][i] = df['date'][i][0:2] + '/' + df['date'][i][2:]

    # 날짜 / 인식
    try:
        for i in range(1, df.shape[0]):
            slash_idx_i = df['date'][i].find('/')  # i번째 날짜의 '/' 위치
            slash_idx_i_1 = df['date'][i - 1].find('/')  # i-1번째 날짜의 '/' 위치
            i_month = int(df['date'][i][:slash_idx_i])
            i_1_month = int(df['date'][i - 1][:slash_idx_i_1])
            if (i_month < i_1_month) or (i_1_month - i_month > 1):  # 위의 날짜의 달보다 아래 날짜의 달이 작거나 차이가 두 달 이상인 경우
                if df['date'][i][-1] == df['date'][i - 1][-1]:  # 만약에 위의 날짜의 일자의 마지막 글자와 아래 날짜의 마지막 글자가 같으면
                    df['date'][i] = df['date'][i - 1]  # 날짜가 같다는 거니깐 그대로 넣어줌
                else:
                    df['date'][i] = df['date'][i - 1][:slash_idx_i_1] + '/' + str(int(df['date'][i - 1][slash_idx_i_1 + 1:]) + 1)  # 다르면 하루 증가한 값 넣어줌
    except:
        pass

    return df


'''서비스 구현'''
app = FastAPI()


# 처음 서비스 화면
app.mount("/static", StaticFiles(directory="static"), name="static") # 첨부 이미지
templates = Jinja2Templates(directory = "templates") # html 파일

@app.get('/', response_class=HTMLResponse)
async def home(request : Request) :
    return templates.TemplateResponse("input2.html", context={"request": request})


# 파일 업로드, API 요청, csv 파일 다운
@app.post("/uploadfiles/")
async def image(files: List[UploadFile] = File(...), table_num : int = Form(...)):
    if table_num == 11112:
        col_names = ['date', 'dtime', 'checkbox', 'sigungu', 'tel']
    elif table_num == 11119:
        col_names = ['date', 'dtime', 'tel', 'sigungu', 'extra']

    elif table_num == 11126:
        col_names = ['date', 'dtime', 'checkbox', 'tel', 'sigungu', 'extra']
    elif table_num == 11127:
        col_names = ['date', 'dtime', 'checkbox', 'tel', 'sigungu']

    df = pd.DataFrame(index=range(0), columns=col_names) # 빈 데이터 프레임 생성

    for file in files :
        file_location = f"./input/{file.filename}"
        file_format = file.filename[-3:]

        # 첨부된 파일 저장
        with open(file_location, "wb+") as file_object:
            file_object.write(file.file.read())

        # api 요청 url
        with open('./data/api_url.txt', 'r') as api_url:
            api_url = api_url.readline()

        # api key
        with open('./data/secret_key.txt', 'r') as secret_key:
            secret_key = secret_key.readline()

        request_json = {
            'images': [
                {
                    'format': file_format,
                    'name': 'demo',
                    'templateIds': [table_num]
                }
            ],
            'requestId': str(uuid.uuid4()),
            'version': 'V2',
            'timestamp': int(round(time.time() * 1000))
        }

        payload = {'message': json.dumps(request_json).encode('UTF-8')}
        filess = [
            ('file', open(file_location, 'rb'))
        ]
        headers = {
            'X-OCR-SECRET': secret_key
        }

        response = requests.request("POST", api_url, headers=headers, data=payload, files=filess)

        res = json.loads(response.text.encode('utf8'))

        # type 1
        if table_num == 11112 :
            # 날짜
            date = res['images'][0]['fields'][0]['inferText'].split('\n')
            # 시간
            dtime = res['images'][0]['fields'][1]['inferText'].split('\n')
            # 수집동의
            checkbox = res['images'][0]['fields'][2]['inferText'].split('\n')
            # 시군구
            sigungu = res['images'][0]['fields'][3]['inferText'].split('\n')
            # 전화번호 + 비고
            tel = res['images'][0]['fields'][4]['inferText'].split('\n')

            li = [date, dtime, checkbox, sigungu, tel]

            df_temp = making_df(li, col_names, 'tel')


        # type 2
        elif table_num == 11119 :
            # 날짜
            date = res['images'][0]['fields'][0]['inferText'].split('\n')
            # 시간
            dtime = res['images'][0]['fields'][1]['inferText'].split('\n')
            # 연락처
            tel = res['images'][0]['fields'][2]['inferText'].split('\n')
            # 시군구
            sigungu = res['images'][0]['fields'][3]['inferText'].split('\n')
            # 비고
            extra = res['images'][0]['fields'][4]['inferText'].split('\n')

            li = [date, dtime, tel, sigungu, extra]

            df_temp = making_df(li, col_names)


        # type3
        elif table_num == 11126:
            # 날짜
            date = res['images'][0]['fields'][0]['inferText'].split('\n')
            # 시간
            dtime = res['images'][0]['fields'][1]['inferText'].split('\n')
            # 수집동의
            checkbox = res['images'][0]['fields'][2]['inferText'].split('\n')
            # 전화번호
            tel = res['images'][0]['fields'][3]['inferText'].split('\n')
            # 시군구
            sigungu = res['images'][0]['fields'][4]['inferText'].split('\n')
            # 비고
            extra = res['images'][0]['fields'][5]['inferText'].split('\n')


            li = [date, dtime, checkbox, tel, sigungu, extra]

            df_temp = making_df(li, col_names)



        # type 4
        elif table_num == 11127:
            # 날짜
            date = res['images'][0]['fields'][0]['inferText'].split('\n')
            # 시간
            dtime = res['images'][0]['fields'][1]['inferText'].split('\n')
            # 수집동의
            checkbox = res['images'][0]['fields'][2]['inferText'].split('\n')
            # 전화번호
            tel = res['images'][0]['fields'][3]['inferText'].split('\n')
            # 시군구 + 비고
            sigungu = res['images'][0]['fields'][4]['inferText'].split('\n')

            li = [date, dtime, checkbox, tel, sigungu]
            col_names = ['date', 'dtime', 'checkbox', 'tel', 'sigungu']

            df_temp = making_df(li, col_names, 'sigungu')

        df = pd.concat([df, df_temp]) # 생성된 애들 계속 합치기
    df.to_excel('./output/covid19.xlsx', index= False)


    # file 보내주기
    file_path = './output/covid19.xlsx'
    return FileResponse(path= file_path, filename='covid19.xlsx')






uvicorn.run(app, port=8000)
