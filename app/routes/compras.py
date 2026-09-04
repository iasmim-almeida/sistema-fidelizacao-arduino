import hmac
import os
import re
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from app.models.compra import Compra
from app.models.cliente import Cliente
from app.extensions import db

compras_bp = Blueprint("compras", __name__)


def verificar_autenticacao_pontuacao():
    """
    Permite pontuação apenas por:
    1. Vendedora autenticada via sessão web; OU
    2. Terminal IoT (ESP8266) com token pré-compartilhado seguro.
    """
    if current_user.is_authenticated and getattr(current_user, "is_vendedora", False):
        return True, "vendedora"

    device_key = request.headers.get("X-Device-Key")
    expected_key = os.getenv("IOT_DEVICE_KEY", "fideliza-iot-key-padrao")
    if device_key and hmac.compare_digest(device_key, expected_key):
        return True, "iot_device"

    return False, None


@compras_bp.route("/", methods=["GET"])
@login_required
def listar():
    """Mitigação VULN-01: Exige login e segrega visão de compras por perfil."""
    query = Compra.query

    if getattr(current_user, "is_cliente", False):
        query = query.filter_by(id_cliente=current_user.id_cliente)
    elif getattr(current_user, "is_vendedora", False):
        id_cliente = request.args.get("id_cliente", type=int)
        if id_cliente:
            query = query.filter_by(id_cliente=id_cliente)
    else:
        return jsonify({"erro": "Acesso nao autorizado"}), 403

    compras = query.order_by(Compra.data.desc()).all()
    return jsonify([c.to_dict() for c in compras])


@compras_bp.route("/", methods=["POST"])
def registrar():
    """Mitigação VULN-01 e VULN-03: Pontuação restrita a vendedoras ou hardware autorizado."""
    autorizado, origem = verificar_autenticacao_pontuacao()
    if not autorizado:
        return jsonify({"erro": "Acesso nao autorizado para pontuacao."}), 401

    data = request.get_json() or {}

    cliente = None
    if data.get("id_cliente"):
        cliente = Cliente.query.get(data["id_cliente"])
    elif data.get("telefone"):
        identificador = str(data["telefone"]).strip()
        tel_limpo = re.sub(r"\D", "", identificador)
        cliente = Cliente.query.filter(
            (Cliente.telefone == identificador) | (Cliente.telefone == tel_limpo)
        ).first()

    if not cliente:
        return jsonify({"erro": "Cliente nao encontrado"}), 404

    try:
        valor = Decimal(str(data.get("valor")))
    except (InvalidOperation, TypeError):
        return jsonify({"erro": "valor invalido"}), 400

    if valor <= 0:
        return jsonify({"erro": "valor deve ser maior que zero"}), 400

    if valor > Decimal("50000.00"):
        return jsonify({"erro": "valor excede o limite maximo por transacao"}), 400

    pontos_por_real = current_app.config.get("PONTOS_POR_REAL", 1)
    pontos_gerados = int(valor) * pontos_por_real

    compra = Compra(id_cliente=cliente.id_cliente, valor=valor, pontos_gerados=pontos_gerados)
    cliente.pontos_acumulados += pontos_gerados
    db.session.add(compra)
    db.session.commit()

    return jsonify({
        "status": "sucesso",
        "origem": origem,
        "compra": compra.to_dict(),
        "cliente": cliente.to_dict(),
        "saldo_atualizado": cliente.pontos_acumulados,
    }), 201
