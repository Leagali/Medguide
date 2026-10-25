# Interface exclusiva para o vídeo — CONITEC

Esta pasta contém a demonstração visual da branch `demo/video-conitec`. A página
exibe **DEMONSTRAÇÃO PARA O VÍDEO** e não representa a interface final do MedGuide.
Os arquivos do núcleo, suas dependências e o Compose principal foram preservados.

## Abrir no Ubuntu/WSL

Dentro do projeto, com Docker e Docker Compose disponíveis:

```bash
bash demo/conitec/run.sh
```

Abra **http://127.0.0.1:8001** no navegador do Windows e mantenha o terminal aberto.
O comando cria o projeto Docker **`medguide-video-local`**, com PostgreSQL, Redis,
armazenamento de PDFs, API e workers próprios. A primeira abertura dessa sessão
começa com **zero diretrizes**. O acervo do projeto `medguide` permanece separado.

O token local da demonstração fica no servidor; não precisa ser digitado no
navegador. O Compose complementar fixa a conexão no PostgreSQL da sessão, mesmo
que o `.env` original aponte para outro banco. A API interna não publica a porta
8000; somente a interface é exposta em `127.0.0.1:8001`.

O launcher prepara `.env` a partir do exemplo somente se ele não existir. Na
primeira execução, o Docker pode precisar construir a imagem da aplicação.

### Se a versão anterior da interface estiver aberta

Encerre-a com Ctrl+C no terminal antigo. Se foi iniciada pelo launcher anterior:

```bash
docker stop medguide-video-demo
```

Esse comando para apenas o demonstrador antigo, liberando a porta 8001. Não
execute duas sessões de vídeo simultaneamente na mesma porta.

## Gravar a demonstração

1. Mostre o aviso de demonstração e a lista vazia. Explique que o coletor consulta
   uma fonte oficial e transforma os documentos em textos consultáveis.
2. Clique em **Começar coleta CONITEC**. A página chama a API existente, que
   registra a execução e publica a tarefa real na fila Celery.
3. Acompanhe o catálogo e os **jobs ativos**. Após a descoberta, as diretrizes
   aparecem na lista, ainda aguardando download. Os workers baixam os originais,
   extraem o texto e registram as versões no PostgreSQL da demonstração.
4. Quando **Com texto disponível** aumentar, selecione uma diretriz pronta. Use
   **Com texto** para encontrar os resultados já concluídos. Um documento aberto
   antes da conclusão passa a exibir o resultado automaticamente após a coleta.
5. Avance para uma página interna, por exemplo a 6. Mostre **Texto completo**,
   **Baixar texto**, a versão observada e a data da coleta.
6. Clique em **Abrir PDF original** para abrir a cópia preservada daquela versão.
7. Clique em **Ver na fonte oficial** para abrir o endereço HTTPS do documento
   publicado pela CONITEC. Antes de existir um PDF coletado, o botão pode apontar
   para a página oficial da diretriz. A barra lateral também abre o catálogo.

A descoberta pode terminar antes dos downloads: **catálogo concluído não significa
que todos os PDFs já foram extraídos**. A página acompanha esses estados separados,
consultando a API a cada 5 segundos enquanto a aba está visível.

A coleta do catálogo completo pode ultrapassar os cinco minutos do vídeo. Grave a
partida vazia e mostre os primeiros resultados prontos; se necessário, corte a
espera e informe isso durante a apresentação. Não há tempo ou porcentagem simulados.
Limites, indisponibilidade da fonte e documentos sem texto extraível podem produzir
falhas reais, exibidas para conferência. Não há OCR ou resumo por IA.

**Verificar CONITEC novamente** fica disponível quando a coleta deixa de ter jobs
ativos. Uma nova verificação respeita as regras existentes de rechecagem e
idempotência: documentos já conhecidos podem não gerar novos downloads ou versões.

## Gravar novamente começando do zero

Ctrl+C encerra os serviços dessa demonstração, preservando os volumes. Reabrir com
o mesmo nome continua a sessão existente. Para outra gravação, encerre a anterior
e escolha um nome ainda não utilizado:

```bash
bash demo/conitec/run.sh gravacao-2
```

Isso cria o projeto `medguide-video-gravacao-2`, com banco, fila e arquivos vazios,
sem apagar a sessão anterior nem o acervo principal. Não é necessário limpar tabelas
ou remover volumes. Cada nome cria dados persistentes próprios e ocupa espaço local.

## Ver os logs e os serviços

Em outro terminal, para a sessão padrão:

```bash
docker compose --project-name medguide-video-local -f compose.yaml -f demo/conitec/compose.video.yaml ps -a

docker compose --project-name medguide-video-local -f compose.yaml -f demo/conitec/compose.video.yaml logs --tail 80 worker-discovery worker-ingestion beat demo
```

Troque `medguide-video-local` pelo nome exibido pelo launcher se usar outra sessão.
O serviço `migrate` terminar com código 0 é esperado. O Beat da demonstração usa
`video_scheduler.py`: recupera publicações pendentes e novas tentativas pelo mesmo
mecanismo do núcleo, mas **não agenda a descoberta automática de fontes**. A primeira
coleta depende do clique na página. Jobs já solicitados podem continuar ao reabrir
uma sessão existente.

Para encerrar a sessão padrão por outro terminal, preservando os dados:

```bash
docker compose --project-name medguide-video-local -f compose.yaml -f demo/conitec/compose.video.yaml down
```

## Origem dos dados e limites

| Área | Implementação |
|---|---|
| Início vazio | Volumes próprios do projeto Docker `medguide-video-*`; nenhum documento é apagado ou escondido. |
| Botão de coleta | `POST /api/sources/{id}/discover`, API e workers existentes. |
| Downloads e extração | Scraper CONITEC e `IngestionService` reais, usando PostgreSQL, Redis e RAW da sessão. |
| Etapas e contagens | Estados registrados pelos jobs; sem progresso artificial. |
| Texto e versões | API administrativa existente. |
| Relação versão/PDF | `SELECT` somente de leitura em `version_artifacts`, seguido da API RAW. |
| PDF preservado | Original vinculado à versão selecionada, inclusive após reversão de conteúdo. |
| Fonte oficial | `source_url` do documento ou `catalog_url` da diretriz, em HTTPS. |

As contagens de falhas/revisões são históricas; uma tentativa antiga pode ter falhado
antes de uma nova concluir. O filtro da lista considera o último job de cada diretriz.
O total **com texto** conta diretrizes com versão corrente, não todas as versões.

O ensaio avulso de um PDF, da implementação anterior, continua disponível para quem
executar o adaptador fora do modo isolado. Seu painel fica oculto neste launcher,
pois o foco do vídeo é o job real pelas filas. Esse ensaio usa SQLite e RAW em `/tmp`
do container, limitado a uma execução por vez, seis por sessão e três minutos por
execução; não grava no PostgreSQL. Seus resultados são identificados como temporários.

## Validação do adaptador

No ambiente de desenvolvimento:

```bash
uv run python -m pytest demo/conitec/test_demo.py
```

Os testes de contrato usam uma API controlada, sem consultar CONITEC ou o banco do
acervo. Incluem início vazio sem coleta automática, acionamento explícito pela API,
agenda exclusiva de recuperação, paginação, origem local das operações e vínculo
correto entre versão e PDF. A suíte pode emitir o aviso já existente de depreciação
do TestClient/Starlette.

Os testes reais no navegador e os relatórios locais ficam em
`test-results/demo-ui/`, ignorado pelo Git.

### Conferência em 25/10/2026

- Sete testes de contrato aprovados; Ruff e sintaxe JavaScript aprovados.
- Compose resolvido com volumes próprios, conexão fixada no banco da sessão e
  porta da API interna sem publicação no host; Docker Compose 5.2.0. O complemento
  usa a marca `!reset` do Compose para remover a publicação herdada da porta 8000.
- Navegador: sessão inicialmente vazia, sem execução automática; clique na página
  iniciou descoberta real de 132 itens e criou 132 jobs.
- Diretriz selecionada durante o processamento passou a exibir texto sem recarregar
  a página: Acidentes Escorpiônicos, 50 páginas e 110.609 caracteres.
- Página 6 e texto completo conferidos; TXT igual ao texto da versão e PDF com
  SHA-256 igual ao original preservado. Link oficial igual ao endereço coletado.
- Layout desktop e celular sem rolagem horizontal ou erros JavaScript.
- Acervo principal manteve as mesmas contagens antes e depois: 132 diretrizes,
  133 versões, 133 artefatos, 133 jobs e seis execuções de catálogo.

A sessão de teste foi separada da sessão padrão. A validação conferiu os primeiros
resultados reais; não representa uma auditoria de todos os PDFs do catálogo.
