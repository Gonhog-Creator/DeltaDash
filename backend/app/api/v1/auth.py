from datetime import timedelta
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.db.session import get_db
from app.db.models.user import User as UserModel
from app.schemas.user import UserCreate, User as UserSchema, Token, TokenData

router = APIRouter(redirect_slashes=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    access_token: Annotated[Optional[str], Cookie()] = None,
    authorization: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserModel:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try to get token from Authorization header first (immediate, no timing issues)
    # then fall back to cookie (for session persistence)
    token = None
    if authorization:
        token = authorization
    elif access_token:
        # Remove "Bearer " prefix if present
        if access_token.startswith("Bearer "):
            token = access_token[7:]
        else:
            token = access_token

    if token is None:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def get_current_active_user(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_admin(current_user: UserModel = Depends(get_current_active_user)) -> UserModel:
    # Dev mode bypass: treat admin user as admin in development
    if settings.APP_ENV == "development" and current_user.username == "admin":
        return current_user
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_editor_or_admin(current_user: UserModel = Depends(get_current_active_user)) -> UserModel:
    """Require user to be editor or admin (can edit/create but not delete)"""
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor or admin access required"
        )
    return current_user


def require_write_access(current_user: UserModel = Depends(get_current_active_user)) -> UserModel:
    """Require user to have write access (editor or admin)"""
    if current_user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required. Viewers have read-only access."
        )
    return current_user


@router.post("/login", response_model=Token)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Dev mode bypass: accept any password for admin and viewer users in development
    if settings.APP_ENV == "development" and form_data.username in ["admin", "viewer"]:
        user = db.query(UserModel).filter(UserModel.username == form_data.username).first()
        if user:
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.username}, expires_delta=access_token_expires
            )
            # Use same cookie settings as normal login
            response.set_cookie(
                key="access_token",
                value=f"Bearer {access_token}",
                httponly=True,  # True for security (JS can use localStorage)
                secure=False,  # False for HTTP in development
                samesite="lax",  # Lax for same-site requests
                path="/",  # Set path to root
                max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
            return {"access_token": access_token, "token_type": "bearer"}

    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Use development-appropriate cookie settings in development mode
    if settings.APP_ENV == "development":
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,  # True for security (JS can use localStorage)
            secure=False,  # False for HTTP in development
            samesite="lax",  # Lax for same-site requests
            path="/",  # Set path to root
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    else:
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,  # True for security (prevents XSS)
            secure=True,  # True for HTTPS in production
            samesite="lax",  # Lax for same-site requests (more secure than none)
            path="/",  # Set path to root
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: UserModel = Depends(get_current_active_user)):
    return current_user


@router.post("/change-password")
def change_password(
    old_password: str,
    new_password: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not verify_password(old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    
    current_user.hashed_password = get_password_hash(new_password)
    db.commit()
    return {"message": "Password changed successfully"}
