from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.schemas.auth import AuthAccount, AuthLoginRequest, AuthLoginResponse
from app.services.auth import AuthConfigurationError, AuthService
from app.middleware import client_ip


router = APIRouter(prefix="/api/auth", tags=["Authentication"])
auth_service = AuthService(settings.DB_PATH)
bearer = HTTPBearer(auto_error=False)


def _client_id(request: Request) -> str:
    return client_ip(request)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> tuple[str, AuthAccount]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация.")
    account = auth_service.get_account(credentials.credentials)
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
    if not auth_service.reserve_login_attempt(client_id):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Слишком много попыток. Повторите позже.")
    try:
        result = auth_service.login_reserved(payload.access_key, client_id)
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Сервис входа временно недоступен.") from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ключ не подошёл.")
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth: tuple[str, AuthAccount] = Depends(require_auth)) -> Response:
    auth_service.revoke(auth[0])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthAccount)
def me(auth: tuple[str, AuthAccount] = Depends(require_auth)) -> AuthAccount:
    return auth[1]
