"""Merge social API vars from Artworks Digital V2 .env into artworks_site .env."""
import os

SRC_PATHS = [
    os.path.join(os.path.dirname(__file__), '..', '..', 'Artworks Digital V2', '.env'),
]
DST = os.path.join(os.path.dirname(__file__), '.env')
KEYS = {
    'FACEBOOK_PAGE_ACCESS_TOKEN', 'FB_PAGE_TOKEN', 'FACEBOOK_PAGE_ID', 'FB_PAGE_ID',
    'INSTAGRAM_ACCESS_TOKEN', 'INSTAGRAM_USER_ID', 'IG_BUSINESS_ACCOUNT_ID', 'IG_ACCOUNT_ID',
    'PINTEREST_CLIENT_ID', 'PINTEREST_CLIENT_SECRET', 'PINTEREST_DEFAULT_BOARD_ID',
    'PINTEREST_REDIRECT_URI', 'DEVIANTART_CLIENT_ID', 'DEVIANTART_CLIENT_SECRET',
    'DEVIANTART_REDIRECT_URI',
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
        # Alias V2 → V3
        if src.get('FB_PAGE_TOKEN') and not dst.get('FACEBOOK_PAGE_ACCESS_TOKEN'):
            dst['FACEBOOK_PAGE_ACCESS_TOKEN'] = src['FB_PAGE_TOKEN']
        if src.get('FB_PAGE_ID') and not dst.get('FACEBOOK_PAGE_ID'):
            dst['FACEBOOK_PAGE_ID'] = src['FB_PAGE_ID']
        if src.get('IG_BUSINESS_ACCOUNT_ID') and not dst.get('INSTAGRAM_USER_ID'):
            dst['INSTAGRAM_USER_ID'] = src['IG_BUSINESS_ACCOUNT_ID']

    with open(DST, 'w', encoding='utf-8') as f:
        for k, v in dst.items():
            f.write(f'{k}={v}\n')
    print('Social keys merged:', sum(1 for k in KEYS if dst.get(k)), 'vars present')


if __name__ == '__main__':
    main()
