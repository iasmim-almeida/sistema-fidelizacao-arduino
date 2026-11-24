# Frontend

Interface server-rendered com Jinja2, Bootstrap e JavaScript `fetch()`.

## Perfis

- Vendedora/Admin: dashboard, clientes, pontuação, recompensas, resgate, relatórios e senha.
- Cliente: saldo, extrato, recompensas, perfil e senha.

Não existem telas de equipe nem auditoria operacional. Compras não possuem campos financeiros.

## Assets offline

Bootstrap 5.3.2, Bootstrap Icons 1.11.1, Font Awesome 6.5.1 e Chart.js 4.4.7 estão em `frontend/static/vendor`. As licenças correspondentes estão em `frontend/static/vendor/licenses`.

Os templates não dependem de CDN para funcionamento. Scripts e estilos inline foram preservados para evitar uma refatoração ampla antes da banca.

## API e CSRF

Chamadas mutáveis por sessão enviam `X-CSRFToken`. A tela de pontuação também envia `X-Idempotency-Key` para impedir cliques repetidos.
