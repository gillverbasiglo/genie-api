from firebase_admin import initialize_app, auth, credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import google.auth
import google.auth.transport.requests
import json
import os

# Create a custom credential provider using Workload Identity Federation
class WorkloadIdentityCredentials(credentials.Base):
    def __init__(self):
        # Initialize the Google Auth client
        self._request = google.auth.transport.requests.Request()
        
    def get_access_token(self):
        # This will use the EC2 instance's IAM role to get Google credentials
        creds, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Refresh the credentials if needed
        if not creds.valid:
            creds.refresh(self._request)
            
        return {
            'access_token': creds.token,
            'expires_in': creds.expiry
        }