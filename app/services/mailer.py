import os
import smtplib
import ssl
import threading
import time
import uuid
from email.message import EmailMessage
from email.utils import formatdate


class MailNotConfigured(Exception):
    pass


class MailRateLimited(Exception):
    pass


class MailDeliveryError(Exception):
    pass


_lock = threading.Lock()
_sent: list[float] = []


def _cfg() -> dict:
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip() or user
    if not host or not sender:
        raise MailNotConfigured("SMTP не настроен: задайте SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM.")
    port = int(os.environ.get("SMTP_PORT", "587"))
    mode = os.environ.get("SMTP_SECURITY", "ssl" if port == 465 else "starttls").lower()
    return {
        "host": host,
        "port": port,
        "mode": mode,
        "user": user,
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "sender": sender,
    }


def _check_rate() -> None:
    limit = int(os.environ.get("SMTP_MAX_PER_HOUR", "30"))
    now = time.time()
    with _lock:
        _sent[:] = [t for t in _sent if now - t < 3600]
        if len(_sent) >= limit:
            raise MailRateLimited("Достигнут лимит отправки писем в час.")
        _sent.append(now)


def send_access_key(to: str, full_name: str, role: str, access_key: str) -> str:
    cfg = _cfg()
    _check_rate()

    msg = EmailMessage()
    message_id = f"<{uuid.uuid4()}@promscan>"
    msg["Message-ID"] = message_id
    msg["Date"] = formatdate(localtime=True)
    msg["From"] = cfg["sender"]
    msg["To"] = to
    msg["Subject"] = "ПромСкан: ключ доступа к веб-панели"
    msg.set_content(
        "\n".join(
            [
                f"Здравствуйте, {full_name}!",
                "",
                f"Для вас создана учётная запись в веб-панели «ПромСкан» (КСТ Энерго). Роль: {role}.",
                "",
                f"Ваш ключ доступа: {access_key}",
                "",
                "Ключ личный, не пересылайте его. Если письмо пришло по ошибке, проигнорируйте его.",
            ]
        )
    )

    try:
        ctx = ssl.create_default_context()
        if cfg["mode"] == "ssl":
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15, context=ctx)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
        with server:
            if cfg["mode"] == "starttls":
                server.starttls(context=ctx)
            if cfg["user"]:
                server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
    except Exception as exc:
        with _lock:
            if _sent:
                _sent.pop()
        raise MailDeliveryError(f"Не удалось отправить письмо: {type(exc).__name__}") from exc

    return message_id
