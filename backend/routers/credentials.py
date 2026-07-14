from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import CredentialSet
from backend.services import credentials as cred_service

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


@router.get("")
def list_credentials():
    return cred_service.list_services()


@router.get("/{service}")
def get_credential(service: str):
    val = cred_service.get_key(service)
    return {"service": service, "key": val}


@router.put("")
def set_credential(body: CredentialSet):
    cred_service.set_key(body.service, body.key)
    return {"ok": True}


@router.delete("/{service}")
def delete_credential(service: str):
    cred_service.delete_key(service)
    return {"ok": True}
