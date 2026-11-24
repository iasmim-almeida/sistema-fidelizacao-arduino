from functools import wraps
from flask import jsonify, request, redirect, url_for
from flask_login import current_user

# Papel administrativo único da loja: Vendedora (Admin)
ROLE_VENDEDORA = "vendedora"

# Aliases de retrocompatibilidade
ROLE_ADMIN = "vendedora"
ROLE_PROPRIETARIO = "vendedora"
ROLE_GERENTE = "vendedora"
ROLE_VENDEDOR = "vendedora"

ROLES_VALIDOS = (ROLE_VENDEDORA,)

# Hierarquia unificada (Vendedora com perfil de administração integral)
HIERARQUIA_CARGOS = {
    ROLE_VENDEDORA: 30,
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

    "recompensas.visualizar": "Permissão para visualizar catálogo de recompensas",
    "recompensas.criar": "Permissão para cadastrar novas recompensas",
    "recompensas.editar": "Permissão para editar e alterar estoque de recompensas",
    "recompensas.desativar": "Permissão para pausar/reativar recompensas",

    "resgates.validar": "Permissão para validar e entregar resgates",
    "relatorios.visualizar": "Permissão para visualizar indicadores de fidelização",
    "configuracoes.editar": "Permissão para alterar configurações do sistema",
}

# Matriz de permissões: a Vendedora (Admin) possui acesso integral ao sistema
MATRIZ_PERMISSOES = {
    ROLE_VENDEDORA: set(PERMISSOES.keys()),
}


def normalizar_cargo(cargo_ou_nivel: str | None) -> str:
    """Mapeia aliases administrativos para o papel único Vendedora."""
    if not cargo_ou_nivel:
        return ROLE_VENDEDORA
    valor = str(cargo_ou_nivel).strip().lower()
    if valor in ("vendedora", "vendedor", "admin", "proprietario", "proprietaria", "proprietária", "gerente", "gestor"):
        return ROLE_VENDEDORA
    if valor == "cliente":
        return "cliente"
    return valor


def usuario_tem_permissao(usuario, permissao: str) -> bool:
    """Verifica se o usuário possui a permissão requerida."""
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False

    # Apenas usuários internos (vendedoras) possuem permissões administrativas
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
