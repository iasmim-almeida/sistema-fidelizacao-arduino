# Diretrizes permanentes para agentes

Estas diretrizes se aplicam a todo o repositório e devem ser observadas em conjunto com as instruções específicas fornecidas pelo usuário em cada tarefa.

## Operações permitidas

- Leitura, criação e edição de código.
- Refatoração e correção de bugs.
- Execução de comandos e testes isolados.
- Gerenciamento de dependências.
- Criação de branches e commits.
- Push e Pull Requests somente em branches comprovadamente desvinculadas de qualquer deploy.
- Criação e atualização de documentações.

## Operações que exigem aprovação explícita e individual do usuário

- Qualquer deploy ou rollback.
- Qualquer push ou merge que possa desencadear deploy.
- Alterações na infraestrutura de produção.
- Alterações no Render e no Neon.
- Migrações em bancos persistentes.
- Operações destrutivas no Git.
- Alterações nas configurações de CI/CD relacionadas ao deploy.

Uma aprovação vale apenas para a operação específica apresentada ao usuário. Não presumir aprovação por contexto, por aprovações anteriores ou por autorização concedida a outra operação.

## Regras de segurança operacional

- Na dúvida sobre um possível gatilho de deploy, interromper a operação e solicitar aprovação antes de executá-la.
- Antes de qualquer push ou abertura/atualização de Pull Request, comprovar que a branch envolvida não está ligada a auto-deploy, Blueprint Auto Sync, deploy previews, deploy hooks ou qualquer outro mecanismo de implantação.
- Tratar alterações em `render.yaml`, workflows de deploy, configurações do Render, configurações do Neon e comandos de migração persistente como sensíveis a deploy.
- Preservar todas as alterações locais existentes e não sobrescrever, descartar, limpar, restaurar ou incluir em commits mudanças do usuário sem solicitação explícita.
- Não executar deploy, rollback, push, merge ou migração persistente como forma de teste ou validação.

## Requisitos definitivos do IT Clube

- O banco operacional oficial é PostgreSQL hospedado na Neon. SQLite pode ser usado somente em testes unitários isolados e descartáveis.
- Os perfis do produto são Administrador, representado na interface pela vendedora, e Cliente.
- Não existe gestão de funcionários ou equipes. Não restaurar menus, templates, rotas, permissões, testes ou documentação desse módulo.
- O sistema é de fidelização, não um PDV financeiro. Uma compra válida corresponde a exatamente um ponto e não armazena valor monetário da compra.
- Valores de benefícios das recompensas, custo em pontos, estoque e validade permanecem parte das regras de resgate.
- O modelo de dados consolidado possui três entidades principais: `usuario`, `produto` e `historico`.
- Não existe módulo de auditoria operacional. Preservar o histórico transacional, incluindo COMPRA, RESGATE, AJUSTE_POSITIVO, AJUSTE_NEGATIVO, origem, saldos e motivos.
- Frequência de Recompra é a quantidade de compras do período dividida pela quantidade de clientes ativos. Nunca contar resgates, ajustes ou administradores como compras ou clientes.
- A criação do primeiro administrador deve falhar de forma fechada em produção quando o token de setup não estiver configurado.
- Segredos e credenciais de dispositivos não podem ser versionados. A integração IoT deve prever TLS, provisionamento externo e proteção contra duplicidade/replay.

## Validação e migrações

- Validar migrações e concorrência PostgreSQL apenas em instância local ou efêmera com dados fictícios.
- Nunca usar credenciais, dados ou a instância Neon operacional para testes.
- Migrações destrutivas exigem backup, validação prévia e aprovação individual antes de execução em banco persistente.
- Não declarar reversível uma migração cujo downgrade apenas recrie a estrutura sem recuperar os dados removidos.
- Testes devem sanitizar variáveis externas, usar dados fictícios e evitar efeitos fora do ambiente descartável.
- Não reduzir asserções nem desabilitar testes para obter resultado positivo.
