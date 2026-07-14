from __future__ import annotations

from pydantic import BaseModel


class InstanceCreate(BaseModel):
    name: str
    type: str  # 'docker' | 'local' | 'remote'
    url: str = "http://localhost:11434"
    api_key: str | None = None
    container_id: str | None = None
    gguf_dir: str | None = None
    container_gguf_dir: str | None = None


class InstanceUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    url: str | None = None
    api_key: str | None = None
    container_id: str | None = None
    gguf_dir: str | None = None
    container_gguf_dir: str | None = None


class ModelImport(BaseModel):
    instance_id: str
    gguf_path: str
    model_name: str


class ModelPull(BaseModel):
    instance_id: str
    name: str


class HuggingFacePull(BaseModel):
    instance_id: str
    url: str
    hf_token: str | None = None


class ModelDelete(BaseModel):
    instance_id: str
    name: str


class ModelInspect(BaseModel):
    instance_id: str
    name: str


class CredentialSet(BaseModel):
    service: str
    key: str
