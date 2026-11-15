from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.routers.auth import auth_service, require_users
from app.schemas.auth import AuthAccount


router = APIRouter(prefix="/front/api/employees", tags=["Employees"])


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    role: Literal["admin", "dispatcher", "engineer"]


@router.get("")
def list_employees(_account: AuthAccount = Depends(require_users)) -> list[dict]:
    return auth_service.list_employees()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, account: AuthAccount = Depends(require_users)) -> dict:
    if payload.role == "admin" and account.role != "director":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Администратора может создать только директор.")
    employee, key = auth_service.create_employee(payload.full_name.strip(), payload.email.strip(), payload.role)
    return {"employee": employee, "access_key": key}


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: str, account: AuthAccount = Depends(require_users)) -> None:
    role = auth_service.get_employee_role(employee_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сотрудник не найден.")
    if role == "admin" and account.role != "director":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Удалить администратора может только директор.")
    auth_service.delete_employee(employee_id)
