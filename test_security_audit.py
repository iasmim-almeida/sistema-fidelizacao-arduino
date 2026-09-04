"""
Suíte de Verificação Automatizada de Segurança (SAST / DAST Local)
Valida a eficácia das mitigações aplicadas no sistema FideliZa.
"""
import re
from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models import load_user


def run_tests():
    print("=" * 70)
    print("🔒 INICIANDO SUÍTE DE TESTES DE SEGURANÇA - FIDELIZA")
    print("=" * 70)

    app = create_app('development')
    client = app.test_client()

    with app.app_context():
        db.create_all()

    # -------------------------------------------------------------
    # TESTE 1: Fechamento de Endpoints da API (VULN-01 - BOLA / BFLA)
    # -------------------------------------------------------------
    print("\n[TESTE 1] Verificando controle de acesso nos endpoints /api/*...")
    r_cli = client.get('/api/clientes/')
    r_cmp = client.get('/api/compras/')
    r_res = client.get('/api/resgates/')
    r_post_cmp = client.post('/api/compras/', json={'telefone': '11999991111', 'valor': 50})

    assert r_cli.status_code == 401, f"Falha: /api/clientes/ retornou {r_cli.status_code}, esperado 401"
    assert r_cmp.status_code == 401, f"Falha: /api/compras/ retornou {r_cmp.status_code}, esperado 401"
    assert r_res.status_code == 401, f"Falha: /api/resgates/ retornou {r_res.status_code}, esperado 401"
    assert r_post_cmp.status_code == 401, f"Falha: POST /api/compras/ anônimo retornou {r_post_cmp.status_code}, esperado 401"
    print("  ✅ [PASSOU] Todos os endpoints da API REST rejeitam acessos não autenticados (401 Unauthorized).")

    # -------------------------------------------------------------
    # TESTE 2: Autenticação de Dispositivo IoT ESP8266 (VULN-03)
    # -------------------------------------------------------------
    print("\n[TESTE 2] Verificando canal autenticado do ESP8266...")
    r_iot = client.post(
        '/api/compras/',
        json={'telefone': '11999991111', 'valor': 25.00},
        headers={'X-Device-Key': 'fideliza-iot-key-padrao'}
    )
    assert r_iot.status_code == 201, f"Falha: ESP8266 com chave válida retornou {r_iot.status_code}, esperado 201"
    
    # Teste com chave inválida
    r_iot_fake = client.post(
        '/api/compras/',
        json={'telefone': '11999991111', 'valor': 25.00},
        headers={'X-Device-Key': 'chave-falsa-invasor'}
    )
    assert r_iot_fake.status_code == 401, f"Falha: ESP8266 com chave falsa retornou {r_iot_fake.status_code}, esperado 401"
    print("  ✅ [PASSOU] Hardware ESP8266 autentica com chave segura pré-compartilhada (chaves inválidas são bloqueadas).")

    # -------------------------------------------------------------
    # TESTE 3: Eliminação do Backdoor de Senha "1234" (VULN-02)
    # -------------------------------------------------------------
    print("\n[TESTE 3] Verificando remoção do backdoor de senha '1234'...")
    cliente_sem_hash = Cliente(nome="Sem Hash", telefone="11900000000")
    cliente_sem_hash.senha_hash = None
    assert cliente_sem_hash.verificar_senha("1234") is False, "Falha: Backdoor '1234' ainda aceito em conta sem hash!"
    assert cliente_sem_hash.verificar_senha("") is False, "Falha: Senha vazia foi aceita!"
    print("  ✅ [PASSOU] Backdoor de senha padrão '1234' eliminado com sucesso (retorna False).")

    # -------------------------------------------------------------
    # TESTE 4: Proteção contra Escalação de Privilégios no load_user (VULN-08)
    # -------------------------------------------------------------
    print("\n[TESTE 4] Verificando deserialização estrita de sessão (load_user)...")
    with app.app_context():
        user_legado = load_user("1")
        user_correto = load_user("u_1")
        assert user_legado is None, f"Falha: ID numérico sem prefixo retornou {user_legado}, deveria ser None!"
        assert user_correto is not None, "Falha: ID válido 'u_1' não conseguiu carregar o usuário!"
    print("  ✅ [PASSOU] IDs sem prefixo 'u_' ou 'c_' são descartados, impedindo colisão e escalação vertical.")

    # -------------------------------------------------------------
    # TESTE 5: Formulário de Cadastro, Anti-CSRF e Hash Forte (VULN-07 e VULN-02)
    # -------------------------------------------------------------
    print("\n[TESTE 5] Verificando fluxo da Tela de Cadastro Segura e Anti-CSRF...")
    # 5.1 Tentativa sem token CSRF -> deve ser barrado com 400
    r_no_csrf = client.post('/auth/cadastro', data={
        'nome': 'Tentativa Sem CSRF',
        'telefone': '11911112222',
        'senha': 'SenhaSegura123',
        'confirmar_senha': 'SenhaSegura123'
    })
    assert r_no_csrf.status_code == 400, f"Falha: Cadastro sem CSRF retornou {r_no_csrf.status_code}, esperado 400"

    # 5.2 Obter formulário legítimo com CSRF token
    r_form = client.get('/auth/cadastro')
    assert r_form.status_code == 200, f"Falha ao carregar formulário: {r_form.status_code}"
    match_csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r_form.get_data(as_text=True))
    assert match_csrf, "Falha: Campo oculto de CSRF token não foi renderizado no HTML!"
    csrf_token = match_csrf.group(1)

    # 5.3 Tentativa com senha fraca "1234" -> validação do Flask-WTF deve rejeitar
    r_weak = client.post('/auth/cadastro', data={
        'csrf_token': csrf_token,
        'nome': 'Teste Senha Fraca',
        'telefone': '11911112222',
        'senha': '1234',
        'confirmar_senha': '1234'
    })
    html_weak = r_weak.get_data(as_text=True)
    assert ("insegura" in html_weak or "minimo 8 caracteres" in html_weak), "Falha: Senha '1234' não foi rejeitada pelo validador!"

    # 5.4 Cadastro legítimo com senha forte
    with app.app_context():
        Cliente.query.filter_by(telefone='11911112222').delete()
        db.session.commit()

    r_form_new = client.get('/auth/cadastro')
    csrf_token_new = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r_form_new.get_data(as_text=True)).group(1)

    r_success = client.post('/auth/cadastro', data={
        'csrf_token': csrf_token_new,
        'nome': 'Cliente Auditado',
        'telefone': '11911112222',
        'senha': 'MinhaSenhaSegura99',
        'confirmar_senha': 'MinhaSenhaSegura99'
    }, follow_redirects=False)
    assert r_success.status_code == 302, f"Falha: Cadastro válido retornou {r_success.status_code}, esperado 302 (redirect)"

    with app.app_context():
        c_salvo = Cliente.query.filter_by(telefone='11911112222').first()
        assert c_salvo is not None, "Falha: Cliente não foi persistido no banco!"
        assert c_salvo.verificar_senha('MinhaSenhaSegura99') is True, "Falha: Hash PBKDF2 incorreto!"
        assert c_salvo.verificar_senha('1234') is False, "Falha: Senha 1234 ainda funciona no cliente salvo!"
        # Limpa cliente de teste
        db.session.delete(c_salvo)
        db.session.commit()
    print("  ✅ [PASSOU] Anti-CSRF ativo, senha fraca bloqueada e cadastro persistido com hash seguro PBKDF2.")

    # -------------------------------------------------------------
    # TESTE 6: Mitigação de Enumeração de Usuários (VULN-06)
    # -------------------------------------------------------------
    print("\n[TESTE 6] Verificando mitigação de enumeração de contas em /auth/cliente/login...")
    r_enum1 = client.post('/auth/cliente/login', json={'telefone': '11999999999', 'senha': 'qualquersenhainvalida'})
    r_enum2 = client.post('/auth/cliente/login', json={'telefone': '11999991111', 'senha': 'senhaincorreta'})
    
    assert r_enum1.status_code == 401, f"Falha: Usuário inexistente retornou {r_enum1.status_code}, esperado 401"
    assert r_enum2.status_code == 401, f"Falha: Senha incorreta retornou {r_enum2.status_code}, esperado 401"
    assert r_enum1.get_json() == r_enum2.get_json(), "Falha: As respostas para telefone inexistente e senha incorreta são discrepantes!"
    print("  ✅ [PASSOU] Mensagens de erro simétricas (401), impedindo enumeração automatizada de clientes.")

    # -------------------------------------------------------------
    # TESTE 7: Configuração de Segurança em Produção (VULN-05)
    # -------------------------------------------------------------
    print("\n[TESTE 7] Verificando isolamento do modo Debug em Produção...")
    app_prod = create_app('production')
    assert app_prod.config['DEBUG'] is False, "Falha: Debug continua ativo na configuração de produção!"
    print("  ✅ [PASSOU] Ambiente de produção desabilita o depurador interativo (DEBUG=False).")

    print("\n" + "=" * 70)
    print("🏆 RESULTADO FINAL: 100% DOS TESTES DE SEGURANÇA PASSARAM!")
    print("=" * 70)


if __name__ == '__main__':
    run_tests()
