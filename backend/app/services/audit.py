from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from app.db.models.audit_log import AuditLog
from app.db.models.user import User


def log_action(
    db: Session,
    user: User,
    action: str,
    entity_type: str,
    entity_id: Optional[Any] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
):
    """Create an audit log entry. Call before db.commit() so it's in the same transaction."""
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=uuid.UUID(str(entity_id)) if entity_id else None,
        before_json=before,
        after_json=after,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry


def serialize_model(obj) -> dict:
    """Best-effort serialization of a SQLAlchemy model to a dict for audit logging."""
    if obj is None:
        return None
    result = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name, None)
        if value is None:
            result[column.name] = None
        elif isinstance(value, (str, int, float, bool)):
            result[column.name] = value
        elif isinstance(value, datetime):
            result[column.name] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            result[column.name] = str(value)
        else:
            try:
                result[column.name] = str(value)
            except Exception:
                result[column.name] = None
    return result
