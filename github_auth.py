import requests
import json

def parse_access_token_str(token_str):
    vars = str(token_str).split('&')
    access_token = vars[0].spli('=')[1]
    return access_token


with open('../data/github_credentials.json') as f:
    data = json.loads(f.read())

client_id = data['client_id']
client_secret = data['client_secret']

url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={'http://chaitanyapy.ml/github_sign_in/'}"
print(url)

code =  'fdd0eda8e013981d17d3'
req = requests.post(f"https://github.com/login/oauth/access_token?client_id={client_id}&redirect_uri={'http://chaitanyapy.ml/github_sign_in/'}&client_secret={client_secret}&code={code}")
print(req.text)

access_token = "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"
print(requests.get('https://api.github.com/user', headers={'Authorization': f'token {access_token}'}).json())

# https://github.com/login/oauth/authorize?client_id=06e4f3b0a5a33a2b9c46&redirect_uri=http://chaitanyapy.ml/github_sign_in/signin/
