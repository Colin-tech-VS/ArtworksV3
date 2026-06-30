"""Promouvoir ou créer le compte admin CRM.

Usage:
  python make_admin.py                          # promote Artworks_App_Admin
  python make_admin.py mon_username
  python make_admin.py --create admin@email.fr MonMotDePasse
"""
import sys

from artworks_app import create_app, db
from artworks_app.models import User

app = create_app()

DEFAULT_USERNAME = 'Artworks_App_Admin'
DEFAULT_EMAIL = 'admin@artworksdigital.fr'


def promote(user: User) -> None:
    user.is_staff = True
    user.role = 'admin'


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a.strip()]
    create_mode = '--create' in args
    if create_mode:
        args = [a for a in args if a != '--create']

    with app.app_context():
        user = None
        password = None

        if create_mode:
            email = (args[0] if len(args) > 0 else DEFAULT_EMAIL).strip().lower()
            password = args[1] if len(args) > 1 else None
            username = (args[2] if len(args) > 2 else DEFAULT_USERNAME).strip()
            user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            if not user:
                user = User(
                    username=username,
                    email=email,
                    role='admin',
                    display_name='Artworks Admin',
                    is_staff=True,
                )
                db.session.add(user)
                print(f'Compte créé : {username}')
            else:
                promote(user)
                print(f'Compte mis à jour : {user.username}')
            if password:
                if len(password) < 6:
                    print('Mot de passe trop court (6 caractères minimum).')
                    sys.exit(1)
                user.set_password(password)
        else:
            username = (args[0] if args else DEFAULT_USERNAME).strip()
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User.query.filter_by(email=username.lower()).first()
            if not user:
                print(f'Utilisateur "{username}" introuvable. Utilisez --create pour créer le compte.')
                sys.exit(1)
            promote(user)
            if len(args) > 1 and args[1]:
                password = args[1]
                user.set_password(password)

        db.session.commit()
        print(
            f'OK — {user.username} ({user.email}) · role={user.role} · is_staff={user.is_staff}\n'
            f'Connexion : /login puis /crm'
        )
