from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path

def authenticate():
    # Get absolute path to the directory containing this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(current_dir, 'token.json')
    credentials_path = os.path.join(current_dir, 'credentials.json')
    
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(
            token_path, 
            [
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/gmail.send'
            ]
        )
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, 
                [
                    'https://www.googleapis.com/auth/calendar',
                    'https://www.googleapis.com/auth/gmail.send'
                ]
            )
            creds = flow.run_local_server(port=0)
        
        # Save the credentials with absolute path
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

if __name__ == '__main__':
    authenticate()
