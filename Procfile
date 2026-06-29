release: cd artworks_site && python migrate.py
web: cd artworks_site && gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --access-logfile -
