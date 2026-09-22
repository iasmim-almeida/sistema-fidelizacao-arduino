import os
import sys

# Insere backend no sys.path para importação consistente do Flask e Gunicorn
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from run import app

if __name__ == "__main__":
    app.run()
