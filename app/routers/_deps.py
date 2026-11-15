"""Общие зависимости роутеров.

`storage_dep` — request-time разрешение хранилища: без DSN роутеры
каталога/задач честно отвечают 503 вместо AttributeError (500).
"""
from fastapi import HTTPException, status

from app.services.storage import get_storage


def storage_dep():
    svc = get_storage()
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище PostgreSQL не настроено: задайте DATABASE_URL и перезапустите сервис.",
        )
    return svc
