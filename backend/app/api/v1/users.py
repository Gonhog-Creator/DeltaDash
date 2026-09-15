from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.auth import require_admin
from app.core.security import get_password_hash
from app.db.session import get_db
from app.db.models.user import User as UserModel
from app.schemas.user import UserCreate, UserUpdate, User as UserSchema

router = APIRouter(redirect_slashes=False)

VALID_ROLES = {"viewer", "editor", "admin"}


@router.get("/users", response_model=List[UserSchema])
def list_users(
    db: Session = Depends(get_db),
    _admin: UserModel = Depends(require_admin),
):
    """List all users (admin only)."""
    return db.query(UserModel).order_by(UserModel.username).all()


@router.post("/users", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    _admin: UserModel = Depends(require_admin),
):
    """Create a user. The plaintext password is hashed with bcrypt before storage."""
    username = user_in.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not user_in.password:
        raise HTTPException(status_code=400, detail="Password is required")
    if user_in.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")

    existing = db.query(UserModel).filter(UserModel.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    is_admin = user_in.is_admin or user_in.role == "admin"
    user = UserModel(
        username=username,
        full_name=user_in.full_name or username,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        is_active=user_in.is_active,
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserSchema)
def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: UserModel = Depends(require_admin),
):
    """Update user fields. If password is provided it is re-hashed."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.role is not None:
        if user_in.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
        user.role = user_in.role
        if user_in.role == "admin":
            user.is_admin = True

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.is_admin is not None:
        user.is_admin = user_in.is_admin
    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)

    # Prevent an admin from locking themselves out
    if user.id == current_admin.id and (not user.is_admin or not user.is_active):
        raise HTTPException(status_code=400, detail="You cannot remove your own admin access or deactivate your own account")

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_admin: UserModel = Depends(require_admin),
):
    """Delete a user (admin only). Admins cannot delete themselves."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    db.delete(user)
    db.commit()
    return None
