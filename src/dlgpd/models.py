"""Estruturas de dados compartilhadas entre os módulos."""
from dataclasses import dataclass, field

# Categorias de classificação (LGPD, Art. 5º)
PESSOAL = "Pessoal"        # dado pessoal (Art. 5º, I)
SENSIVEL = "Sensível"      # dado pessoal sensível (Art. 5º, II)
POTENCIAL = "Potencial"    # pode identificar pessoa natural, depende do contexto

# Nomes legíveis para os tipos de dado
KIND_LABELS = {
    "CPF": "CPF",
    "CNPJ": "CNPJ",
    "EMAIL": "E-mail",
    "TELEFONE": "Telefone",
    "CEP": "CEP",
    "RG": "RG",
    "PLACA": "Placa de veículo",
    "DATA_NASCIMENTO": "Data de nascimento",
    "ENDERECO": "Endereço",
    "PESSOA": "Nome de pessoa",
    "LOCAL": "Local (NER)",
    "SAUDE": "Saúde",
    "RELIGIAO": "Convicção religiosa",
    "SINDICATO": "Filiação sindical",
    "POLITICA": "Opinião política / filiação partidária",
    "ETNIA": "Origem racial ou étnica",
    "SEXUAL": "Vida sexual / orientação sexual",
    "BIOMETRICO": "Dado biométrico ou genético",
}


@dataclass(frozen=True)
class Segment:
    """Trecho de texto extraído de um arquivo, com sua localização."""
    file: str
    location: str
    text: str


@dataclass
class Finding:
    """Um achado de dado pessoal. `value` guarda o dado bruto e NUNCA vai para relatórios."""
    file: str
    location: str
    kind: str
    category: str
    value: str
    masked: str
    detector: str
    start: int = -1
    end: int = -1
    priority: int = 99

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)


@dataclass
class ScanResult:
    root: str
    files_scanned: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    skipped: list = field(default_factory=list)   # (arquivo, motivo)
    ner_enabled: bool = False
    # Nome de arquivo como aparece nos relatórios: o caminho relativo com os dados pessoais
    # encontrados no próprio nome mascarados, ou um código (ARQ-001) com pseudonimização.
    display: dict = field(default_factory=dict)

    def shown(self, rel: str) -> str:
        return self.display.get(rel, rel)
