from __future__ import print_function
import pickle
import os.path
from google.oauth2 import id_token
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.transport import requests
from google_auth_oauthlib.flow import Flow

class authorize:
    def get_url(self):
        self.flow = Flow.from_client_secrets_file('credentials.json', scopes=['https://www.googleapis.com/auth/drive'], redirect_uri='urn:ietf:wg:oauth:2.0:oob')
        self.auth_url, _ = self.flow.authorization_url(prompt='consent')
        return self.auth_url
    def verify_code(self, code):
        try:
            self.flow.fetch_token(code=code)
            creds = self.flow.credentials
            return creds
        except:
            return False
    def save_credentials(self, creds, file='credentials.pickle'):
        with open(file, 'wb') as token:
            pickle.dump(creds, token)
        return True
    def load_credentials(self, file='credentials.pickle'):
        try:
            with open(file, 'rb') as token:
                creds = pickle.load(token)
            return creds
        except FileNotFoundError:
            return None
    def verify_token(self, creds):
        try:
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()
            result = sheet.values().get(spreadsheetId='1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms', range='A1:C').execute()
            return True
        except:
            return False

def get_values(sheet_id, credentials, range='A1:Z'):
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id, range=range).execute()
    values = result.get('values', [])
    return values

def create_sheet(title, credentials):
    service = build('sheets', 'v4', credentials=credentials)
    spreadsheet = {'properties': {'title': title}}
    result = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
    tamper_with_format(result.get('spreadsheetId'), credentials)
    return result.get('spreadsheetId')

def tamper_with_format(sheet_id, credentials):
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()
    tamper_data = ['Name, Subject', 'Student Tags', 'Easy Questions', 'Options', 'Correct Option', 'Image', 'Medium Questions', 'Options', 'Correct Option', 'Image', 'Hard Questions', 'Options', 'Correct Option', 'Image']
    req = sheet.values().update(spreadsheetId=sheet_id, range="A1:Z", valueInputOption="USER_ENTERED", body={"range": "A1:Z", "majorDimension": "ROWS", "values": [tamper_data]})
    req.execute()

if __name__=='__main__':
    gauth = authorize()
    tamper_with_format('1FqZwkcNI325Tk4nwcbE2wEylHBX8vP9sFb8_F37Uxh4', gauth.load_credentials())
