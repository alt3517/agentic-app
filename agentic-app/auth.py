from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
import os
from typing import Iterator

import jwt
from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]
    access_token: str


_principal_context: ContextVar[Principal | None] = ContextVar("principal", default=None)


def validate_signing_key() -> None:
    if len(os.getenv("AI_JWT_SIGNING_KEY", "").encode("utf-8")) < 32:
        raise RuntimeError("AI_JWT_SIGNING_KEY must contain at least 32 bytes.")


def decode_access_token(token: str) -> Principal:
    key = os.getenv("AI_JWT_SIGNING_KEY", "")
    validate_signing_key()

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["HS256"],
            issuer="service-desk-main-app",
            audience="service-desk-agentic-app",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid main-app access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")

    roles_claim = claims.get("role", [])
    roles = {roles_claim} if isinstance(roles_claim, str) else set(roles_claim)
    return Principal(claims["sub"], frozenset(roles), token)


def bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A bearer token issued by main-app is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def current_principal() -> Principal:
    principal = _principal_context.get()
    if principal is None:
        raise HTTPException(status_code=401, detail="No authenticated MCP caller.")
    return principal


@contextmanager
def principal_context(principal: Principal) -> Iterator[None]:
    token: Token[Principal | None] = _principal_context.set(principal)
    try:
        yield
    finally:
        _principal_context.reset(token)
