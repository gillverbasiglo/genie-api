import json
import boto3
import tempfile
import os
from functools import lru_cache
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class SecretsManager:
    """
    Configuration manager for retrieving and caching credentials
    from AWS Secrets Manager with support for multiple secret types.
    """
    
    def __init__(self, region_name: str = None):
        """
        Initialize the secrets manager.
        
        Args:
            region_name: AWS region name, defaults to instance metadata or env variable
        """
        self.region_name = region_name or os.environ.get('AWS_REGION', 'us-east-1')
        self._client = None
        
    @property
    def client(self):
        """Lazy-loaded Secrets Manager client"""
        if self._client is None:
            session = boto3.session.Session()
            self._client = session.client(
                service_name='secretsmanager',
                region_name=self.region_name
            )
        return self._client
    
    @lru_cache(maxsize=32)
    def get_secret(self, secret_id: str) -> str:
        """
        Get a secret value from Secrets Manager with caching.
        
        Args:
            secret_id: The secret ID or ARN
            
        Returns:
            The secret value as a string
        """
        try:
            response = self.client.get_secret_value(SecretId=secret_id)
            
            # If the secret has binary data, convert it
            if 'SecretBinary' in response:
                return response['SecretBinary']
            else:
                return response['SecretString']
                
        except Exception as e:
            logger.error(f"Failed to get secret {secret_id}: {e}")
            raise
    
    def get_json_secret(self, secret_id: str) -> Dict[str, Any]:
        """
        Get a JSON secret and parse it.
        
        Args:
            secret_id: The secret ID or ARN
            
        Returns:
            Parsed JSON as dictionary
        """
        value = self.get_secret(secret_id)
        return json.loads(value)
    
    def get_db_credentials(self) -> Dict[str, str]:
        """
        Get PostgreSQL database credentials from Secrets Manager.
        For RDS instances, the secret is automatically formatted to include
        username, password, host, port, dbname, etc.
        """
        return self.get_json_secret(os.environ.get('DATABASE_SECRETS_NAME', 'rds!db-3805dfcb-d481-41ee-9f16-1b6fb710913e'))
    
    def get_api_key(self, service_name: str) -> str:
        """Get API key for a specific service"""
        secret_id = f'{service_name}-api-key'
        return self.get_secret(secret_id)
