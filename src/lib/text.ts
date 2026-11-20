// O texto extraído vem no formato do backend (src/medguide/ingestion/text.py):
//   [main]
//   [p.1]
//   ...conteúdo da página...
// Um marcador [chave] inicia um documento; [p.N] inicia uma página.

export type TextPage = { reference: string; page: number; text: string }

export function splitPages(extracted: string): TextPage[] {
  const pages: TextPage[] = []
  let reference = 'main'
  let current: TextPage | null = null
  for (const line of extracted.split('\n')) {
    const pageMatch = /^\[p\.(\d+)\]$/.exec(line)
    const referenceMatch = !pageMatch && /^\[([\w.-]+)\]$/.exec(line)
    if (pageMatch) {
      current = { reference, page: Number(pageMatch[1]), text: '' }
      pages.push(current)
    } else if (referenceMatch) {
      reference = referenceMatch[1]
      current = null
    } else {
      if (!current) {
        current = { reference, page: 0, text: '' }
        pages.push(current)
      }
      current.text += current.text ? `\n${line}` : line
    }
  }
  return pages.filter((page) => page.text.trim())
}

/**
 * Comparação por linhas entre duas versões: lista o que só existe em uma
 * delas. Ignora diferenças de espaço e a ordem das linhas repetidas.
 */
export function compareVersions(older: string, newer: string) {
  const clean = (text: string) =>
    text
      .split('\n')
      .map((line) => line.replace(/\s+/g, ' ').trim())
      .filter((line) => line && !/^\[(p\.\d+|[\w.-]+)\]$/.test(line))
  const before = clean(older)
  const after = clean(newer)
  const beforeSet = new Set(before)
  const afterSet = new Set(after)
  return {
    added: after.filter((line) => !beforeSet.has(line)),
    removed: before.filter((line) => !afterSet.has(line)),
  }
}
