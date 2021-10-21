
'''모듈 불러오기'''
from fastapi import FastAPI, File, UploadFile, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn




'''서비스 구현'''
app = FastAPI()


# 처음 서비스 화면
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory = "templates")
@app.get('/', response_class=HTMLResponse)
async def home(request : Request) :
    return templates.TemplateResponse("input2.html", context={"request": request})


# 파일 업로드, API 요청, csv 파일 다운
@app.post("/uploadfiles/")
async def image(files: UploadFile = File(...), table_num : int = Form(...)):
    import requests
    import uuid
    import time
    import json

    file_location = f"./input/{files.filename}"
    file_format = files.filename[-3:]
    with open(file_location, "wb+") as file_object:
        file_object.write(files.file.read())


    with open('./data/api_url.txt', 'r') as api_url:
        api_url = api_url.readline()

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
    files = [
        ('file', open(file_location, 'rb'))
    ]
    headers = {
        'X-OCR-SECRET': secret_key
    }

    response = requests.request("POST", api_url, headers=headers, data=payload, files=files)

    res = json.loads(response.text.encode('utf8'))


    if table_num == 11112 :
        # 날짜
        date = res['images'][0]['fields'][0]['inferText'].split('\n')
        # 시간
        time = res['images'][0]['fields'][1]['inferText'].split('\n')
        # 수집동의
        checkbox = res['images'][0]['fields'][2]['inferText'].split('\n')
        # 시군구
        sigungu = res['images'][0]['fields'][3]['inferText'].split('\n')
        # 전화번호 + 비고
        tel = res['images'][0]['fields'][4]['inferText'].split('\n')

        # max length
        length = 0
        li = [date, time, checkbox, sigungu, tel]
        for i in li:
            length = max(len(i), length)

        # 패딩 맞춰주기
        import numpy as np
        df_li = []
        for i in li:
            df_li.append(np.pad(i, (0, length - len(i)), 'constant', constant_values=0))

        import pandas as pd
        df = pd.DataFrame(df_li).transpose()
        df.columns = ['date', 'time', 'checkbox', 'sigungu', 'tel']

        df['extra'] = '-'

        for i in df[df.tel.str.contains('외')].index:
            # '외'이후를 extra에 저장
            df.extra[i] = '외' + df[df.tel.str.contains('외')].tel[i].split('외')[1]

            # tel에서 '외'이후 버림
            df.tel[i] = df[df.tel.str.contains('외')].tel[i].split('외')[0]

        # 공백 및 특수문자 제거
        for col in ['date', 'time', 'checkbox', 'sigungu', 'tel']:
            df[col] = df[col].str.replace(' ', '')
            df[col] = df[col].str.replace('.', '')


        # 전화번호 형식 통일
        for col in ['tel']:
            df[col] = df[col].str.replace('-', '')
            df[col] = df[col].str.replace(',', '')
            df[col] = df[col].str.replace('~', '')
            df[col] = df[col].str.replace('.', '')


        # 010 미표기 처리
        for i in range(len(df)):
            if df['tel'][i].startswith('010'):
                df['tel'][i] = df['tel'][i][3:]
            df['tel'][i] = '010' + '-' + df['tel'][i][0:4] + '-' + df['tel'][i][4:]

        # 체크박스 형식 통일
        for i in ['v', 'r', 'o', 'O', '0', 'ㅇ','○','b','6','9']:
            df.loc[(df['checkbox'] == i), 'checkbox'] = 'V'


        # ' " ' 처리
        df.replace({'11':'"', '1/':'"', '//':'"', '/1':'"'}, inplace = True)

        for i in range(len(df)):
            for col in df.columns:
                if df[col][i] == '"':
                    df[col][i] = df[col][i - 1]

        # 시간 형식 통일
        for i in range(len(df)):
            if df['time'][i].find(':') < 0:
                if len(df['time'][i]) == 2:
                    df['time'][i] = df['time'][i][0] + ':' + df['time'][i][1]
                elif len(df['time'][i]) == 3:
                    df['time'][i] = df['time'][i][0] + ':' + df['time'][i][1:]
                else:
                    df['time'][i] = df['time'][i][0:2] + ':' + df['time'][i][2:]

        # 날짜 형식 통일
        df['date'] = df['date'].str.replace(',', '')

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
            for i in range(df.shape[0]):
                slash_idx_i = df['date'][i].find('/')  # i번째 날짜의 '/' 위치
                slash_idx_i_1 = df['date'][i - 1].find('/')  # i-1번째 날짜의 '/' 위치
                i_month = int(df['date'][i][:slash_idx_i])
                i_1_month = int(df['date'][i - 1][:slash_idx_i_1])
                if (i_month < i_1_month) or (i_1_month - i_month > 1):  # 위의 날짜의 달보다 아래 날짜의 달이 작거나 차이가 두 달 이상인 경우
                    if df['date'][i][-1] == df['date'][i - 1][-1]:  # 만약에 위의 날짜의 일자의 마지막 글자와 아래 날짜의 마지막 글자가 같으면
                        df['date'][i] = df['date'][i - 1]  # 날짜가 같다는 거니깐 그대로 넣어줌
                    else:
                        df['date'][i] = df['date'][i - 1][:slash_idx_i_1] + '/' + str(
                            int(df['date'][i - 1][slash_idx_i_1 + 1:]) + 1)  # 다르면 하루 증가한 값 넣어줌
        except:
            pass


    elif table_num == 11126:
        # 날짜
        date = res['images'][0]['fields'][0]['inferText'].split('\n')
        # 시간
        time = res['images'][0]['fields'][1]['inferText'].split('\n')
        # 수집동의
        checkbox = res['images'][0]['fields'][2]['inferText'].split('\n')
        # 전화번호
        tel = res['images'][0]['fields'][3]['inferText'].split('\n')
        # 시군구
        sigungu = res['images'][0]['fields'][4]['inferText'].split('\n')
        # 비고
        extra = res['images'][0]['fields'][5]['inferText'].split('\n')

        # max length
        length = 0
        li = [date, time, checkbox, tel, sigungu, extra]
        for i in li:
            length = max(len(i), length)

        # 패딩 맞춰주기
        import numpy as np
        df_li = []
        for i in li:
            df_li.append(np.pad(i, (0, length - len(i)), 'constant', constant_values=0))

        import pandas as pd
        df = pd.DataFrame(df_li).transpose()
        df.columns = ['date', 'time', 'checkbox', 'tel', 'sigungu', 'extra']

        df['extra'] = '-'

        # 공백제거
        for col in ['date', 'time', 'sigungu', 'tel']:
            df[col] = df[col].str.replace(' ', '')

        # 전화번호 형식 통일
        for col in ['tel']:
            df[col] = df[col].str.replace('-', '')
            df[col] = df[col].str.replace(',', '')
            df[col] = df[col].str.replace('~', '')
            df[col] = df[col].str.replace('.', '')

        # 010 미표기 처리
        for i in range(len(df)):
            if df['tel'][i].startswith('010'):
                df['tel'][i] = df['tel'][i][3:]
            df['tel'][i] = '010' + '-' + df['tel'][i][0:4] + '-' + df['tel'][i][4:]

        # 체크박스 형식 통일
        for i in ['v', 'r', 'o', 'O', '0', 'ㅇ','○','b','6','9']:
            df.loc[(df['checkbox'] == i), 'checkbox'] = 'V'

        # ' " ' 처리
        df.replace({'11':'"', '1/':'"', '//':'"', '/1':'"'}, inplace = True)

        for i in range(len(df)):
            for col in df.columns:
                if df[col][i] == '"':
                    df[col][i] = df[col][i - 1]
        

        # 시간 형식 통일
        for i in range(len(df)):
            if df['time'][i].find(':') < 0:
                if len(df['time'][i]) == 2:
                    df['time'][i] = df['time'][i][0] + ':' + df['time'][i][1]
                elif len(df['time'][i]) == 3:
                    df['time'][i] = df['time'][i][0] + ':' + df['time'][i][1:]
                else:
                    df['time'][i] = df['time'][i][0:2] + ':' + df['time'][i][2:]
        
        df['time'] = df['time'].str.replace('.', '')

        # 날짜 형식 통일
        df['date'] = df['date'].str.replace(',', '')

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
            for i in range(df.shape[0]):
                slash_idx_i = df['date'][i].find('/')  # i번째 날짜의 '/' 위치
                slash_idx_i_1 = df['date'][i - 1].find('/')  # i-1번째 날짜의 '/' 위치
                i_month = int(df['date'][i][:slash_idx_i])
                i_1_month = int(df['date'][i - 1][:slash_idx_i_1])
                if (i_month < i_1_month) or (i_1_month - i_month > 1):  # 위의 날짜의 달보다 아래 날짜의 달이 작거나 차이가 두 달 이상인 경우
                    if df['date'][i][-1] == df['date'][i - 1][-1]:  # 만약에 위의 날짜의 일자의 마지막 글자와 아래 날짜의 마지막 글자가 같으면
                        df['date'][i] = df['date'][i - 1]  # 날짜가 같다는 거니깐 그대로 넣어줌
                    else:
                        df['date'][i] = df['date'][i - 1][:slash_idx_i_1] + '/' + str(
                            int(df['date'][i - 1][slash_idx_i_1 + 1:]) + 1)  # 다르면 하루 증가한 값 넣어줌
        except:
            pass


    elif table_num == 11119 :
        # 날짜
        date = res['images'][0]['fields'][0]['inferText'].split('\n')
        # 시간
        time = res['images'][0]['fields'][1]['inferText'].split('\n')
        # 연락처
        tel = res['images'][0]['fields'][2]['inferText'].split('\n')
        # 시군구
        sigungu = res['images'][0]['fields'][3]['inferText'].split('\n')
        # 비고
        extra = res['images'][0]['fields'][4]['inferText'].split('\n')

        # max length
        length = 0
        li = [date, time, tel, sigungu, extra]
        for i in li:
            length = max(len(i), length)

        # 패딩 맞춰주기
        import numpy as np
        df_li = []
        for i in li:
            df_li.append(np.pad(i, (0, length - len(i)), 'constant', constant_values=0))

        import pandas as pd
        df = pd.DataFrame(df_li).transpose()
        df.columns = ['date', 'time', 'tel', 'sigungu', 'extra']

        # 공백 제거
        for col in ['date', 'time', 'sigungu', 'tel']:
            df[col] = df[col].str.replace(' ', '')


        # 비고(체온) 형식 통일
        for col in ['extra']:
            df[col] = df[col].str.replace(' ', '')
            df[col] = df[col].str.replace(',', '.')

        # 전화번호 형식 통일
        for col in ['tel']:
            df[col] = df[col].str.replace('-', '')
            df[col] = df[col].str.replace(',', '')
            df[col] = df[col].str.replace('~', '')
            df[col] = df[col].str.replace('.', '')

        # 010 미표기 처리
        for i in range(len(df)):
            if df['tel'][i].startswith('010'):
                df['tel'][i] = df['tel'][i][3:]
            df['tel'][i] = '010' + '-' + df['tel'][i][0:4] + '-' + df['tel'][i][4:]

        # ' " ' 처리
        df.replace({'11':'"', '1/':'"', '//':'"', '/1':'"'}, inplace = True)

        for i in range(len(df)):
            for col in df.columns:
                if df[col][i] == '"':
                    df[col][i] = df[col][i - 1]

        # 시간 형식 통일
        for i in range(len(df)):
            if df['time'][i].find(':') < 0:
                if len(df['time'][i]) == 2:
                    df['time'][i] = df['time'][i][0] + ':' + df['time'][i][1]
                elif len(df['time'][i]) == 3:
                    df['time'][i] = df['time'][i][0] + ':' + df['time'][i][1:]
                else:
                    df['time'][i] = df['time'][i][0:2] + ':' + df['time'][i][2:]

        # 날짜 형식 통일
        df['date'] = df['date'].str.replace(',', '')

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
            for i in range(df.shape[0]):
                slash_idx_i = df['date'][i].find('/')  # i번째 날짜의 '/' 위치
                slash_idx_i_1 = df['date'][i - 1].find('/')  # i-1번째 날짜의 '/' 위치
                i_month = int(df['date'][i][:slash_idx_i])
                i_1_month = int(df['date'][i - 1][:slash_idx_i_1])
                if (i_month < i_1_month) or (i_1_month - i_month > 1):  # 위의 날짜의 달보다 아래 날짜의 달이 작거나 차이가 두 달 이상인 경우
                    if df['date'][i][-1] == df['date'][i - 1][-1]:  # 만약에 위의 날짜의 일자의 마지막 글자와 아래 날짜의 마지막 글자가 같으면
                        df['date'][i] = df['date'][i - 1]  # 날짜가 같다는 거니깐 그대로 넣어줌
                    else:
                        df['date'][i] = df['date'][i - 1][:slash_idx_i_1] + '/' + str(
                            int(df['date'][i - 1][slash_idx_i_1 + 1:]) + 1)  # 다르면 하루 증가한 값 넣어줌
        except:
            pass

    elif table_num == 11127:
        # 날짜
        date = res['images'][0]['fields'][0]['inferText'].split('\n')
        # 시간
        time = res['images'][0]['fields'][1]['inferText'].split('\n')
        # 수집동의
        checkbox = res['images'][0]['fields'][2]['inferText'].split('\n')
        # 전화번호
        tel = res['images'][0]['fields'][3]['inferText'].split('\n')
        # 시군구 + 비고
        sigungu = res['images'][0]['fields'][4]['inferText'].split('\n')

        # max length
        length = 0
        li = [date, time, checkbox, sigungu, tel]
        for i in li:
            length = max(len(i), length)

        # 패딩 맞춰주기
        import numpy as np
        df_li = []
        for i in li:
            df_li.append(np.pad(i, (0, length - len(i)), 'constant', constant_values=0))

        import pandas as pd
        df = pd.DataFrame(df_li).transpose()
        df.columns = ['date', 'time', 'checkbox', 'sigungu', 'tel']

        df['extra'] = '-'

        for i in df[df.sigungu.str.contains('외')].index:
            # '외'이후를 extra에 저장
            df.extra[i] = df[df.sigungu.str.contains('외')].sigungu[i].split(' ')[1] + ' ' + \
                          df[df.sigungu.str.contains('외')].sigungu[i].split(' ')[2]
            # sigungu에서 '외'이후 버림
            df.sigungu[i] = df[df.sigungu.str.contains('외')].sigungu[i].split(' ')[0]

        # 공백 및 특수문자 제거
        for col in ['date', 'time', 'checkbox', 'sigungu', 'tel']:
            df[col] = df[col].str.replace(' ', '')
            df[col] = df[col].str.replace('.', '')

        # 전화번호 형식 통일
        for col in ['tel']:
            df[col] = df[col].str.replace('-', '')
            df[col] = df[col].str.replace(',', '')
            df[col] = df[col].str.replace('~', '')
            df[col] = df[col].str.replace('.', '')

        # 010 미표기 처리
        for i in range(len(df)):
            if df['tel'][i].startswith('010'):
                df['tel'][i] = df['tel'][i][3:]
            df['tel'][i] = '010' + '-' + df['tel'][i][0:4] + '-' + df['tel'][i][4:]

        # 체크박스 형식 통일
        for i in ['v', 'r', 'o', 'O', '0', 'ㅇ','○','b','6','9']:
            df.loc[(df['checkbox'] == i), 'checkbox'] = 'V'

        # ' " ' 처리
        df.replace({'11':'"', '1/':'"', '//':'"', '/1':'"'}, inplace = True)

        for i in range(len(df)):
            for col in df.columns:
                if df[col][i] == '"':
                    df[col][i] = df[col][i - 1]

        
        for i in range(len(df)):
            if df['date'][i].find('/') < 0:
                if len(df['date'][i]) == 2:
                    df['date'][i] = df['date'][i][0] + '/' + df['date'][i][1]
                elif len(df['date'][i]) == 3 and df['date'][i][0:2] > 9 and df['date'][i][0:2] == df['date'][i-1][0:2]:
                    df['date'][i] = df['date'][i][0:2] + '/' + df['date'][i][2:]
                elif len(df['date'][i]) == 3 and df['date'][i][0:2] > 9 and df['date'][i][0:2] != df['date'][i-1][0:2]:
                    df['date'][i] = df['date'][i][0] + '/' + df['date'][i][1:]
                else:
                    df['date'][i] = df['date'][i][0:2] + '/' + df['date'][i][2:]

        # 날짜 형식 통일
        df['date'] = df['date'].str.replace(',', '')

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
            for i in range(df.shape[0]):
                slash_idx_i = df['date'][i].find('/')  # i번째 날짜의 '/' 위치
                slash_idx_i_1 = df['date'][i - 1].find('/')  # i-1번째 날짜의 '/' 위치
                i_month = int(df['date'][i][:slash_idx_i])
                i_1_month = int(df['date'][i - 1][:slash_idx_i_1])
                if (i_month < i_1_month) or (i_1_month - i_month > 1):  # 위의 날짜의 달보다 아래 날짜의 달이 작거나 차이가 두 달 이상인 경우
                    if df['date'][i][-1] == df['date'][i - 1][-1]:  # 만약에 위의 날짜의 일자의 마지막 글자와 아래 날짜의 마지막 글자가 같으면
                        df['date'][i] = df['date'][i - 1]  # 날짜가 같다는 거니깐 그대로 넣어줌
                    else:
                        df['date'][i] = df['date'][i - 1][:slash_idx_i_1] + '/' + str(
                            int(df['date'][i - 1][slash_idx_i_1 + 1:]) + 1)  # 다르면 하루 증가한 값 넣어줌
        except:
            pass




    df.to_csv('./output/covid19.csv', index= False)


    # file 보내주기
    file_path = './output/covid19.csv'
    return FileResponse(path= file_path, filename='covid19.csv')






uvicorn.run(app, port=8000)