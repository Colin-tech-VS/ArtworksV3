Artworks Marketplace (local)

Quickstart

1. Create a virtualenv and install dependencies:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Initialize DB and seed sample data:

```powershell
python seed.py
```

3. Run the app:

```powershell
python run.py
```

By default the app runs locally on http://127.0.0.1:5000
