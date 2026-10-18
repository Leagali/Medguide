# Fixtures

`catalog.html`: casos sintéticos baseados na estrutura CONITEC, incluindo ausência
de link/data, retificação e múltiplos anexos.

`conitec_snapshot.html`: quatro linhas do catálogo oficial obtidas por GET em
17/10/2026, preservando a estrutura das células e links. Fonte:
https://www.gov.br/conitec/pt-br/assuntos/avaliacao-de-tecnologias-em-saude/protocolos-clinicos-e-diretrizes-terapeuticas/pcdt

PDFs de teste são gerados com PyMuPDF, sem conteúdo clínico real. A coleta ao vivo
é explícita em `scripts/smoke_live.py` e baixa apenas o primeiro item do catálogo.
