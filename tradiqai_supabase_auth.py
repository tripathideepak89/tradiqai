"""
Supabase Authentication Integration for TradiqAI

This module provides authentication using Supabase Auth instead of custom JWT.
Supabase Auth handles:
- User registration and login
- JWT token generation and validation
- Password hashing and security
- Email verification (optional)
- Session management
"""
from typing import Optional, Dict, Any
from tradiqai_supabase_config import get_supabase_client, get_supabase_admin
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Pydantic models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    username: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    capital: float
    paper_trading: bool
    created_at: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[Dict[str, Any]] = None


class SupabaseAuth:
    """Supabase Authentication Manager"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.admin = get_supabase_admin()
    
    async def register_user(self, user_data: UserRegister) -> Dict[str, Any]:
        """
        Register a new user with Supabase Auth
        
        Returns:
            dict: User data and session info
        """
        try:
            # Sign up user with Supabase Auth
            auth_response = self.supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
            })
            
            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Registration failed"
                )
            
            user_id = auth_response.user.id
            
            # Create user profile in public.users table
            profile_data = {
                "id": user_id,
                "email": user_data.email,
                "username": user_data.username,
                "full_name": user_data.full_name,
                "capital": 50000.0,  # Default capital
                "paper_trading": True,  # Start in paper trading mode
                "max_daily_loss": 1500.0,
                "max_position_risk": 400.0,
                "max_open_positions": 2,
                "is_active": True,
                "is_admin": False
            }
            
            # Insert into users table using admin client (bypasses RLS)
            result = self.admin.table("users").insert(profile_data).execute()
            
            logger.info(f"User registered: {user_data.email} (ID: {user_id})")
            
            return {
                "user": auth_response.user,
                "session": auth_response.session,
                "message": "Registration successful"
            }
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}"
            )
    
    async def login_user(self, credentials: UserLogin) -> Dict[str, Any]:
        """
        Login user with Supabase Auth
        
        Returns:
            dict: Session tokens and user info
        """
        try:
            # Sign in with email and password
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": credentials.email,
                "password": credentials.password
            })
            
            if not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Get user profile
            user_id = auth_response.user.id
            profile = self.supabase.table("users").select("*").eq("id", user_id).execute()
            
            if not profile.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found"
                )
            
            user_profile = profile.data[0]
            
            # Update last login
            self.supabase.table("users").update({
                "last_login": "now()"
            }).eq("id", user_id).execute()
            
            logger.info(f"User logged in: {credentials.email}")
            
            return {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "token_type": "bearer",
                "user": user_profile
            }
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """
        Get current user from JWT token
        
        FastAPI dependency for protected routes
        """
        try:
            token = credentials.credentials
            
            # Verify token with Supabase
            user_response = self.supabase.auth.get_user(token)
            
            if not user_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            
            user_id = user_response.user.id
            
            # Get user profile from database
            profile = self.supabase.table("users").select("*").eq("id", user_id).execute()
            
            if not profile.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found"
                )
            
            user_data = profile.data[0]
            
            # Check if user is active
            if not user_data.get("is_active", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is deactivated"
                )
            
            return user_data
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            auth_response = self.supabase.auth.refresh_session(refresh_token)
            
            if not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            return {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "token_type": "bearer"
            }
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token refresh failed"
            )
    
    async def logout_user(self, token: str) -> Dict[str, str]:
        """Logout user and invalidate session"""
        try:
            # Sign out from Supabase
            self.supabase.auth.sign_out()
            return {"message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed"
            )
    
    async def update_user_settings(self, user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update user trading settings"""
        try:
            result = self.supabase.table("users").update(settings).eq("id", user_id).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return result.data[0]
        except Exception as e:
            logger.error(f"Update settings error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update settings: {str(e)}"
            )


# Global auth instance
auth_manager = SupabaseAuth()


# FastAPI dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """FastAPI dependency to get current authenticated user"""
    return await auth_manager.get_current_user(credentials)


async def get_current_active_user(current_user: Dict = Depends(get_current_user)) -> Dict[str, Any]:
    """FastAPI dependency to get current active user"""
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    return current_user
