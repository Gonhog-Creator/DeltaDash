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

    # Try to get token from cookie first, then from Authorization header
    token = None
    if access_token:
        # Remove "Bearer " prefix if present
        if access_token.startswith("Bearer "):
            token = access_token[7:]
        else:
            token = access_token
    elif authorization:
        token = authorization

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


@router.post("/login", response_model=Token)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Dev mode bypass: accept any password for admin user in development
    if settings.APP_ENV == "development" and form_data.username == "admin":
        user = db.query(UserModel).filter(UserModel.username == form_data.username).first()
        if user:
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.username}, expires_delta=access_token_expires
            )
            response.set_cookie(
                key="access_token",
                value=f"Bearer {access_token}",
                httponly=True,
                secure=False,  # False for HTTP in development
                samesite="lax",  # Lax for same-site requests in development
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
    
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,
        samesite="none",
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
