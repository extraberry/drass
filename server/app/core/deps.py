"""FastAPI dependencies: authentication + server-side RBAC (PRD s5, s47)."""
from typing import Optional
from fastapi import Depends, Header
from sqlalchemy.orm import Session
from ..db import get_db
from ..domain import rbac
from ..domain.enums import Role
from ..domain.errors import Forbidden
from ..models import User
from ..services import auth_service
from ..services.common import audit


def bearer_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(token: Optional[str] = Depends(bearer_token), db: Session = Depends(get_db)) -> User:
    return auth_service.authenticate_token(db, token)


def role_of(user: User) -> Role:
    return Role(user.role.role_name)


def require(permission: str):
    def dep(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        if not rbac.can(role_of(user), permission):
            audit(db, user.user_id, "PERMISSION_DENIED", "permission", permission, "DENIED",
                  f"role={user.role.role_name}")
            db.commit()
            raise Forbidden("You do not have permission to perform this action.")
        return user
    return dep
