"""Merge SMTP vars from Artworks Digital V2 .env into artworks_site .env."""
import os

SRC_PATHS = [
    os.path.join(os.path.dirname(__file__), '..', '..', 'Artworks Digital V2', '.env'),
    os.path.join(os.path.dirname(__file__), '..', '..', 'Art_Peintures', 'Artworks', 'frontend', 'template', '.env'),
]
DST = os.path.join(os.path.dirname(__file__), '.env')
KEYS = {
    'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM', 'SMTP_FROM_NAME',
    'MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'BREVO_SMTP_KEY', 'MAIL_PORT', 'MAIL_USE_TLS',
}


def parse_env(path):
    data = {}
    if not os.path.isfile(path):
        return data
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def main():
    dst = parse_env(DST)
    for src_path in SRC_PATHS:
        src = parse_env(src_path)
        for k in KEYS:
            if src.get(k) and not dst.get(k):
                dst[k] = src[k]
        # Map template naming
        if src.get('MAIL_SERVER') and not dst.get('SMTP_HOST'):
            dst['SMTP_HOST'] = src['MAIL_SERVER']
        if src.get('MAIL_USERNAME') and not dst.get('SMTP_USER'):
            dst['SMTP_USER'] = src['MAIL_USERNAME']
        if src.get('MAIL_PASSWORD') and not dst.get('SMTP_PASSWORD'):
            dst['SMTP_PASSWORD'] = src['MAIL_PASSWORD']
        if src.get('SMTP_SERVER') and not dst.get('SMTP_HOST'):
            dst['SMTP_HOST'] = src['SMTP_SERVER']
        if src.get('SMTP_USER') and not dst.get('SMTP_USER'):
            dst['SMTP_USER'] = src['SMTP_USER']
    if dst.get('SMTP_HOST') and not dst.get('MAIL_SERVER'):
        dst['MAIL_SERVER'] = dst['SMTP_HOST']
    if dst.get('SMTP_USER') and not dst.get('MAIL_USERNAME'):
        dst['MAIL_USERNAME'] = dst['SMTP_USER']
    pw = dst.get('SMTP_PASSWORD') or dst.get('BREVO_SMTP_KEY')
    if pw and not dst.get('MAIL_PASSWORD'):
        dst['MAIL_PASSWORD'] = pw
    if dst.get('SMTP_FROM') and not dst.get('MAIL_DEFAULT_SENDER'):
        dst['MAIL_DEFAULT_SENDER'] = dst['SMTP_FROM']
    if dst.get('SMTP_PORT') and not dst.get('MAIL_PORT'):
        dst['MAIL_PORT'] = dst['SMTP_PORT']
    if not dst.get('MAIL_USE_TLS'):
        dst['MAIL_USE_TLS'] = '1' if str(dst.get('SMTP_PORT', '587')) != '465' else '0'

    order = [
        'SECRET_KEY', 'MISTRAL_API_KEY', 'MISTRAL_MODEL', 'MISTRAL_MODEL_HEAVY', 'AI_PRIMARY',
        'STRIPE_PUBLISHABLE_KEY', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'SITE_URL',
        'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM', 'SMTP_FROM_NAME',
        'MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_DEFAULT_SENDER',
        'ADMIN_EMAILS',
    ]
    written = set()
    with open(DST, 'w', encoding='utf-8') as f:
        for k in order:
            if k in dst:
                f.write(f'{k}={dst[k]}\n')
                written.add(k)
        for k, v in dst.items():
            if k not in written:
                f.write(f'{k}={v}\n')
    ready = bool((dst.get('MAIL_USERNAME') or dst.get('SMTP_USER')) and (dst.get('MAIL_PASSWORD') or dst.get('SMTP_PASSWORD')))
    print('SMTP ready:', ready)
    print('Host:', dst.get('SMTP_HOST') or dst.get('MAIL_SERVER') or '(empty)')


if __name__ == '__main__':
    main()
