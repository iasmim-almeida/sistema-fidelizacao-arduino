# Camada Frontend — IT Clube

Este diretório contém os componentes visuais, templates Jinja2 e arquivos estáticos (CSS/JS) da aplicação **IT Clube**.

---

## 1. Estrutura de Diretórios

```
frontend/
├── static/
│   ├── css/
│   │   └── style.css            # Folha de estilo global e identidade visual
│   ├── js/                      # Scripts reutilizáveis de interface
│   └── assets/                  # Ícones, logotipos e ilustrações
└── templates/
    ├── base_clientes.html       # Layout base do Portal do Cliente
    ├── base_vendedora.html      # Layout base do Painel da Loja (PDV / Admin)
    ├── login.html               # Tela unificada de login com abas (Vendedora / Cliente)
    ├── cadastro.html            # Cadastro público de novos clientes
    ├── clientes/                # Visões exclusivas do cliente autenticado
    │   ├── bemvindo.html        # Dashboard inicial do cliente com saldo
    │   ├── meuspontos.html      # Extrato detalhado de pontuação
    │   ├── recompensas.html     # Vitrine de prêmios (disponíveis vs faltantes)
    │   ├── historico.html       # Histórico de compras e resgates
    │   └── perfil.html          # Minha Conta (edição de dados cadastrais e senha)
    └── vendedora/               # Visões da equipe da loja (PDV / Gestão)
        ├── dashboard.html       # Visão geral de métricas operacionais da loja
        ├── pontos.html          # Terminal PDV de identificação e pontuação
        ├── resgate.html         # Validação e baixa física de prêmios
        ├── relatorios.html      # Métricas analíticas do programa
        ├── clientes.html        # Gestão e consulta da carteira de clientes
        ├── recompensas.html     # Cadastro e edição de recompensas
        ├── funcionarios.html    # Gestão interna de acessos e cargos
        ├── auditoria.html       # Trilha de auditoria administrativa
        └── alterar_senha.html   # Troca de senha da vendedora/gestora
```

---

## 2. Identidade Visual & Paleta de Cores

O sistema preserva a paleta de cores original e consagrada da aplicação:

| Variável CSS | Cor Hexadecimal | Aplicação Principal |
| :--- | :---: | :--- |
| `--rosa-primario` | `#d85f82` | Botões de ação primária, títulos em destaque e detalhes |
| `--rosa-escuro` | `#c43d67` | Estados de hover, cabeçalhos de cards e ênfase |
| `--sidebar-color` | `#5c3a43` | Menu lateral de navegação e textos estruturais |
| `--bg-sistema` | `#fdf8f9` | Fundo geral da aplicação e áreas de leitura |
| `--rosa-pastel` | `#f6cfd9` | Bordas suaves, divisores e cards destacados |

---

## 3. Diretrizes de Segurança na Interface

- **Proteção Anti-CSRF:** Todas as requisições `POST`, `PUT` e `DELETE` incluem o cabeçalho `X-CSRFToken` obtido da meta tag `<meta name="csrf-token" content="{{ csrf_token() }}">` ou de campos ocultos em formulários `Flask-WTF`.
- **Sanitização contra XSS:** Textos injetados dinamicamente no DOM passam pela função `escapeHtml()` ou são renderizados via Jinja2 com auto-escaping ativado.
- **Isolamento de Controles do Cliente:** No Portal do Cliente, saldos e pontos são elementos estritamente de leitura, sem inputs que permitam manipulação client-side.
- **Validação de Recompensas:** Prêmios com custo superior ao saldo do cliente são renderizados desabilitados, exibindo visualmente o cálculo de quantos pontos faltam para o resgate.
