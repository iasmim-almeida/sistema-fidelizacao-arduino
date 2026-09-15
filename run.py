import os
import sys

# Insere backend no sys.path para importação de app
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app

env = os.getenv("FLASK_ENV", "production").lower()
app = create_app(env)

if __name__ == "__main__":
    is_development = (env == "development")
    # Mitigação VULN-05: debug=True ativado apenas em ambiente de desenvolvimento isolado
    app.run(
        host="127.0.0.1" if is_development else os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 5000)),
        debug=is_development
    )
