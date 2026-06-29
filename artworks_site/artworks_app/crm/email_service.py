"""Transactional / campaign email via SMTP (Scalingo / Brevo / LWS)."""
from __future__ import annotations

import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..mail_config import smtp_config
from ..models import EmailCampaign, EmailTemplate, User
from .email_branding import personalize, render_branded_email


def html_to_text(html: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.I)
    text = re.sub(r'</p>', '\n\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def build_message_html(*, body_html: str, preview_text: str = '', subject: str = '', user=None) -> str:
    return render_branded_email(body_html, preview_text=preview_text, subject=subject, user=user)


def send_email(to: str, subject: str, html: str, text: str | None = None) -> tuple[bool, str]:
    cfg = smtp_config()
    if not cfg['ready']:
        return False, 'SMTP non configuré (SMTP_HOST / SMTP_USER / SMTP_PASSWORD)'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = cfg['sender']
    msg['To'] = to

    if text:
        msg.attach(MIMEText(text, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    try:
        ctx = ssl.create_default_context()
        port = int(cfg['port'])
        if cfg['use_ssl']:
            server = smtplib.SMTP_SSL(cfg['host'], port, timeout=30, context=ctx)
        else:
            server = smtplib.SMTP(cfg['host'], port, timeout=30)
        with server as s:
            s.ehlo()
            if not cfg['use_ssl'] and cfg['use_tls']:
                s.starttls(context=ctx)
                s.ehlo()
            s.login(cfg['user'], cfg['password'])
            s.sendmail(cfg['sender'], [to], msg.as_string())
        return True, 'ok'
    except Exception as exc:
        return False, str(exc)


def send_to_user(*, user: User, subject: str, body_html: str, preview_text: str = '') -> tuple[bool, str]:
    if not user.email:
        return False, 'Pas d\'adresse email'
    subj = personalize(subject, user)
    html = build_message_html(body_html=body_html, preview_text=preview_text, subject=subj, user=user)
    text = html_to_text(personalize(body_html, user))
    return send_email(user.email, subj, html, text)


def send_transactional(template_slug: str, user: User) -> tuple[bool, str]:
    tpl = EmailTemplate.query.filter_by(slug=template_slug, active=True).first()
    if tpl is None:
        return False, f'Template {template_slug} introuvable'
    if not tpl.auto_send:
        return False, 'Envoi automatique désactivé pour ce template'
    return send_to_user(
        user=user,
        subject=tpl.subject,
        body_html=tpl.body_html or '',
        preview_text=tpl.preview_text or '',
    )


def resolve_campaign_recipients(campaign: EmailCampaign) -> list[User]:
    from .segments import segment_users

    mode = campaign.recipient_mode or 'segment'
    if mode == 'role' and campaign.recipient_role:
        return (
            User.query
            .filter(
                User.role == campaign.recipient_role,
                User.is_staff.is_(False),
                User.role != 'admin',
            )
            .order_by(User.id)
            .all()
        )
    if mode == 'users':
        ids = campaign.recipient_user_ids or []
        if not ids:
            return []
        return (
            User.query
            .filter(User.id.in_(ids), User.is_staff.is_(False))
            .order_by(User.id)
            .all()
        )
    if campaign.segment_id and campaign.segment:
        return segment_users(campaign.segment.filters)
    return []


def send_campaign_to_users(campaign, users) -> tuple[int, int, list[str]]:
    sent = 0
    failed = 0
    errors: list[str] = []

    for user in users:
        if not user.email:
            failed += 1
            continue
        ok, err = send_to_user(
            user=user,
            subject=campaign.subject,
            body_html=campaign.body_html or '',
            preview_text=campaign.preview_text or '',
        )
        if ok:
            sent += 1
        else:
            failed += 1
            if len(errors) < 5:
                errors.append(f'{user.email}: {err}')

    return sent, failed, errors
