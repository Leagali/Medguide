# Interface exclusiva para o vídeo — CONITEC

Esta pasta contém uma demonstração visual descartável, na branch `demo/video-conitec`.
Não representa o frontend final do MedGuide. Os arquivos existentes da aplicação,
dependências e Compose foram preservados. Não há dados fictícios nem animação de
progresso simulada.

## Abrir no Ubuntu/WSL

Com Docker/Compose disponível, dentro da pasta do projeto:

```bash
bash demo/conitec/run.sh
```

O comando prepara `.env` a partir do exemplo apenas se ele não existir, inicia os
serviços existentes e abre um container separado para a demonstração. Aguarde a API
do acervo inicializar; a página tenta se reconectar automaticamente.

Abra **http://127.0.0.1:8001** no navegador do Windows. Mantenha o terminal aberto.
O código da demonstração é montado somente para leitura em `/demo`; nenhum serviço
foi adicionado ao `compose.yaml`.

Se já houver uma instância, pare-a no terminal onde foi iniciada ou use
`docker stop medguide-video-demo` antes de iniciar novamente. Não execute dois
demonstradores na mesma porta.

O token administrativo é lido pelo servidor, do ambiente já configurado no Compose.
Não é necessário digitá-lo na página. Se o `.env` antigo não tiver
`MEDGUIDE_ADMIN_TOKEN`, configure-o antes de iniciar o demonstrador e recrie os
serviços com `docker compose up -d`.

## Roteiro sugerido para a gravação

1. Mostre o aviso **DEMONSTRAÇÃO PARA O VÍDEO**, o resumo do acervo e a origem CONITEC.
2. Clique em **Verificar CONITEC**. A solicitação usa a API real e o processamento
   ocorre nos workers existentes. Se nenhum documento estiver elegível, o resultado
   pode ser “0 novos jobs”. Fonte desabilitada precisa ser habilitada pela CLI.
3. Selecione uma diretriz, use a busca e avance para uma página interna, como a 6.
4. Abra **PDF original** e compare o mesmo trecho. O PDF é o vinculado à versão
   selecionada, não simplesmente o último arquivo baixado daquela diretriz.
5. Mostre a versão observada, data, fonte e **Baixar texto**. Se houver uma única
   versão, isso é esperado: o coletor ainda não observou outro conteúdo.
6. Para mostrar uma extração nova, clique em **Extrair um PDF agora**. O ensaio usa
   o documento principal da diretriz selecionada, consultando o catálogo oficial.
7. Acompanhe os eventos reportados pelo serviço e clique em **Ver texto extraído**.
   O leitor passa a exibir o selo **ENSAIO TEMPORÁRIO**. Use **Voltar ao acervo**
   para retornar aos dados persistentes.

O link **Como funciona** explica a sequência em linguagem de apresentação. Amplie a
fonte do leitor com A+ para facilitar a gravação. A interface funciona sem CDN,
fontes remotas ou instalação npm adicional.

## O que é real e onde fica

| Área | Origem | Efeito |
|---|---|---|
| Resumo e lista | API existente, apenas CONITEC | Consultas paginadas, atualizadas a cada 5 s enquanto a aba está visível. |
| Verificar CONITEC | `POST /api/sources/{id}/discover` | Pode criar um run e jobs reais, preservando as regras atuais. |
| Texto e versões | API administrativa | Leitura do conteúdo persistido. |
| Relação versão/PDF | `SELECT` em `version_artifacts` e API RAW | Consulta de leitura para evitar misturar originais de versões diferentes. |
| Extrair um PDF | Scraper e `IngestionService` existentes | Um documento principal, SQLite e RAW temporários; sem filas e sem gravar no PostgreSQL. |

As contagens de jobs para conferência são históricas; podem incluir uma tentativa
antiga com falha mesmo quando outra tentativa concluiu. O filtro de revisão da lista
considera somente o último job de cada diretriz. O total “com texto” conta diretrizes
com versão corrente, não o número de todas as versões históricas.

O ensaio é limitado a uma execução por vez, seis por sessão e três minutos por
execução. Os eventos são emitidos durante chamadas reais do pipeline, sem porcentagem
de páginas supostamente processadas. Pode aparecer mais de um evento de persistência:
originais e resultado final são salvos em momentos diferentes.

PDF, texto e banco temporários ficam em um diretório `medguide-video-*` em `/tmp`
do container e são removidos ao encerrar o demonstrador. Reiniciar a página não
transforma o ensaio em uma coleta permanente. Se a referência principal não for PDF,
o ensaio mostra a falha em vez de apresentar um resultado falso.

Ao iniciar o acervo, o Beat pode executar fontes vencidas normalmente. O demonstrador
nunca limpa dados, modifica intervalos, habilita fontes ou cria versões artificiais.
OCR, resumo por IA e um histórico anterior às coletas observadas não fazem parte
desta demonstração.

## Encerrar

No terminal da demonstração, pressione Ctrl+C. Para encerrar também os serviços do
acervo, use `docker compose down`; os volumes persistentes são preservados.

## Validação local do adaptador

Usando o ambiente de desenvolvimento do projeto:

```bash
uv run python -m pytest demo/conitec/test_demo.py
```

Os testes usam uma API HTTP controlada e vínculos de versão em memória. Nenhuma
consulta do teste usa o banco de coletas nem acessa a CONITEC. O teste real limitado
e a inspeção no navegador devem ser distinguidos desses testes de contrato.

### Conferência desta implementação — 24/10/2026

- Cinco testes do adaptador aprovados; Ruff e verificação de sintaxe JavaScript aprovados.
- Navegador Edge: busca, seleção de diretriz, leitura da página 6, texto completo,
  download de texto igual ao banco e PDF conferido pelo SHA-256 do artefato.
- Descoberta solicitada pela página: 132 itens, zero novos jobs nessa execução.
- Ensaio temporário solicitado pela página: Asma, 57 páginas e 167.126 caracteres;
  reexecução ignorada e resultado exibido com identificação de ambiente temporário.
- Layout conferido em desktop e celular, sem rolagem horizontal ou erros JavaScript.

Esses números são resultados da execução, não conteúdo fixo da interface. Capturas
e relatório locais: `test-results/demo-ui/`, ignorado pelo Git. A suíte pode emitir
o aviso já existente de depreciação do TestClient/Starlette; os testes passam.
