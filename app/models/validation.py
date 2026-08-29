from pydantic import BaseModel


class Identity(BaseModel):
    user_or_org: str
    scopes: list[str]


class VerifyResponse(BaseModel):
    status: str
    core_version: str
    instance_type: str
    identity: Identity