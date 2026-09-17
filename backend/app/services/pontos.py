from datetime import datetime, timezone
from app.extensions import db
from app.models.cliente import Cliente
from app.models.historico import Historico


TIPOS_MOVIMENTACAO = (
    "COMPRA",
    "RESGATE",
    "AJUSTE_POSITIVO",
    "AJUSTE_NEGATIVO",
    "ESTORNO",
    "EXPIRACAO",
)


def registrar_movimentacao(
    cliente_id: int,
    tipo: str,
    quantidade: int,
    origem: str = "sistema",
    motivo: str | None = None,
    usuario_id: int | None = None,
    compra_id: int | None = None,
    resgate_id: int | None = None,
    recompensa_id: int | None = None,
) -> tuple[bool, Historico | None, str | None]:
    """
    Executa a alteração atômica do saldo do cliente e persiste o registro no ledger imutável.
    
    Regras:
    - O cliente deve existir e estar ativo;
    - quantidade não pode ser zero;
    - O saldo final não pode ser negativo;
    - Garante row-level lock com with_for_update();
    - Retorna (sucesso, objeto_movimentacao, mensagem_erro).
    """
    tipo_formatado = str(tipo).upper().strip()
    if tipo_formatado not in TIPOS_MOVIMENTACAO:
        return False, None, f"Tipo de movimentação inválido: '{tipo}'"

    if quantidade == 0:
        return False, None, "A quantidade de pontos para movimentação não pode ser zero."

    # Bloqueia a linha do cliente para concorrência
    cliente = Cliente.query.with_for_update().filter_by(id_usuario=cliente_id).first()
    if not cliente:
        return False, None, "Cliente não encontrado."

    if not getattr(cliente, "ativo", True):
        return False, None, "Cliente está inativo. Operação não permitida."

    saldo_anterior = int(cliente.pontos_acumulados or 0)
    novo_saldo = saldo_anterior + int(quantidade)

    if novo_saldo < 0:
        return False, None, f"Saldo insuficiente. Saldo atual: {saldo_anterior}, tentativa de debitar: {abs(quantidade)}."

    # Atualiza saldo
    cliente.pontos_acumulados = novo_saldo

    movimentacao = Historico(
        id_usuario=cliente.id_usuario,
        id_produto=recompensa_id,
        tipo_movimentacao=tipo_formatado,
        pontos=quantidade,
        saldo_anterior=saldo_anterior,
        saldo_posterior=novo_saldo,
        origem=origem,
        descricao=motivo.strip() if motivo else None,
        data_movimentacao=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(movimentacao)
    db.session.flush()

    return True, movimentacao, None
