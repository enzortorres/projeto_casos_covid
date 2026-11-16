# Dados brutos

O arquivo bruto **não é versionado**: tem ~92 MB, acima do limite recomendado de 50 MB do GitHub.

| Arquivo | Origem | Tamanho |
|---|---|---|
| `caso_full.csv.gz` | <https://data.brasil.io/dataset/covid19/caso_full.csv.gz> | 92.436.661 bytes |

## Como obter

O pipeline baixa o arquivo automaticamente quando ele não existe:

```bash
python -m src.etl            # baixa (se necessário) e processa
python -m src.etl --force    # força um novo download
```

Download manual (alternativa):

```bash
curl -L -o data/raw/caso_full.csv.gz https://data.brasil.io/dataset/covid19/caso_full.csv.gz
```

Licença dos dados: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), Brasil.IO / Secretarias Estaduais de Saúde.
Documentação da fonte: <https://brasil.io/dataset/covid19/caso_full/>.
