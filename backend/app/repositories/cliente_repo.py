from app.extensions import db
from app.models.cliente import Cliente


class ClienteRepository:
    @staticmethod
    def get_by_id(id_cliente: int) -> Cliente | None:
        return db.session.get(Cliente, id_cliente)

    @staticmethod
    def get_by_telefone(telefone: str) -> Cliente | None:
        return Cliente.query.filter_by(telefone=telefone).first()

    @staticmethod
    def get_by_email(email: str) -> Cliente | None:
        if not email:
            return None
        return Cliente.query.filter_by(email=email.strip().lower()).first()

    @staticmethod
    def create(cliente: Cliente) -> Cliente:
        db.session.add(cliente)
        db.session.flush()
        return cliente
