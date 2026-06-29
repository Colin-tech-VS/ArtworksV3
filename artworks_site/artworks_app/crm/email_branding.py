"""Enveloppe HTML Artworks pour tous les emails (transactionnels et campagnes)."""
from __future__ import annotations

from flask import current_app, url_for

from ..models import User

_BRAND = {
    'name': 'Artworks',
    'tagline': 'Galeries & collectionneurs d\'art contemporain',
    'primary': '#1a2832',
    'accent': '#b8734a',
    'bg': '#f7f4ee',
    'text': '#1a2832',
    'muted': '#5a636c',
}


def personalize(template: str, user: User | None) -> str:
    if not template:
        return ''
    if user is None:
        user = _sample_user()
    name = user.display_name or user.username or 'Membre'
    role_labels = {
        'artiste': 'Artiste',
        'galerie': 'Galerie',
        'collectionneur': 'Collectionneur',
        'admin': 'Administrateur',
    }
    role_label = role_labels.get(user.role or '', user.role or '')
    plan = user.subscription_plan or 'free'
    return (
        template.replace('{{name}}', name)
        .replace('{{email}}', user.email or '')
        .replace('{{username}}', user.username or '')
        .replace('{{role}}', user.role or '')
        .replace('{{role_label}}', role_label)
        .replace('{{plan}}', plan)
    )


def _sample_user() -> User:
    u = User(
        username='camille',
        email='camille@example.com',
        display_name='Camille',
        role='artiste',
        subscription_plan='essentiel',
    )
    u.id = 0
    return u


def _site_url() -> str:
    try:
        return current_app.config.get('SITE_URL') or 'https://artworksdigital.fr'
    except RuntimeError:
        return 'https://artworksdigital.fr'


def _logo_url() -> str:
    try:
        return url_for('static', filename='img/logo-artworks.png', _external=True)
    except RuntimeError:
        return f'{_site_url()}/static/img/logo-artworks.png'


def render_branded_email(
    body_html: str,
    *,
    preview_text: str = '',
    subject: str = '',
    user: User | None = None,
) -> str:
    """Assemble le contenu dans le design Artworks unifié."""
    body = personalize(body_html or '', user)
    preheader = personalize(preview_text or '', user)
    site = _site_url()
    logo = _logo_url()
    year = __import__('datetime').datetime.utcnow().year

    hidden_preheader = (
        f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">'
        f'{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</div>'
        if preheader else ''
    )

    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>{subject or _BRAND["name"]}</title>
<!--[if mso]><style>table,td{{font-family:Arial,sans-serif!important}}</style><![endif]-->
</head>
<body style="margin:0;padding:0;background:{_BRAND["bg"]};font-family:Georgia,'Times New Roman',serif;color:{_BRAND["text"]};-webkit-font-smoothing:antialiased;">
{hidden_preheader}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{_BRAND["bg"]};">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background:#ffffff;border:1px solid #e8e4dc;">
<tr>
<td style="background:{_BRAND["primary"]};padding:28px 32px;text-align:center;">
<a href="{site}" style="text-decoration:none;color:#ffffff;">
<span style="font-family:Arial,Helvetica,sans-serif;font-size:22px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;">Artworks</span>
<span style="font-family:Arial,Helvetica,sans-serif;font-size:22px;font-weight:300;color:{_BRAND["accent"]};"> Salon</span>
</a>
<p style="margin:8px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#aaaaaa;letter-spacing:0.12em;text-transform:uppercase;">{_BRAND["tagline"]}</p>
</td>
</tr>
<tr>
<td style="height:3px;background:linear-gradient(90deg,{_BRAND["accent"]},#e8dcc0,{_BRAND["accent"]});font-size:0;line-height:0;">&nbsp;</td>
</tr>
<tr>
<td style="padding:36px 32px 28px;font-size:16px;line-height:1.65;color:{_BRAND["text"]};">
{body}
</td>
</tr>
<tr>
<td style="padding:0 32px 28px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0">
<tr><td style="border-top:1px solid #e8e4dc;padding-top:24px;text-align:center;">
<a href="{site}" style="display:inline-block;padding:12px 28px;background:{_BRAND["primary"]};color:#ffffff;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;">Visiter {_BRAND["name"]}</a>
</td></tr>
</table>
</td>
</tr>
<tr>
<td style="background:#faf8f5;padding:20px 32px;text-align:center;border-top:1px solid #e8e4dc;">
<p style="margin:0 0 6px;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:{_BRAND["muted"]};line-height:1.5;">
© {year} {_BRAND["name"]} · <a href="{site}" style="color:{_BRAND["muted"]};">artworksdigital.fr</a>
</p>
<p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:10px;color:#999999;">
Vous recevez cet email car vous avez un compte sur {_BRAND["name"]}.
</p>
</td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>'''
