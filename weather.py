import math
import httpx
import os

from mcp.server.fastmcp import FastMCP
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

# Initialize FastMCP server
mcp = FastMCP("weather")

# 초단기예보
API_URL = 'http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst'

# 단기예보
# API_URL = 'http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst'

API_SECRET = os.environ.get('PUBLIC_DATA_API_SECRET')
if not API_SECRET:
    raise ValueError("PUBLIC_DATA_API_SECRET environment variable is required")


def mapToGrid(lat, lon) -> tuple[int, int]:
    RE = 6371.00877     # 지도반경
    grid = 5.0          # 격자간격 (km)
    slat1 = 30.0        # 표준위도 1
    slat2 = 60.0        # 표준위도 2
    olon = 126.0        # 기준점 경도
    olat = 38.0         # 기준점 위도
    xo = 43             # 기준점 X좌표
    yo = 136            # 기준점 Y좌표
    PI = math.pi        # PI

    DEGRAD = PI / 180.0

    re = RE / grid
    slat1 = slat1 * DEGRAD
    slat2 = slat2 * DEGRAD
    olon = olon * DEGRAD
    olat = olat * DEGRAD

    sn = math.tan(PI * 0.25 + slat2 * 0.5) / math.tan(PI * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(PI * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(PI * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)    
    ra = math.tan(PI * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / pow(ra, sn)

    theta = lon * DEGRAD - olon

    if theta > PI:
        theta -= 2.0 * PI
    if theta < -PI:
        theta += 2.0 * PI

    theta *= sn

    nx = math.floor(ra * math.sin(theta) + xo + 0.5)
    ny = math.floor(ro - ra * math.cos(theta) + yo + 0.5)

    return (nx, ny)


async def get_weather(lat: float, lon: float):
    """초단기예보
매시간 30분에 생성되고 10분마다 최신 정보로 업데이트(기온, 습도, 바람)

T1H 기온
RN1 1시간 강수량 
SKY 하늘상태
UUU 동서바람성분
VVV 남북바람성분
REH 습도
PTY 강수형태
LGT 낙뢰
VEC 풍향
WSD 풍속

- 하늘상태(SKY) 코드 : 맑음(1), 구름많음(3), 흐림(4)
- 강수형태(PTY) 코드 : (초단기) 없음(0), 비(1), 비/눈(2), 눈(3), 빗방울(5), 빗방울눈날림(6), 눈날림(7)
(단기) 없음(0), 비(1), 비/눈(2), 눈(3), 소나기(4)
    """
    SEOUL = ZoneInfo("Asia/Seoul")
    current_time = datetime.now(SEOUL)

    # API 제공 시간은 매 시 45분 이후이다. 
    # 45분 전후로 체크해서 base time 을 정하지 말고 그냥 무조건 한 시간 이전 데이터를 가져오게 한다.
    fcst_time = f"{current_time.hour:02d}00"
    current_time = current_time - timedelta(hours=1)

    base_time = f"{current_time.hour:02d}30"
    base_date = current_time.strftime('%Y%m%d')

    # print(base_date, base_time)

    nx, ny = mapToGrid(lat, lon)

    params ={
        'serviceKey' : API_SECRET, 
        'pageNo' : 1, 
        'numOfRows' : '60', 
        'dataType' : 'JSON', 
        'base_date' : base_date, # 발표일자
        'base_time' : base_time, # 발표시각
        'nx' : nx, 
        'ny' : ny
    }

    # response = requests.get(API_URL, params=params)
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, params=params)
    
    if response.status_code != 200:
        return None

    result = response.json()
    # print('numOfRows:', result['response']['body']['numOfRows'])
    # print('totalCount:', result['response']['body']['totalCount'])

    items = result['response']['body']['items']['item']
    
    # print(fcst_time)

    data = {}
    for item in items:
        if item['fcstTime'] == fcst_time:
            data[item['category']] = item['fcstValue']

    return data


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        lat: Latitude of the location
        lon: Longitude of the location
    """
    data = await get_weather(latitude, longitude)

    if data['SKY'] == '1':
        sky = '맑음'
    elif data['SKY'] == '3':
        sky = '구름많음'
    elif data['SKY'] == '4':
        sky = '흐림'

    if data['PTY'] == '0':
        pty = '없음'
    elif data['PTY'] == '1':
        pty = '비'
    elif data['PTY'] == '2':
        pty = '비나 눈'
    elif data['PTY'] == '3':
        pty = '눈'
    elif data['PTY'] == '5':
        pty = '빗방울'
    elif data['PTY'] == '6':
        pty = '빗방울눈날림'
    elif data['PTY'] == '7':
        pty = '눈날림'

    rn1 = '강수없음' if data['RN1'] == '강수없음' else f"{data['RN1']}mm"

    forecast = f"""
기온: {data['T1H']}°C
하늘상태: {sky}
강수형태: {pty}
습도: {data['REH']}%
1시간 강수량: {rn1}
풍속: {data['WSD']}m/s
"""

    return forecast


def main():
    """Main entry point for the weather MCP server."""
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
