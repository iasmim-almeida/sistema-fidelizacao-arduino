# Arquitetura validada

```mermaid
flowchart LR
    VA[Browser da vendedora] --> F[Flask]
    CL[Browser do cliente] --> F
    ESP[ESP8266] -->|POST compra| F
    F --> BP[Blueprints]
    BP --> SV[Serviços de pontos e RBAC]
    BP --> M[Models SQLAlchemy]
    SV --> M
    M --> PG[(PostgreSQL / Neon)]
    F --> J[Jinja2 + assets locais]
```

A aplicação é um monólito Flask com Application Factory. As rotas consultam os models diretamente; não existe uma repository layer completa.

## Modelo

```mermaid
erDiagram
    USUARIO ||--o{ PRODUTO : administra
    USUARIO ||--o{ HISTORICO : possui
    PRODUTO o|--o{ HISTORICO : referencia
```

`usuario` contém os perfis ADMIN e CLIENTE. `historico.tipo_movimentacao` discrimina COMPRA, RESGATE, AJUSTE_POSITIVO, AJUSTE_NEGATIVO, ESTORNO e EXPIRACAO.

## Decisões

- Uma compra equivale a um ponto.
- Não há valor monetário em compras.
- Não há gestão de equipes.
- Não há auditoria operacional.
- O histórico transacional é preservado.
- PostgreSQL é o banco operacional; SQLite fica restrito a testes unitários.
