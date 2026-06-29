"""SMTP configuration — compatible Scalingo / V2 (SMTP_* et MAIL_*)."""
from __future__ import annotations

import os


def _clean(raw: str | None) -> str:
    val = (raw or '').strip().strip('\r\n')
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        val = val[1:-1].strip()
    return val


def smtp_config() -> dict:
    user = (
        _clean(os.environ.get('SMTP_USER'))
        or _clean(os.environ.get('EMAIL_ADDRESS'))
        or _clean(os.environ.get('MAIL_USERNAME'))
    )
    password = (
        _clean(os.environ.get('SMTP_PASSWORD'))
        or _clean(os.environ.get('EMAIL_PASSWORD'))
        or _clean(os.environ.get('MAIL_PASSWORD'))
        or _clean(os.environ.get('BREVO_SMTP_KEY'))
    )
    host = _clean(os.environ.get('SMTP_HOST')) or _clean(os.environ.get('MAIL_SERVER'))
    port_raw = _clean(os.environ.get('SMTP_PORT')) or _clean(os.environ.get('MAIL_PORT')) or '587'
    port = int(port_raw or '587')
    from_email = _clean(os.environ.get('SMTP_FROM')) or user or 'contact@artworksdigital.fr'
    from_name = _clean(os.environ.get('SMTP_FROM_NAME')) or 'Artworks'
    use_tls = os.environ.get('MAIL_USE_TLS', '').lower() in ('1', 'true', 'yes')
    use_ssl = port == 465 or os.environ.get('SMTP_USE_SSL', '').lower() in ('1', 'true', 'yes')
    if port == 465:
        use_ssl = True
        use_tls = False
    elif not use_ssl:
        use_tls = True
    sender = os.environ.get('MAIL_DEFAULT_SENDER') or f'{from_name} <{from_email}>'
    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'from_email': from_email,
        'from_display': from_name,
        'sender': sender,
        'use_tls': use_tls,
        'use_ssl': use_ssl,
        'ready': bool(host and user and password),
    }
