"""
Azure AD Authentication Module
Handles user authentication using Microsoft Authentication Library (MSAL)
"""
import os
import json
import requests
from flask import session, redirect, url_for, request
from msal import ConfidentialClientApplication
from functools import wraps
from typing import Optional, Dict


class AzureADAuth:
    """Azure AD Authentication handler"""
    
    def __init__(self, app=None):
        self.app = app
        self.msal_app = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the authentication module with Flask app"""
        self.app = app
        
        # Get Azure AD configuration from environment
        self.tenant_id = os.getenv('AZURE_AD_TENANT_ID')
        self.client_id = os.getenv('AZURE_AD_CLIENT_ID')
        self.client_secret = os.getenv('AZURE_AD_CLIENT_SECRET')
        
        # Get redirect URI - use environment variable or construct from request
        redirect_uri_env = os.getenv('AZURE_AD_REDIRECT_URI')
        if redirect_uri_env:
            self.redirect_uri = redirect_uri_env
        else:
            # Fallback: construct from app config or use default
            self.redirect_uri = os.getenv('AZURE_AD_REDIRECT_URI_PROD', 
                                         'http://localhost:8080/login/authorized')
        
        # Authority URL
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        
        # Scopes for authentication
        self.scopes = ["User.Read"]
        
        # Initialize MSAL app if credentials are available
        if self.tenant_id and self.client_id and self.client_secret:
            self.msal_app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.authority
            )
        else:
            print("Warning: Azure AD credentials not configured. Authentication will be disabled.")
    
    def get_login_url(self) -> Optional[str]:
        """Get the Azure AD login URL"""
        if not self.msal_app:
            return None
        
        # Generate authorization URL
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        return auth_url
    
    def get_token_from_code(self, code: str) -> Optional[Dict]:
        """Exchange authorization code for token"""
        if not self.msal_app:
            return None
        
        try:
            result = self.msal_app.acquire_token_by_authorization_code(
                code=code,
                scopes=self.scopes,
                redirect_uri=self.redirect_uri
            )
            
            if "access_token" in result:
                return result
            else:
                print(f"Token acquisition failed: {result.get('error_description', 'Unknown error')}")
                return None
        except Exception as e:
            print(f"Error acquiring token: {e}")
            return None
    
    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get user information from Microsoft Graph API"""
        try:
            graph_endpoint = 'https://graph.microsoft.com/v1.0/me'
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(graph_endpoint, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get user info: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return 'user' in session and 'access_token' in session
    
    def get_user(self) -> Optional[Dict]:
        """Get current user from session"""
        return session.get('user')
    
    def login(self, user_info: Dict, access_token: str):
        """Store user information in session"""
        session['user'] = user_info
        session['access_token'] = access_token
        session['authenticated'] = True
    
    def logout(self):
        """Clear session and logout user"""
        session.clear()
    
    def require_auth(self, f):
        """Decorator to require authentication for a route"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                # Store the original URL to redirect after login
                session['next_url'] = request.url
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function


# Global instance (will be initialized in app.py)
auth = AzureADAuth()

