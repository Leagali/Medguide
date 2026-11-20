import { normalize } from './format'

// O catálogo da CONITEC não informa a especialidade de cada PCDT. Esta
// classificação provisória usa palavras-chave do título; o backend deve
// assumi-la quando existir um cadastro de especialidades revisado.

export type Specialty = { id: string; name: string }

export const SPECIALTIES: Specialty[] = [
  { id: 'cardiologia', name: 'Cardiologia' },
  { id: 'clinica-medica', name: 'Clínica Médica' },
  { id: 'dermatologia', name: 'Dermatologia' },
  { id: 'emergencia', name: 'Emergência e Toxicologia' },
  { id: 'endocrinologia', name: 'Endocrinologia' },
  { id: 'gastroenterologia', name: 'Gastroenterologia e Hepatologia' },
  { id: 'genetica', name: 'Genética e Doenças Raras' },
  { id: 'ginecologia', name: 'Ginecologia e Obstetrícia' },
  { id: 'hematologia', name: 'Hematologia' },
  { id: 'imunologia', name: 'Alergia e Imunologia' },
  { id: 'infectologia', name: 'Infectologia' },
  { id: 'nefrologia', name: 'Nefrologia' },
  { id: 'neurologia', name: 'Neurologia' },
  { id: 'oftalmologia', name: 'Oftalmologia' },
  { id: 'oncologia', name: 'Oncologia' },
  { id: 'pediatria', name: 'Pediatria' },
  { id: 'pneumologia', name: 'Pneumologia' },
  { id: 'psiquiatria', name: 'Psiquiatria' },
  { id: 'reumatologia', name: 'Reumatologia' },
  { id: 'transplantes', name: 'Transplantes' },
  { id: 'urologia', name: 'Urologia' },
]

const BY_ID = new Map(SPECIALTIES.map((specialty) => [specialty.id, specialty]))

export function specialtyName(id: string) {
  return BY_ID.get(id)?.name ?? id
}

// Cada regra recebe o título sem acentos e em minúsculas.
const RULES: [RegExp, string[]][] = [
  [/acidente vascular cerebral|\bavc\b/, ['neurologia', 'emergencia']],
  [/escorpion|ofidic/, ['emergencia']],
  [/acromegalia|hormonio do crescimento|hipopituitarismo|diabete|insipido|hiperprolactinemia|hipoparatireoidismo|insuficiencia adrenal|hiperplasia adrenal|puberdade precoce|tireoide|tireoid|osteoporose|raquitismo|osteomalacia|doenca de paget|obesidade|sindrome de turner|dislipidemia/, ['endocrinologia']],
  [/adenocarcinoma|carcinoma|cancer|melanoma|neoplasia|tumor|linfoma|leucemia|mieloma|mielodisplasica/, ['oncologia']],
  [/linfoma|leucemia|mieloma|mielodisplasica|anemia|falciforme|hemoglobinuria|trombocitopenia|falencia medular|sobrecarga de ferro|tromboembolismo|porfiria/, ['hematologia']],
  [/prostata|renal de celulas|incontinencia urinaria/, ['urologia']],
  [/colon e reto|estomago|esofago|estroma gastrointestinal|colangite|hepatite|doenca celiaca|crohn|retocolite|pancreatica|transplante hepatico|doenca de wilson/, ['gastroenterologia']],
  [/transtirretina|biotinidase|fabry|gaucher|pompe|fenilcetonuria|homocistinuria|mucopolissacaridose|lipofuscinose|osteogenese|atrofia muscular espinhal|ictioses|fibrose cistica|hipotireoidismo congenito|linfangioleiomiomatose|wilson|porfiria|angioedema/, ['genetica']],
  [/angioedema|imunodeficiencia/, ['imunologia']],
  [/artrite|lupus|esclerose sistemica|espondilite|miopatias inflamatorias|vasculite|uveites|osteoporose|doenca de paget|osteogenese/, ['reumatologia']],
  [/juvenil|infantil|criancas|pediatria|congenit|biotinidase|fenilcetonuria|mucopolissacaridose|atrofia muscular espinhal|lipofuscinose|puberdade precoce|transtorno do espectro do autismo|deficit de atencao|sindrome de turner|osteogenese/, ['pediatria']],
  [/\basma\b|pulmonar|fibrose cistica|tabagismo|linfangioleiomiomatose/, ['pneumologia']],
  [/hipertensao arterial|insuficiencia cardiaca|transplante cardiaco|cardiovascular|hipertensao pulmonar|chagas|transtirretina/, ['cardiologia']],
  [/dermatite|psoriase|hidradenite|ictioses|hemangioma|melanoma|hanseniase/, ['dermatologia']],
  [/hiv|sexualmente transmissiveis|\bist\b|hepatite b|hepatite c|hepatites virais|hanseniase|brucelose|chagas|sifilis/, ['infectologia']],
  [/doenca renal|nefrotica|transplante renal|renal de celulas/, ['nefrologia']],
  [/alzheimer|parkinson|epilepsia|esclerose lateral|esclerose multipla|distonia|espasticidade|miastenia|guillain|atrofia muscular|lipofuscinose|dor cronica/, ['neurologia']],
  [/macular|glaucoma|retinopatia|uveites/, ['oftalmologia']],
  [/esquizofrenia|esquizoafetivo|bipolar|deficit de atencao|autismo|tabagismo/, ['psiquiatria']],
  [/mama|ovario|endometriose|\bleiomioma|ovarios policisticos|gestantes|transmissao vertical/, ['ginecologia']],
  [/transplante/, ['transplantes']],
  [/hipertensao arterial|dislipidemia|obesidade|dor cronica|tabagismo|diabete melito tipo 2|anemia por deficiencia de ferro/, ['clinica-medica']],
]

export function classifyGuideline(title: string): string[] {
  const text = normalize(title)
  const found = new Set<string>()
  for (const [pattern, ids] of RULES) {
    if (pattern.test(text)) ids.forEach((id) => found.add(id))
  }
  if (found.size === 0) found.add('clinica-medica')
  return SPECIALTIES.filter((specialty) => found.has(specialty.id)).map((specialty) => specialty.id)
}
