import requests
from urllib.parse import unquote

BASE_URL = "https://apis.data.go.kr/1741000/household_waste_info/info"

# 공공데이터포털에서 복사한 일반 인증키
ENCODED_SERVICE_KEY = "mS1zLq%2Fmt9tvlCLbqIZBxiPyC5pZxde%2FGmTkdsHZ3PkNxMEEkQqtxL6QrFHp%2BWVfzuY2vIMS2yXau3LF80VFmw%3D%3D"

# 이미 URL Encoding 되어 있다면 한 번 decode
SERVICE_KEY = unquote(ENCODED_SERVICE_KEY)

params = {
    "serviceKey": SERVICE_KEY,
    "pageNo": 1,
    "numOfRows": 10,
    "returnType": "json",
    "cond[SGG_NM::LIKE]": "강남구",
}

response = requests.get(
    BASE_URL,
    params=params,
    timeout=30,
)

print("요청 URL:")
print(response.url)

print("\nHTTP STATUS:")
print(response.status_code)

print("\n응답:")
print(response.text)