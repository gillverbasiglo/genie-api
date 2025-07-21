import json
import boto3
import os
import time
from functools import wraps
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class SecretsManager:
    """
    Configuration manager for retrieving and caching credentials
    from AWS Secrets Manager with TTL-based caching to handle rotation.
    """
    
    def __init__(self, region_name: str = None):
        """
        Initialize the secrets manager.
        
        Args:
            region_name: AWS region name, defaults to instance metadata or env variable
        """
        self.region_name = region_name or os.environ.get('AWS_REGION', 'us-east-1')
        self._client = None
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = 300  # 5 minutes TTL for secrets cache
        
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
    
    def _time_based_cache(self, func):
        """Decorator for time-based caching with TTL."""
        @wraps(func)
        def wrapper(secret_id: str) -> str:
            current_time = time.time()
            cache_key = f"{func.__name__}:{secret_id}"
            
            # Check if we have a cached value that's still valid
            if (cache_key in self._cache and 
                cache_key in self._cache_timestamps and 
                current_time - self._cache_timestamps[cache_key] < self._cache_ttl):
                logger.debug(f"Returning cached secret for {secret_id}")
                return self._cache[cache_key]
            
            # Cache miss or expired - fetch fresh value
            logger.info(f"Fetching fresh secret for {secret_id}")
            try:
                result = func(secret_id)
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = current_time
                return result
            except Exception as e:
                # If fresh fetch fails and we have stale cache, log warning but use stale data
                if cache_key in self._cache:
                    logger.warning(f"Fresh secret fetch failed for {secret_id}, using stale cache: {e}")
                    return self._cache[cache_key]
                raise
        return wrapper
    
    def clear_cache(self):
        """Clear the secrets cache to force fresh retrieval."""
        logger.info("Clearing secrets cache")
        self._cache.clear()
        self._cache_timestamps.clear()
    
    def get_secret(self, secret_id: str) -> str:
        """
        Get a secret value from Secrets Manager with TTL-based caching.
        
        Args:
            secret_id: The secret ID or ARN
            
        Returns:
            The secret value as a string
        """
        @self._time_based_cache
        def _fetch_secret(secret_id: str) -> str:
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
        
        return _fetch_secret(secret_id)
    
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
    
    def get_genie_ai_url(self) -> str:
        """
        Get the GENIE_AI_URL from either a dedicated secret or included in db credentials secret.
        
        Returns:
            Genie AI URL as string
        """
        try:
            # Option 1: separate secret
            secret_id = os.environ.get("GENIE_AI_URL_SECRET_NAME")
            if secret_id:
                return self.get_secret(secret_id)
        except Exception as e:
            logger.error("Failed to retrieve GENIE_AI_URL from Secrets Manager: %s", e)
            raise