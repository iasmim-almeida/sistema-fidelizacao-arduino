import os
from app import create_app
from app.extensions import db

env = os.getenv("FLASK_ENV", "production").lower()
app = create_app(env)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    is_development = (env == "development")
    # Mitigação VULN-05: debug=True ativado apenas em ambiente de desenvolvimento isolado
    app.run(
        host="127.0.0.1" if is_development else os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 5000)),
        debug=is_development
    )
