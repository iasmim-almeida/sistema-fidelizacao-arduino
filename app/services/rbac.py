from functools import wraps
from flask import jsonify, request, redirect, url_for
from flask_login import current_user

# Papéis de funcionários
ROLE_PROPRIETARIO = "proprietario"
ROLE_GERENTE = "gerente"
ROLE_VENDEDOR = "vendedor"

ROLES_VALIDOS = (ROLE_PROPRIETARIO, ROLE_GERENTE, ROLE_VENDEDOR)

# Hierarquia de cargos para prevenção de privilege escalation
# Quanto maior o peso, maior a hierarquia
HIERARQUIA_CARGOS = {
    ROLE_PROPRIETARIO: 30,
    ROLE_GERENTE: 20,
    ROLE_VENDEDOR: 10,
}

# Permissões do sistema
PERMISSOES = {
    "clientes.visualizar": "Permissão para consultar clientes e histórico",
    "clientes.criar": "Permissão para cadastrar novos clientes",
    "clientes.editar": "Permissão para alterar dados de clientes",
    "clientes.desativar": "Permissão para desativar/ativar clientes",

    "pontos.visualizar": "Permissão para consultar extrato e saldo de pontos",
    "pontos.adicionar": "Permissão para adicionar pontos (compras e ajustes)",
    "pontos.remover": "Permissão para remover/estornar pontos manualmente",

    "funcionarios.visualizar": "Permissão para listar e visualizar funcionários",
    "funcionarios.criar": "Permissão para cadastrar novos funcionários",
    "funcionarios.editar": "Permissão para editar funcionários",
    "funcionarios.desativar": "Permissão para desativar/ativar funcionários",
    "funcionarios.alterar_permissao": "Permissão para alterar cargo e permissões",

    "recompensas.visualizar": "Permissão para visualizar catálogo de recompensas",
    "recompensas.criar": "Permissão para cadastrar novas recompensas",
    "recompensas.editar": "Permissão para editar e alterar estoque de recompensas",
    "recompensas.desativar": "Permissão para pausar/reativar recompensas",

    "resgates.validar": "Permissão para validar e entregar resgates",
    "relatorios.visualizar": "Permissão para visualizar relatórios e faturamento",
    "auditoria.visualizar": "Permissão para visualizar logs de auditoria administrativa",
    "configuracoes.editar": "Permissão para alterar configurações do sistema",
}

# Matriz de permissões por papel
MATRIZ_PERMISSOES = {
    ROLE_PROPRIETARIO: set(PERMISSOES.keys()),
    ROLE_GERENTE: {
        "clientes.visualizar",
        "clientes.criar",
        "clientes.editar",
        "clientes.desativar",
        "pontos.visualizar",
        "pontos.adicionar",
        "pontos.remover",
        "recompensas.visualizar",
        "recompensas.criar",
        "recompensas.editar",
        "recompensas.desativar",
        "resgates.validar",
        "relatorios.visualizar",
    },
    ROLE_VENDEDOR: {
        "clientes.visualizar",
        "clientes.criar",
        "pontos.visualizar",
        "pontos.adicionar",
        "recompensas.visualizar",
        "resgates.validar",
    },
}


def normalizar_cargo(cargo_ou_nivel: str | None) -> str:
    """Mapeia aliases legados ('gestor', 'admin') para os papéis padronizados."""
    if not cargo_ou_nivel:
        return ROLE_VENDEDOR
    valor = str(cargo_ou_nivel).strip().lower()
    if valor in ("gestor", "admin", "administrador", "proprietario", "proprietária"):
        return ROLE_PROPRIETARIO
    if valor in ("gerente", "gerencia"):
        return ROLE_GERENTE
    if valor in ("vendedor", "vendedora", "funcionario", "operador"):
        return ROLE_VENDEDOR
    return ROLE_VENDEDOR


def usuario_tem_permissao(usuario, permissao: str) -> bool:
    """Verifica se o usuário possui a permissão requerida."""
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False

    # Apenas usuários internos (funcionários/vendedoras) possuem permissões administrativas
    if not getattr(usuario, "is_vendedora", False):
        return False

    # Usuário inativo não possui permissão alguma
    if not getattr(usuario, "ativo", True):
        return False

    cargo = normalizar_cargo(getattr(usuario, "cargo", None) or getattr(usuario, "nivel_acesso", None))
    permissoes_do_cargo = MATRIZ_PERMISSOES.get(cargo, set())
    return permissao in permissoes_do_cargo


def permissao_requerida(permissao: str):
    """Decorator para proteção estrita de endpoints no backend via RBAC."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                    return jsonify({"erro": "Não autenticado"}), 401
                return redirect(url_for("main.index"))

            if not getattr(current_user, "is_vendedora", False):
                if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                    return jsonify({"erro": "Acesso negado. Requer perfil administrativo."}), 403
                return redirect(url_for("main.bemvindo"))

            if not getattr(current_user, "ativo", True):
                if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                    return jsonify({"erro": "Conta inativa. Acesso negado."}), 403
                return redirect(url_for("main.index"))

            if not usuario_tem_permissao(current_user, permissao):
                if request.is_json or request.path.startswith("/api") or request.path.startswith("/auth"):
                    return jsonify({
                        "erro": f"Acesso negado. Requer permissão '{permissao}'."
                    }), 403
                return redirect(url_for("main.dashboard"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def pode_gerenciar_cargo(cargo_operador: str, cargo_alvo: str) -> bool:
    """Impede privilege escalation: operador só gerencia cargos estritamente inferiores."""
    peso_operador = HIERARQUIA_CARGOS.get(normalizar_cargo(cargo_operador), 0)
    peso_alvo = HIERARQUIA_CARGOS.get(normalizar_cargo(cargo_alvo), 0)
    # Proprietário pode gerenciar tudo inclusive outro proprietário se autorizado
    if peso_operador >= HIERARQUIA_CARGOS[ROLE_PROPRIETARIO]:
        return True
    return peso_operador > peso_alvo
