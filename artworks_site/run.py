from artworks_app import create_app
import os
import sys

app = create_app()

if __name__ == '__main__':
    # Port can be provided as first CLI arg or via PORT env var. Default 5000.
    port = None
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            port = None
    if port is None:
        port = int(os.environ.get('PORT', 5000))

    app.run(host='127.0.0.1', port=port, debug=True)
