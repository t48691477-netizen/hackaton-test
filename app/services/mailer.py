import json
import os
import smtplib
import ssl
import threading
import time
import urllib.request
import uuid
from email.message import EmailMessage
from email.utils import formatdate, parseaddr


class MailNotConfigured(Exception):
    pass


class MailRateLimited(Exception):
    pass


class MailDeliveryError(Exception):
    pass


_lock = threading.Lock()
_sent: list[tuple[float, object]] = []


def current_provider() -> str:
    if os.environ.get("RESEND_API_KEY", "").strip() or os.environ.get(
        "RESEND_FROM_EMAIL", ""
    ).strip():
        return "resend"
    return "smtp"


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


def _resend_cfg() -> dict:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("RESEND_FROM_EMAIL", "").strip()
    if not api_key:
        raise MailNotConfigured("Resend is not configured: set RESEND_API_KEY.")
    if not sender:
        raise MailNotConfigured("Resend is not configured: set RESEND_FROM_EMAIL.")

    address = parseaddr(sender)[1]
    local, separator, domain = address.rpartition("@")
    if not separator or not local or not domain or any(c.isspace() for c in address):
        raise MailNotConfigured("RESEND_FROM_EMAIL must be a valid email address.")
    return {"api_key": api_key, "sender": sender}


def _check_rate() -> object:
    limit = int(os.environ.get("SMTP_MAX_PER_HOUR", "30"))
    now = time.time()
    reservation = object()
    with _lock:
        _sent[:] = [(sent_at, token) for sent_at, token in _sent if now - sent_at < 3600]
        if len(_sent) >= limit:
            raise MailRateLimited("Достигнут лимит отправки писем в час.")
        _sent.append((now, reservation))
    return reservation


def _release_rate(reservation: object) -> None:
    with _lock:
        for index, (_sent_at, token) in enumerate(_sent):
            if token is reservation:
                del _sent[index]
                break


def _send_resend(msg: EmailMessage, cfg: dict) -> str:
    payload = {
        "from": cfg["sender"],
        "to": [msg["To"]],
        "subject": msg["Subject"],
        "text": msg.get_content(),
    }
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        status = getattr(response, "status", None)
        if status is None:
            status = response.getcode()
        if not 200 <= status < 300:
            raise ValueError("Unexpected Resend response status")
        result = json.loads(response.read())
    message_id = result.get("id") if isinstance(result, dict) else None
    if not isinstance(message_id, str) or not message_id.strip():
        raise ValueError("Resend response did not contain a message id")
    return message_id


def send_access_key(to: str, full_name: str, role: str, access_key: str) -> str:
    provider = current_provider()
    cfg = _resend_cfg() if provider == "resend" else _cfg()
    reservation = _check_rate()

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

    delivery_error = None
    try:
        if provider == "resend":
            message_id = _send_resend(msg, cfg)
        else:
            ctx = ssl.create_default_context()
            if cfg["mode"] == "ssl":
                server = smtplib.SMTP_SSL(
                    cfg["host"], cfg["port"], timeout=15, context=ctx
                )
            else:
                server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
            with server:
                if cfg["mode"] == "starttls":
                    server.starttls(context=ctx)
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
    except Exception as exc:
        delivery_error = type(exc).__name__

    if delivery_error is not None:
        _release_rate(reservation)
        raise MailDeliveryError(
            f"Не удалось отправить письмо: {delivery_error}"
        ) from None

    return message_id
