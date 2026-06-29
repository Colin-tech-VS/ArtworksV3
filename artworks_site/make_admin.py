"""Promote a user to CRM admin (is_staff). Usage: python make_admin.py camille"""
import sys
from artworks_app import create_app, db
from artworks_app.models import User

app = create_app()

if __name__ == '__main__':
    username = (sys.argv[1] if len(sys.argv) > 1 else 'Artworks_App_Admin').strip()
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f'Utilisateur "{username}" introuvable.')
            sys.exit(1)
        user.is_staff = True
        if user.role == 'collectionneur' and username == 'Artworks_App_Admin':
            user.role = 'admin'
        db.session.commit()
        print(f'OK — {user.username} ({user.email}) a maintenant accès au CRM sur /crm')
