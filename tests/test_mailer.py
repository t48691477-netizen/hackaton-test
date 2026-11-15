import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from app.services import mailer


ACCESS_KEY = "access-key-test-secret"
API_KEY = "resend-api-test-secret"


@pytest.fixture(autouse=True)
def clear_rate_limit():
    with mailer._lock:
        mailer._sent.clear()
    yield
    with mailer._lock:
        mailer._sent.clear()


def _clear_mail_settings(monkeypatch):
    for name in (
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "SMTP_PORT",
        "SMTP_SECURITY",
        "SMTP_MAX_PER_HOUR",
    ):
        monkeypatch.delenv(name, raising=False)


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return self.body


def test_resend_sends_access_key_and_returns_provider_message_id(monkeypatch):
    _clear_mail_settings(monkeypatch)
    monkeypatch.setenv("RESEND_API_KEY", API_KEY)
    monkeypatch.setenv("RESEND_FROM_EMAIL", "PromScan <mail@example.test>")
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(b'{"id":"re_123"}')

    monkeypatch.setattr(mailer.urllib.request, "urlopen", fake_urlopen)

    assert mailer.current_provider() == "resend"
    assert mailer.send_access_key(
        "employee@example.test", "Test Employee", "engineer", ACCESS_KEY
    ) == "re_123"

    request, timeout = requests[0]
    payload = json.loads(request.data)
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Authorization") == f"Bearer {API_KEY}"
    assert payload["from"] == "PromScan <mail@example.test>"
    assert payload["to"] == ["employee@example.test"]
    assert ACCESS_KEY in payload["text"]
    assert timeout == 15


@pytest.mark.parametrize(
    ("api_key", "sender", "message"),
    [
        ("", "mail@example.test", "RESEND_API_KEY"),
        (API_KEY, "", "RESEND_FROM_EMAIL"),
        (API_KEY, "not-an-email", "valid email address"),
    ],
)
def test_resend_configuration_failures_are_reported_before_delivery(
    monkeypatch, api_key, sender, message
):
    _clear_mail_settings(monkeypatch)
    monkeypatch.setenv("RESEND_API_KEY", api_key)
    monkeypatch.setenv("RESEND_FROM_EMAIL", sender)
    monkeypatch.setattr(
        mailer.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("HTTP should not be called"),
    )

    with pytest.raises(mailer.MailNotConfigured, match=message):
        mailer.send_access_key("employee@example.test", "Test", "engineer", ACCESS_KEY)

    assert mailer._sent == []


def test_resend_provider_failure_does_not_expose_access_key_or_api_key(monkeypatch):
    _clear_mail_settings(monkeypatch)
    monkeypatch.setenv("RESEND_API_KEY", API_KEY)
    monkeypatch.setenv("RESEND_FROM_EMAIL", "mail@example.test")

    def fail_urlopen(_request, timeout):
        assert timeout == 15
        raise OSError(f"request failed with {API_KEY} and {ACCESS_KEY}")

    monkeypatch.setattr(mailer.urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(mailer.MailDeliveryError) as captured:
        mailer.send_access_key("employee@example.test", "Test", "engineer", ACCESS_KEY)

    rendered_error = f"{captured.value!s} {captured.value!r}"
    assert "OSError" in rendered_error
    assert API_KEY not in rendered_error
    assert ACCESS_KEY not in rendered_error
    assert captured.value.__context__ is None
    assert mailer._sent == []


def test_resend_http_error_does_not_expose_provider_details(monkeypatch):
    _clear_mail_settings(monkeypatch)
    monkeypatch.setenv("RESEND_API_KEY", API_KEY)
    monkeypatch.setenv("RESEND_FROM_EMAIL", "mail@example.test")

    def reject_request(*_args, **_kwargs):
        raise HTTPError(
            "https://api.resend.com/emails",
            401,
            f"rejected {API_KEY} {ACCESS_KEY}",
            hdrs=None,
            fp=BytesIO(f"provider said {ACCESS_KEY}".encode()),
        )

    monkeypatch.setattr(mailer.urllib.request, "urlopen", reject_request)

    with pytest.raises(mailer.MailDeliveryError) as captured:
        mailer.send_access_key("employee@example.test", "Test", "engineer", ACCESS_KEY)

    rendered_error = f"{captured.value!s} {captured.value!r}"
    assert "HTTPError" in rendered_error
    assert API_KEY not in rendered_error
    assert ACCESS_KEY not in rendered_error
    assert captured.value.__context__ is None


def test_resend_hourly_rate_limit_blocks_additional_requests(monkeypatch):
    _clear_mail_settings(monkeypatch)
    monkeypatch.setenv("RESEND_API_KEY", API_KEY)
    monkeypatch.setenv("RESEND_FROM_EMAIL", "mail@example.test")
    monkeypatch.setenv("SMTP_MAX_PER_HOUR", "1")
    calls = []
    monkeypatch.setattr(
        mailer.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (calls.append("sent") or FakeResponse(b'{"id":"re_1"}')),
    )

    mailer.send_access_key("one@example.test", "One", "engineer", ACCESS_KEY)
    with pytest.raises(mailer.MailRateLimited):
        mailer.send_access_key("two@example.test", "Two", "engineer", ACCESS_KEY)

    assert calls == ["sent"]


def test_smtp_remains_default_and_sends_message(monkeypatch):
    _clear_mail_settings(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "mail@example.test")
    monkeypatch.setenv("SMTP_PORT", "25")
    monkeypatch.setenv("SMTP_SECURITY", "none")
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example.test", 25, 15)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(
        mailer.smtplib,
        "SMTP_SSL",
        lambda *_args, **_kwargs: pytest.fail("SSL transport should not be called"),
    )

    assert mailer.current_provider() == "smtp"
    message_id = mailer.send_access_key(
        "employee@example.test", "Test Employee", "engineer", ACCESS_KEY
    )

    assert message_id.startswith("<") and message_id.endswith("@promscan>")
    assert len(sent_messages) == 1
    assert sent_messages[0]["To"] == "employee@example.test"
    assert ACCESS_KEY in sent_messages[0].get_content()


def test_smtp_failure_is_safely_mapped_and_releases_rate_slot(monkeypatch):
    _clear_mail_settings(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "mail@example.test")

    def fail_smtp(*_args, **_kwargs):
        raise OSError(f"SMTP failed with {ACCESS_KEY}")

    monkeypatch.setattr(mailer.smtplib, "SMTP", fail_smtp)

    with pytest.raises(mailer.MailDeliveryError) as captured:
        mailer.send_access_key("employee@example.test", "Test", "engineer", ACCESS_KEY)

    assert str(captured.value) == "Не удалось отправить письмо: OSError"
    assert ACCESS_KEY not in repr(captured.value)
    assert mailer._sent == []
