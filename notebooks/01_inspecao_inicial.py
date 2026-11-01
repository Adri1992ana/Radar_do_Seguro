
from pathlib import Path
import pandas as pd

# Localiza a pasta principal do projeto
pasta_projeto = Path(__file__).resolve().parents[1]

# Localiza a planilha original
arquivo = (
    pasta_projeto
    / "dados"
    / "original"
    / "Planilha_para_o_site_jul_2026_valores_47863d4b2f.xlsx"
)

# Confere se o arquivo existe
print("Arquivo encontrado:", arquivo.exists())

# Identifica as abas disponíveis
excel = pd.ExcelFile(arquivo)

print("\nAbas disponíveis na planilha:")
for aba in excel.sheet_names:
    print("-", aba)



# Inspeção inicial das abas
print("\n" + "=" * 50)
print("INSPEÇÃO DAS ABAS DA CNSEG")
print("=" * 50)

for aba in excel.sheet_names:

    # Lê a aba sem assumir que a primeira linha é o cabeçalho
    df = pd.read_excel(
        arquivo,
        sheet_name=aba,
        header=None
    )

    print(f"\nABA: {aba}")
    print("Quantidade de linhas:", df.shape[0])
    print("Quantidade de colunas:", df.shape[1])

    print("\nPrimeiras 8 linhas:")
    print(df.head(8).to_string(index=False, header=False))

# Inspeção das linhas que contêm os dados
abas_principais = [
    "Arrecadação",
    "Sinistros",
    "Sinistralidade"
]

for aba in abas_principais:

    df = pd.read_excel(
        arquivo,
        sheet_name=aba,
        header=None
    )

    print("\n" + "=" * 70)
    print(f"ABA: {aba}")
    print("=" * 70)

    # Mostra as primeiras 20 linhas e apenas as 6 primeiras colunas
    print(
        df.iloc[:20, :6]
        .to_string(index=True, header=False)
    )

    # Investiga a estrutura das linhas e dos cabeçalhos
for aba in ["Arrecadação", "Sinistros", "Sinistralidade"]:

    df = pd.read_excel(
        arquivo,
        sheet_name=aba,
        header=None
    )

    print("\n" + "=" * 70)
    print(f"ESTRUTURA COMPLETA: {aba}")
    print("=" * 70)

    # Mostra as quatro primeiras colunas de todas as linhas
    print("\nIdentificação dos grupos e ramos:")
    print(df.iloc[:, :4].to_string(index=True, header=False))

    # Mostra o conteúdo do cabeçalho de períodos
    print("\nCabeçalho de períodos (linha 6):")

    for indice, valor in enumerate(df.iloc[6]):
        if pd.notna(valor):
            print(f"Coluna {indice}: {valor}")

            # Verificação dos meses de 2026
for aba in ["Arrecadação", "Sinistros", "Sinistralidade"]:

    df = pd.read_excel(
        arquivo,
        sheet_name=aba,
        header=None
    )

    print("\n" + "=" * 60)
    print(f"VERIFICAÇÃO DE 2026: {aba}")
    print("=" * 60)

    # Colunas BQ a CC: meses de 2026 e total anual
    print(
        df.iloc[8:47, 67:81]
        .to_string(index=True, header=True)
    )


# Investigação específica da Sinistralidade
df_sin = pd.read_excel(
    arquivo,
    sheet_name="Sinistralidade",
    header=None
)

print("\n" + "=" * 60)
print("INVESTIGAÇÃO DA ABA SINISTRALIDADE")
print("=" * 60)

print(
    df_sin.iloc[20:38, :8]
    .to_string(index=True, header=True)
)

for aba in ["Arrecadação", "Sinistros", "Sinistralidade"]:

    df = pd.read_excel(
        arquivo,
        sheet_name=aba,
        header=None
    )

    print("\n", "=" * 50)
    print("ABA:", aba)
    print("=" * 50)

    # Colunas de janeiro a dezembro de 2026 e total
    print(df.iloc[8:47, 68:81].to_string(index=True, header=True))