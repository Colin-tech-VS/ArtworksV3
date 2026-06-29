"""Appels Mistral pour notes curatoriales (OpenAI-compatible API)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from flask import current_app

_log = logging.getLogger(__name__)

MISTRAL_ENDPOINT = 'https://api.mistral.ai/v1/chat/completions'


class CuratorialAIError(RuntimeError):
    pass


def _cfg(name, default=''):
    return current_app.config.get(name, default)


def chat_completions(messages, *, temperature=0.55, max_tokens=600, model=None, timeout=45,
                     tools=None, tool_choice='auto'):
    """Appel Mistral chat/completions. Retourne le texte assistant si pas d'outils, sinon la réponse API complète."""
    data = chat_completions_api(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
        timeout=timeout,
        tools=tools,
        tool_choice=tool_choice,
    )
    if tools:
        return data
    try:
        content = data['choices'][0]['message']['content']
        return (content or '').strip()
    except (KeyError, IndexError, TypeError) as e:
        raise CuratorialAIError('Réponse Mistral inattendue.') from e


def chat_completions_api(messages, *, temperature=0.55, max_tokens=600, model=None, timeout=45,
                         tools=None, tool_choice='auto'):
    api_key = _cfg('MISTRAL_API_KEY')
    if not api_key:
        raise CuratorialAIError('MISTRAL_API_KEY non configurée.')
    payload = {
        'model': model or _cfg('MISTRAL_MODEL_HEAVY') or _cfg('MISTRAL_MODEL'),
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    if tools:
        payload['tools'] = tools
        payload['tool_choice'] = tool_choice
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        MISTRAL_ENDPOINT,
        data=body,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Artworks-V3/1.0',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8'))
        return data
    except urllib.error.HTTPError as e:
        msg = e.read().decode('utf-8', errors='replace')[:300]
        if e.code == 429:
            raise CuratorialAIError('Quota Mistral atteint — réessayez dans quelques minutes.') from e
        raise CuratorialAIError(f'Mistral HTTP {e.code} : {msg}') from e
    except urllib.error.URLError as e:
        raise CuratorialAIError(f'Mistral injoignable : {e.reason}') from e
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise CuratorialAIError('Réponse Mistral inattendue.') from e


_SYSTEM = {
    'artiste': (
        'Tu es commissaire d\'exposition et critique d\'art. Tu rédiges une note '
        'curatoriale pour le catalogue d\'un·e artiste contemporain·e. '
        'Style : analytique, contextualisé, fluide — comme dans une revue de musée '
        '(Artpress, Critique d\'art). '
        'Structure implicite : (1) accroche sur la ligne plastique ou la démarche, '
        '(2) lecture du corpus d\'œuvres et des matériaux/formats, '
        '(3) références aux enjeux esthétiques ou historiques suggérés par les '
        'données, (4) ouverture sur la singularité du regard. '
        'Tu n\'inventes JAMAIS de faits, dates, expositions, prix ou références '
        'absents des données. '
        '5 à 7 phrases en français (150 à 220 mots maximum). '
        'Pas de titre, pas de listes, pas de guillemets d\'encadrement. '
        'Texte continu, voix curatoriale au présent ou passé simple.'
    ),
    'galerie': (
        'Tu es commissaire d\'exposition. Tu rédiges une note curatoriale éditoriale '
        'présentant une galerie d\'art contemporain et son programme. '
        'Style : neutre, informé, professionnel — comme une notice de catalogue '
        'd\'exposition collective. '
        'Structure : (1) identité et positionnement de la galerie, '
        '(2) ligne curatoriale et types d\'œuvres présentées, '
        '(3) cohérence du catalogue ou des séries, '
        '(4) enjeu pour le public et le marché de l\'art. '
        'Tu n\'inventes rien — uniquement les informations fournies. '
        '5 à 7 phrases en français (150 à 220 mots maximum), texte continu sans titres ni listes.'
    ),
    'collectionneur': (
        'Tu es conservateur de collections privées. Tu rédiges une note curatoriale '
        'présentant la collection d\'un collectionneur d\'art contemporain. '
        'Style : élégant, analytique, comme dans un dossier de présentation de '
        'collection privée ou une exposition prêtée. '
        'Structure : (1) profil et regard du collectionneur, '
        '(2) cohérence thématique ou formelle des pièces référencées, '
        '(3) lecture des médiums, formats et périodes, '
        '(4) singularité de l\'ensemble. '
        'Tu n\'inventes aucun fait. 5 à 7 phrases en français (150 à 220 mots maximum), texte continu.'
    ),
}


def _clip(text, n=800):
    if not text:
        return ''
    t = ' '.join(str(text).split())
    return t if len(t) <= n else t[: n - 1] + '…'


def build_curatorial_prompt(user, artworks, series_list):
    """Assemble le contexte profil + présentation + œuvres + séries."""
    role = user.role or 'collectionneur'
    name = user.display_name or user.username
    lines = [f'Profil ({role}) : {name}']

    identity = []
    if user.discipline:
        identity.append(f'Discipline / spécialité : {user.discipline}')
    if user.location:
        identity.append(f'Localisation : {user.location}')
    if user.gallery:
        identity.append(f'Galerie / studio : {user.gallery}')
    if user.email:
        identity.append(f'Contact : {user.email}')
    if identity:
        lines.append('Identité :\n' + '\n'.join(f'  • {x}' for x in identity))

    presentation = []
    if user.description:
        presentation.append(f'Description : {_clip(user.description, 600)}')
    if user.statement:
        presentation.append(f'Statement : {_clip(user.statement, 600)}')
    if user.bio:
        presentation.append(f'Biographie : {_clip(user.bio, 600)}')
    if presentation:
        lines.append('Présentation :\n' + '\n'.join(presentation))

    if series_list:
        s_lines = []
        for s in series_list[:8]:
            bits = [s.name]
            if s.year:
                bits.append(str(s.year))
            n = len(s.artworks) if hasattr(s, 'artworks') else 0
            bits.append(f'{n} œuvre{"s" if n != 1 else ""}')
            if s.description:
                bits.append(_clip(s.description, 120))
            s_lines.append('  • ' + ' — '.join(bits))
        lines.append(f'Séries ({len(series_list)}) :\n' + '\n'.join(s_lines))

    if artworks:
        a_lines = []
        for a in artworks[:12]:
            bits = [a.title or 'Sans titre']
            if a.year:
                bits.append(str(a.year))
            if a.discipline:
                bits.append(a.discipline)
            if a.medium:
                bits.append(a.medium)
            if a.dimensions:
                bits.append(a.dimensions)
            if a.format:
                bits.append(f'format {a.format}')
            if a.price:
                bits.append(f'{int(a.price)} €')
            if a.series and a.series.name:
                bits.append(f'série « {a.series.name} »')
            if a.status == 'reserve':
                bits.append('réservée')
            entry = ' — '.join(bits)
            if a.description:
                entry += f' : {_clip(a.description, 160)}'
            a_lines.append(f'  • {entry}')
        lines.append(f'Œuvres ({len(artworks)}) :\n' + '\n'.join(a_lines))
    else:
        lines.append('Œuvres : (aucune œuvre publiée pour le moment — rédigez une note '
                     'prospectique basée sur le profil et la présentation uniquement.)')

    lines.append(
        '\nConsigne : rédigez la note curatoriale finale à la 3e personne, '
        'sans mentionner « l\'artiste », « la galerie » ou « le collectionneur » '
        'de façon répétitive — préférez le nom ou des tournures variées.'
    )
    return '\n\n'.join(lines)


def generate_curatorial_note(user, artworks, series_list, lang='fr'):
    role = user.role or 'collectionneur'
    if role not in _SYSTEM:
        role = 'artiste'
    system = _SYSTEM[role]
    user_prompt = build_curatorial_prompt(user, artworks, series_list)
    return chat_completions(
        [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0.55,
        max_tokens=420,
    )
