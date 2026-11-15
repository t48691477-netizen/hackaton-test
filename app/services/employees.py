"""Employee directory operations across the employees and credentials databases."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from app.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeInvitationResponse,
    EmployeeProvisionResponse,
    EmployeeResponse,
)
from app.services import mailer
from app.services.auth import AuthService
from app.services.db import DatabaseError, PostgresPool, pools


class EmployeeNotFoundError(LookupError):
    pass


class EmployeeEmailConflictError(ValueError):
    pass


class EmployeeRoleForbiddenError(PermissionError):
    pass


class EmployeeService:
    def __init__(
        self,
        employees_pool: Optional[PostgresPool] = None,
        auth_service: Optional[AuthService] = None,
        send_access_key: Optional[Callable[[str, str, str, str], str]] = None,
    ):
        self._employees_pool = employees_pool
        self.auth_service = auth_service or AuthService()
        self._send_access_key = send_access_key or mailer.send_access_key

    @property
    def employees_pool(self) -> PostgresPool:
        if self._employees_pool is None:
            self._employees_pool = pools.get("employees")
        return self._employees_pool

    @staticmethod
    def _employee_uuid(employee_id: str | UUID) -> str:
        try:
            return str(UUID(str(employee_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("employee_id must be a UUID") from exc

    def list_active(self) -> list[EmployeeResponse]:
        with self.employees_pool.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name, email, role
                FROM promscan.employees
                WHERE is_active = true
                ORDER BY full_name, id
                """
            )
            rows = cur.fetchall()
        return [EmployeeResponse(**row) for row in (rows or [])]

    @staticmethod
    def _is_unique_violation(exc: DatabaseError) -> bool:
        return getattr(exc.__cause__, "sqlstate", None) == "23505"

    def _insert_employee(self, payload: EmployeeCreateRequest) -> EmployeeResponse:
        try:
            with self.employees_pool.cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO promscan.employees (full_name, email, role)
                    VALUES (%s, %s, %s)
                    RETURNING id, full_name, email, role
                    """,
                    (payload.full_name, payload.email, payload.role),
                )
                row = cur.fetchone()
        except DatabaseError as exc:
            if self._is_unique_violation(exc):
                raise EmployeeEmailConflictError(payload.email) from exc
            raise
        if row is None:
            raise DatabaseError("Employee insert returned no row")
        return EmployeeResponse(**row)

    def _delete_employee_record(self, employee_id: str) -> None:
        with self.employees_pool.cursor(commit=True) as cur:
            cur.execute("DELETE FROM promscan.employees WHERE id = %s", (employee_id,))

    def _set_invitation(
        self,
        employee_id: str,
        *,
        status_value: str,
        provider: str | None,
        sent_at: datetime | None = None,
        error: str | None = None,
    ) -> None:
        with self.employees_pool.cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE promscan.employees
                SET invitation_status = %s,
                    invitation_provider = %s,
                    invitation_sent_at = %s,
                    invitation_error = %s
                WHERE id = %s AND is_active = true
                """,
                (status_value, provider, sent_at, error, employee_id),
            )

    @staticmethod
    def _invitation(
        email: str,
        *,
        status_value: str,
        provider: str | None,
        sent_at: datetime | None = None,
    ) -> EmployeeInvitationResponse:
        sent_iso = (
            sent_at.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
            if sent_at
            else None
        )
        return EmployeeInvitationResponse(
            status=status_value,
            provider=provider,
            email=email,
            sent_at=sent_iso,
        )

    def _cleanup_created_employee(self, employee_id: str) -> None:
        failures = []
        try:
            self.auth_service.revoke_employee_access(employee_id)
        except Exception as exc:
            failures.append(exc)
        try:
            self._delete_employee_record(employee_id)
        except Exception as exc:
            failures.append(exc)
        if failures:
            raise DatabaseError("Employee provisioning cleanup failed") from failures[0]

    def create(
        self, payload: EmployeeCreateRequest, *, actor_role: str
    ) -> EmployeeProvisionResponse:
        if payload.role == "admin" and actor_role != "director":
            raise EmployeeRoleForbiddenError(
                "Only a director may create an administrator"
            )

        employee = self._insert_employee(payload)
        employee_id = str(employee.id)
        try:
            access_key = self.auth_service.generate_access_key()
            self.auth_service.provision_employee_access(employee_id, access_key)
        except Exception as exc:
            try:
                self._cleanup_created_employee(employee_id)
            except DatabaseError as cleanup_exc:
                raise cleanup_exc from exc
            raise

        try:
            self._send_access_key(
                employee.email, employee.full_name, employee.role, access_key
            )
        except Exception as exc:
            try:
                self._cleanup_created_employee(employee_id)
            except DatabaseError as cleanup_exc:
                raise cleanup_exc from exc
            raise

        sent_at = datetime.now(timezone.utc)
        try:
            self._set_invitation(
                employee_id,
                status_value="sent",
                provider="smtp",
                sent_at=sent_at,
            )
        except Exception as exc:
            try:
                self._cleanup_created_employee(employee_id)
            except DatabaseError as cleanup_exc:
                raise cleanup_exc from exc
            raise
        return EmployeeProvisionResponse(
            account=employee,
            invitation=self._invitation(
                employee.email,
                status_value="sent",
                provider="smtp",
                sent_at=sent_at,
            ),
        )

    def rotate_access(
        self, employee_id: str | UUID, *, actor_role: str
    ) -> EmployeeProvisionResponse:
        normalized_id = self._employee_uuid(employee_id)
        with self.employees_pool.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name, email, role
                FROM promscan.employees
                WHERE id = %s AND is_active = true
                """,
                (normalized_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise EmployeeNotFoundError(normalized_id)

        employee = EmployeeResponse(**row)
        if employee.role == "admin" and actor_role != "director":
            raise EmployeeRoleForbiddenError(
                "Only a director may rotate an administrator key"
            )

        rotated = self.auth_service.rotate_employee_access(normalized_id)
        try:
            self._send_access_key(
                employee.email,
                employee.full_name,
                employee.role,
                rotated.access_key,
            )
        except Exception as exc:
            try:
                self.auth_service.restore_employee_access(
                    normalized_id,
                    rotated.previous_key_hash,
                    rotated.previous_key_salt,
                )
                self._set_invitation(
                    normalized_id,
                    status_value="failed",
                    provider="smtp",
                    error=type(exc).__name__,
                )
            except Exception as compensation_exc:
                raise DatabaseError("Access-key rotation compensation failed") from compensation_exc
            raise

        sent_at = datetime.now(timezone.utc)
        self._set_invitation(
            normalized_id,
            status_value="sent",
            provider="smtp",
            sent_at=sent_at,
        )
        return EmployeeProvisionResponse(
            account=employee,
            invitation=self._invitation(
                employee.email,
                status_value="sent",
                provider="smtp",
                sent_at=sent_at,
            ),
        )

    def deactivate(self, employee_id: str | UUID) -> None:
        normalized_id = self._employee_uuid(employee_id)

        # This transaction belongs only to the employees database. The
        # credential transaction below is intentionally a separate operation.
        with self.employees_pool.cursor(commit=True) as cur:
            cur.execute(
                """
                SELECT id
                FROM promscan.employees
                WHERE id = %s
                """,
                (normalized_id,),
            )
            if cur.fetchone() is None:
                raise EmployeeNotFoundError(normalized_id)
            cur.execute(
                """
                UPDATE promscan.employees
                SET is_active = false
                WHERE id = %s
                """,
                (normalized_id,),
            )

        # DELETE is idempotent. The FK cascade removes all auth sessions and
        # pending verification codes attached to this credential.
        self.auth_service.revoke_employee_access(normalized_id)
