"""
Diagnóstico pontual (não faz parte do pipeline normal): descobre se o
IfDataCadastro do Bacen tem um campo de segmentação prudencial (S1-S5) e
lista candidatos a bancos-alvo adicionais pra ampliar a comparação de
Cartão de Crédito PF (pedido: "mais concorrentes, separando por S1/S2/S3").

Uso: python scripts/_diag_segmento.py
Roda só via workflow manual (.github/workflows/_diag.yml) - não é
agendado, e o script/workflow devem ser removidos depois de extrair a
informação (não é parte do pipeline de produção).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from bacen_cartao_pipeline import _ifdata_get, get_quarters, RELATORIO_CARTAO_PF

ANOMES = get_quarters(2026)[-1] if get_quarters(2026) else 202603
print(f"[diag] usando AnoMes={ANOMES}")

registros = _ifdata_get("IfDataCadastro", params={"AnoMes": ANOMES})
cadastro = pd.DataFrame(registros)
print(f"[diag] cadastro: {len(cadastro)} linhas")
print(f"[diag] colunas disponiveis: {sorted(cadastro.columns.tolist())}")

candidatos_campo = [c for c in cadastro.columns if "segmento" in c.lower() or c.lower() in ("s1", "sfn")]
print(f"[diag] campos candidatos a segmentação: {candidatos_campo}")

for campo in candidatos_campo:
    print(f"[diag] valores unicos de '{campo}': {sorted(cadastro[campo].dropna().unique().tolist(), key=str)}")

# Bancos candidatos a ampliar a comparação de cartão (emissores PF conhecidos,
# além dos já rastreados em BANCOS_ALVO) - nomes aproximados pra buscar no
# cadastro bruto (busca solta, sem fronteira de palavra, só pra achar o nome
# oficial exato antes de configurar termos de verdade).
candidatos_bancos = [
    "BANCO DO BRASIL", "CAIXA ECONOMICA", "SAFRA", "BANRISUL",
    "ORIGINAL", "AGIBANK", "NEON", "WILL BANK", "DIGIO",
    "MERCADO PAGO", "PICPAY", "XP", "MODAL", "DAYCOVAL", "ABC BRASIL",
    "SOFISA", "PINE", "BMG", "CETELEM", "CREFISA",
]
nomes_cadastro = cadastro["NomeInstituicao"].dropna().astype(str)
print("[diag] === candidatos encontrados no cadastro (nome oficial + segmento se houver) ===")
for termo in candidatos_bancos:
    achados = nomes_cadastro[nomes_cadastro.str.upper().str.contains(termo, na=False)].unique().tolist()
    if not achados:
        print(f"[diag]   '{termo}': (nao encontrado)")
        continue
    for nome in achados:
        linha = cadastro[cadastro["NomeInstituicao"] == nome].iloc[0]
        extras = {c: linha.get(c) for c in candidatos_campo}
        cod = linha.get("CodInst")
        cod_cong = linha.get("CodConglomeradoPrudencial")
        print(f"[diag]   '{termo}' -> {nome!r} | CodInst={cod} CodConglomeradoPrudencial={cod_cong} {extras}")

# Cross-check: desses candidatos achados, quais tem "Cartão de Crédito" no
# relatório de valores desse trimestre (pra nao sugerir banco que nao emite
# cartao ou nao reporta essa modalidade)?
print("[diag] === cross-check com IfDataValores (tem Cartao de Credito nesse trimestre?) ===")
tipo_inst = 1 if ANOMES >= 202503 else 2
registros_valores = _ifdata_get(
    "IfDataValores",
    params={"AnoMes": ANOMES, "TipoInstituicao": tipo_inst, "Relatorio": RELATORIO_CARTAO_PF},
)
valores = pd.DataFrame(registros_valores)
if not valores.empty and "CodInst" in valores.columns:
    codigos_com_cartao = set(valores.loc[valores.get("Grupo", "").astype(str).str.contains("Cart", na=False), "CodInst"].astype(str).unique())
    print(f"[diag] {len(codigos_com_cartao)} CodInst distintos com Grupo contendo 'Cart' nesse relatorio/trimestre")
    for termo in candidatos_bancos:
        achados = nomes_cadastro[nomes_cadastro.str.upper().str.contains(termo, na=False)].unique().tolist()
        for nome in achados:
            linha = cadastro[cadastro["NomeInstituicao"] == nome].iloc[0]
            cod = str(linha.get("CodInst"))
            tem_cartao = cod in codigos_com_cartao
            print(f"[diag]   {nome!r} (CodInst={cod}): tem_cartao_credito={tem_cartao}")
else:
    print("[diag] IfDataValores vazio ou sem campo CodInst pra esse relatorio/trimestre")
