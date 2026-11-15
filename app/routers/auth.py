from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import AuthAccount, AuthLoginRequest, AuthLoginResponse
from app.services.auth import AuthConfigurationError, AuthService
from app.services.db import DatabaseError
from app.middleware import client_ip


router = APIRouter(prefix="/api/auth", tags=["Authentication"])
auth_service = AuthService()
bearer = HTTPBearer(auto_error=False)


def _client_id(request: Request) -> str:
    return client_ip(request)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> tuple[str, AuthAccount]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация.")
    try:
        account = auth_service.get_account(credentials.credentials)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Сервис авторизации временно недоступен.") from exc
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация.")
    return credentials.credentials, account


def require_permission(permission: str):
    def check_permission(auth: tuple[str, AuthAccount] = Depends(require_auth)) -> AuthAccount:
        if permission not in auth[1].permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав.")
        return auth[1]

    return check_permission


require_scan = require_permission("scan")
require_dispatch = require_permission("dispatch")
require_users = require_permission("users")


@router.post("/login", response_model=AuthLoginResponse)
def login(payload: AuthLoginRequest, request: Request) -> AuthLoginResponse:
    client_id = _client_id(request)
    try:
        reservation = auth_service.reserve_login_attempt(payload.access_key, client_id)
        if reservation is None:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Слишком много попыток. Повторите позже.")
        result = auth_service.login_reserved(payload.access_key, client_id, reservation)
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Сервис входа временно недоступен.") from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Сервис входа временно недоступен.") from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ключ не подошёл.")
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth: tuple[str, AuthAccount] = Depends(require_auth)) -> Response:
    try:
        auth_service.revoke(auth[0])
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Сервис авторизации временно недоступен.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthAccount)
def me(auth: tuple[str, AuthAccount] = Depends(require_auth)) -> AuthAccount:
    return auth[1]
