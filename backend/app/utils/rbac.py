# FILE: backend/app/utils/rbac.py

from fastapi import Depends, HTTPException
from app.utils.jwt_handler import get_current_user


def require_role(role: str):
    """
    Restrict route to a specific role.
    Usage:
        @router.get(..., dependencies=[Depends(require_role("manufacturer"))])
    """
    def role_checker(user=Depends(get_current_user)):
        if user.role != role:
            raise HTTPException(status_code=403, detail="Access denied")
        return user

    return role_checker
