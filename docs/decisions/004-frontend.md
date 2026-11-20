# ADR 004 — Frontend da plataforma e camada provisória

Status: aceito, 19/11/2026.

O frontend React/Vite implementa a visão do produto: cadastro e login, escolha de
especialidades, feed com filtros, leitura e histórico de versões, notificações,
sugestão de fontes e administração. O backend expõe apenas ingestão, leitura e
administração por token de serviço; não há contas, especialidades, notificações
nem sugestões.

Decisões:

- **Dados reais onde existem.** Feed, diretriz, versões, observações, originais,
  fontes, coletas, jobs e métricas usam a API (`src/lib/api.ts`). O cliente percorre
  as páginas de 200 itens que a API permite.
- **Camada provisória isolada.** Contas, especialidades escolhidas, notificações e
  sugestões ficam em `src/lib/localBackend.ts`, persistidas no `localStorage`. As
  funções são assíncronas e usam os formatos de `src/lib/types.ts`, que servem de
  contrato para os endpoints futuros listados no arquivo. As senhas são guardadas
  como SHA-256 com sal só para não ficarem em texto puro; não é segurança real.
- **Token fora do navegador.** O proxy do Vite injeta `MEDGUIDE_ADMIN_TOKEN` em
  `/api`. Enquanto não houver autenticação de usuários, quem acessa o servidor de
  desenvolvimento tem poder administrativo na API; o controle de acesso da tela de
  administração é apenas visual. Por isso, não há configuração para publicar o `dist/`.
- **Especialidades por regras de título.** A CONITEC não classifica os PCDT.
  `src/lib/specialties.ts` aplica expressões regulares ao título sem acentos, e uma
  diretriz pode ter várias especialidades. As regras foram conferidas contra as 141
  diretrizes coletadas, todas com ao menos uma especialidade específica.
- **Notificações por comparação de catálogo.** O navegador guarda
  `guideline_id → current_version_id` por usuário. Uma diretriz nova ou uma troca de
  versão nas especialidades do usuário gera um aviso; a primeira extração
  (`null` → versão) não gera.
- **Aprovar uma sugestão não cria uma fonte.** A API só aceita conectores homologados
  em código (ADR 003). A aprovação registra a decisão e avisa quem sugeriu.
- **Roteamento por hash** (`#/feed`), sem dependência nova e sem configuração de servidor.

Consequências: para substituir a camada provisória, o backend precisa de usuários e
sessões, preferências de especialidade, um serviço de notificações que compare
versões no servidor e envie e-mail, e uma tabela de sugestões com revisão. A
classificação por especialidade deve passar para o backend, com revisão humana. Os
dados simulados não são compartilhados entre navegadores nem migrados.
