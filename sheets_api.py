import pickle
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import Flow

class authorize:
    def get_url(self):
        self.flow = Flow.from_client_secrets_file('../data/credentials.json', scopes=['https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/drive.file', 'openid'], redirect_uri='urn:ietf:wg:oauth:2.0:oob')
        self.auth_url, _ = self.flow.authorization_url(prompt='consent')
        return self.auth_url
    def verify_code(self, code):
        try:
            self.flow.fetch_token(code=code)
            creds = self.flow.credentials
            self.verify_token(creds)
            return creds
        except Exception as e:
            return False
    def save_credentials(self, creds, file='credentials'):
        file = '../data/credentials/'+file+'.pickle'
        with open(file, 'wb') as token:
            pickle.dump(creds, token)
        return True
    def load_credentials(self, file='credentials.pickle'):
        file = '../data/credentials/'+file+'.pickle'
        try:
            with open(file, 'rb') as token:
                creds = pickle.load(token)
            return creds
        except FileNotFoundError:
            return None
    def verify_token(self, creds):
        try:
            # sheet_id = create_sheet("DAL Assessments Temporary Verification Sheet", creds)
            return True
        except Exception as e:
            return False

def get_values(sheet_id, credentials, sheet_range='A1:Z'):
    service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_range).execute()
    values = result.get('values', [])
    return values

def create_sheet(title, credentials):
    service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    spreadsheet = {'properties': {'title': title}}
    result = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
    tamper_with_format(result.get('spreadsheetId'), credentials)
    return result.get('spreadsheetId')

def create_data_sheet(title, credentials, data):
    service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    spreadsheet = {'properties': {'title': title}}
    result = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
    sheet_id = result.get('spreadsheetId')
    req = service.spreadsheets().values().update(spreadsheetId=sheet_id, range="A1:Z", valueInputOption="USER_ENTERED", body={"range": "A1:Z", "majorDimension": "ROWS", "values": data})
    req.execute()
    return sheet_id

def update_sheet(sheet_id, credentials, data):
    service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    req = service.spreadsheets().values().update(spreadsheetId=sheet_id, range="A1:Z", valueInputOption="USER_ENTERED", body={"range": "A1:Z", "majorDimension": "ROWS", "values": data})
    try:
        req.execute()
    except HttpError as err:
        if err.resp.status == 404:
            return False
        else:
            print(err)
            print(err.resp)
            print(err.resp.status)
    return sheet_id

def tamper_with_format(sheet_id, credentials):
    service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    sheet = service.spreadsheets()
    tamper_data = ['Name, Subject, Total questions', 'Student Tags', 'Easy Questions', 'Options', 'Correct Option', 'Image', 'Medium Questions', 'Options', 'Correct Option', 'Image', 'Hard Questions', 'Options', 'Correct Option', 'Image']
    req = sheet.values().update(spreadsheetId=sheet_id, range="A1:Z", valueInputOption="USER_ENTERED", body={"range": "A1:Z", "majorDimension": "ROWS", "values": [tamper_data]})
    req.execute()
