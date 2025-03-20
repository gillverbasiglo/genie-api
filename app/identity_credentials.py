from firebase_admin import credentials
import boto3
import requests
import json
import logging
import os

logger = logging.getLogger(__name__)

class WorkloadIdentityCredentials(credentials.Base):
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
    
    def get_access_token(self):
        try:
            # Get AWS credentials from boto3
            session = boto3.Session()
            aws_creds = session.get_credentials()
            frozen_creds = aws_creds.get_frozen_credentials()
            region = session.region_name or 'us-east-1'
            
            # Get AWS identity information
            sts_client = boto3.client('sts')
            identity = sts_client.get_caller_identity()
            logger.debug(f"AWS Identity: {identity}")
            
            # Prepare the AWS request to sign
            aws_request = {
                "access_key_id": frozen_creds.access_key,
                "secret_access_key": frozen_creds.secret_key,
                "security_token": frozen_creds.token,
                "region": region,
                "url": "https://sts.amazonaws.com",
                "method": "GET",
                "headers": {"x-amz-date": "20240317T000000Z"},
                "body": "",
                "params": {"Action": "GetCallerIdentity", "Version": "2011-06-15"}
            }
            
            # Request a Google token
            headers = {"Content-Type": "application/json"}
            data = {
                "audience": self.config["audience"],
                "grantType": "urn:ietf:params:oauth:grant-type:token-exchange",
                "requestedTokenType": "urn:ietf:params:oauth:token-type:access_token",
                "scope": "https://www.googleapis.com/auth/cloud-platform",
                "subjectTokenType": self.config["subject_token_type"],
                "subjectToken": json.dumps(aws_request)
            }
            
            # Exchange for Google token
            response = requests.post(
                self.config["token_url"],
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                raise Exception(f"Token exchange failed: {response.text}")
            
            token_data = response.json()
            
            # If service account impersonation is configured, use it
            if "service_account_impersonation_url" in self.config:
                impersonation_url = self.config["service_account_impersonation_url"]
                impersonation_headers = {
                    "Authorization": f"Bearer {token_data['access_token']}",
                    "Content-Type": "application/json"
                }
                impersonation_data = {
                    "scope": ["https://www.googleapis.com/auth/cloud-platform"]
                }
                
                response = requests.post(
                    impersonation_url,
                    headers=impersonation_headers,
                    json=impersonation_data
                )
                
                if response.status_code != 200:
                    logger.error(f"Service account impersonation failed: {response.status_code} - {response.text}")
                    raise Exception(f"Service account impersonation failed: {response.text}")
                
                token_data = response.json()
            
            return {
                "access_token": token_data["access_token"],
                "expires_in": token_data.get("expires_in", 3600)
            }
        except Exception as e:
            logger.exception("Error in get_access_token")
            raise e
