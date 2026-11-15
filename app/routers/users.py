from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.routers.auth import require_users
from app.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeProvisionResponse,
    EmployeeResponse,
)
from app.services import mailer
from app.services.auth import AuthConfigurationError
from app.services.db import DatabaseError
from app.services.employees import (
    EmployeeEmailConflictError,
    EmployeeNotFoundError,
    EmployeeRoleForbiddenError,
    EmployeeService,
)


router = APIRouter(prefix="/api/users", tags=["Users"])
employee_service = EmployeeService()


@router.get("", response_model=list[EmployeeResponse])
def get_active_employees(_account=Depends(require_users)):
    try:
        return employee_service.list_active()
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище сотрудников временно недоступно.",
        ) from exc


@router.post(
    "",
    response_model=EmployeeProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    payload: EmployeeCreateRequest,
    account=Depends(require_users),
) -> EmployeeProvisionResponse:
    try:
        return employee_service.create(payload, actor_role=account.role)
    except EmployeeEmailConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сотрудник с таким email уже существует.",
        ) from exc
    except EmployeeRoleForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для этой роли сотрудника.",
        ) from exc
    except mailer.MailRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Достигнут лимит отправки приглашений. Повторите позже.",
        ) from exc
    except mailer.MailNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Почтовый сервис временно недоступен.",
        ) from exc
    except mailer.MailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить письмо с доступом.",
        ) from exc
    except (AuthConfigurationError, DatabaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище сотрудников, credentials или почта временно недоступны.",
        ) from exc


@router.post(
    "/{employee_id}/access",
    response_model=EmployeeProvisionResponse,
)
def rotate_employee_access(
    employee_id: UUID,
    account=Depends(require_users),
) -> EmployeeProvisionResponse:
    try:
        return employee_service.rotate_access(employee_id, actor_role=account.role)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активный сотрудник не найден.",
        ) from exc
    except EmployeeRoleForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Перевыпускать ключ администратора может только директор.",
        ) from exc
    except mailer.MailRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Достигнут лимит отправки приглашений. Повторите позже.",
        ) from exc
    except mailer.MailNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Почтовый сервис временно недоступен.",
        ) from exc
    except mailer.MailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить письмо с доступом.",
        ) from exc
    except (AuthConfigurationError, DatabaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище сотрудников, credentials или почта временно недоступны.",
        ) from exc


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_employee(employee_id: UUID, _account=Depends(require_users)) -> None:
    try:
        employee_service.deactivate(employee_id)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сотрудник не найден.",
        ) from exc
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище сотрудников или credentials временно недоступно.",
        ) from exc
