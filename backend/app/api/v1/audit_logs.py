from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.db.models.audit_log import AuditLog as AuditLogModel
from app.db.models.user import User as UserModel
from app.api.v1.auth import require_admin
from app.schemas.audit_log import AuditLog

router = APIRouter()


@router.get("/", response_model=List[AuditLog])
def list_audit_logs(
    user_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """List audit logs from the last N days (admin only)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(AuditLogModel).filter(AuditLogModel.created_at >= cutoff)

    if user_id:
        query = query.filter(AuditLogModel.user_id == user_id)
    if entity_type:
        query = query.filter(AuditLogModel.entity_type == entity_type)
    if action:
        query = query.filter(AuditLogModel.action == action)

    query = query.order_by(AuditLogModel.created_at.desc()).limit(limit)
    return query.all()


@router.get("/entity-types")
def list_entity_types(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """List distinct entity types in the audit log (admin only)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    results = db.query(AuditLogModel.entity_type).filter(
        AuditLogModel.created_at >= cutoff,
        AuditLogModel.entity_type.isnot(None),
    ).distinct().all()
    return [r[0] for r in results if r[0]]
