from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Protocol as ProtocolModel
from app.api.v1.auth import get_current_active_user, require_write_access
from app.schemas.protocol import ProtocolCreate, ProtocolUpdate, Protocol
from app.db.models.user import User as UserModel


router = APIRouter()


@router.get("/", response_model=List[Protocol])
def list_protocols(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    protocols = db.query(ProtocolModel).all()
    return protocols


@router.post("/", response_model=Protocol, status_code=status.HTTP_201_CREATED)
def create_protocol(
    protocol: ProtocolCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    db_protocol = ProtocolModel(**protocol.model_dump())
    db.add(db_protocol)
    db.commit()
    db.refresh(db_protocol)
    return db_protocol


@router.get("/{protocol_id}", response_model=Protocol)
def get_protocol(
    protocol_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    protocol = db.query(ProtocolModel).filter(ProtocolModel.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return protocol


@router.patch("/{protocol_id}", response_model=Protocol)
def update_protocol(
    protocol_id: str,
    protocol_update: ProtocolUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    protocol = db.query(ProtocolModel).filter(ProtocolModel.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    update_data = protocol_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(protocol, field, value)
    
    db.commit()
    db.refresh(protocol)
    return protocol


@router.delete("/{protocol_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_protocol(
    protocol_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    protocol = db.query(ProtocolModel).filter(ProtocolModel.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    db.delete(protocol)
    db.commit()


@router.get("/threat-levels/grouped")
def get_threat_levels_grouped(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get all threat levels grouped by protocol.
    Returns a list of protocols with their threat levels.
    Threat levels are prefixed with protocol name for uniqueness.
    """
    protocols = db.query(ProtocolModel).all()
    
    result = []
    for protocol in protocols:
        levels = []
        if protocol.levels_config:
            for level in protocol.levels_config:
                # Create protocol-prefixed level name for uniqueness
                level_name = level.get("level_name", "")
                prefixed_name = f"{protocol.name} - {level_name}"
                levels.append(prefixed_name)
        
        result.append({
            "protocol_id": str(protocol.id),
            "protocol_name": protocol.name,
            "threat_levels": levels
        })
    
    return result
