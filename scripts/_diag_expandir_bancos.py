"""
Diagnóstico pontual (não é pipeline de produção): busca saldo/atraso real de
cartão de crédito PF pra um conjunto ampliado de bancos (S1/S2/S3), usando
os nomes oficiais já confirmados no cadastro (ver _diag_segmento.py). Usa
get_ifdata_cartao() de verdade (já testado), só com um BANCOS_ALVO maior.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bacen_cartao_pipeline as p
import generate_data_json as g

BANCOS_NOVOS = {
    "bb":       {"termos": ["BANCO DO BRASIL S.A."], "tier": "s1"},
    "caixa":    {"termos": ["CAIXA ECONOMICA FEDERAL"], "tier": "s1"},
    "safra":    {"termos": ["BANCO SAFRA S.A.", "BANCO J. SAFRA S.A."], "tier": "s2"},
    "banrisul": {"termos": ["BANCO DO ESTADO DO RIO GRANDE DO SUL", "BANRISUL S.A."], "tier": "s2"},
    "original": {"termos": ["BANCO ORIGINAL S.A."], "tier": "s3"},
    "daycoval": {"termos": ["BANCO DAYCOVAL S.A."], "tier": "s3"},
    "abc":      {"termos": ["BANCO ABC BRASIL S.A."], "tier": "s3"},
    "agibank":  {"termos": ["BANCO AGIBANK S.A."], "tier": "s3"},
}

# monkeypatch: soma o conjunto novo ao BANCOS_ALVO real, pra reusar toda a
# lógica de matching/mapeamento de código já testada (_parece_subsidiaria,
# preferência por principal etc.) sem duplicar código.
p.BANCOS_ALVO.update(BANCOS_NOVOS)

quarters = g.quarters_ifdata_recentes(6)
print(f"[diag2] trimestres: {quarters}")
df = p.get_ifdata_cartao(quarters)
if df.empty:
    print("[diag2] get_ifdata_cartao devolveu vazio")
    sys.exit(0)

for banco_key in BANCOS_NOVOS:
    sub = df[df["NomeInstituicao"].apply(lambda n, k=banco_key: k in p.identificar_bancos_alvo(n, incluir_curtos=False))]
    if sub.empty:
        print(f"[diag2] '{banco_key}': NENHUM dado encontrado")
        continue
    nomes = sub["NomeInstituicao"].unique().tolist()
    total = sub[sub["NomeColuna"] == "Total"]
    venc = sub[sub["NomeColuna"] == "Vencido a Partir de 15 Dias"]
    print(f"[diag2] '{banco_key}' -> nomes={nomes}")
    for _, row in total.sort_values("AnoMes").iterrows():
        anomes = row["AnoMes"]
        saldo = row["Saldo"] / 1e9
        venc_row = venc[venc["AnoMes"] == anomes]
        venc_val = venc_row["Saldo"].iloc[0] / 1e9 if not venc_row.empty else None
        cod = row.get("CodInst_limpo")
        conta = row.get("Conta")
        print(f"[diag2]   {anomes}: saldo_total_bi={saldo:.4f} vencido15d_bi={venc_val} CodInst_limpo={cod} Conta={conta}")

    # Diagnóstico extra: se o valor pular entre trimestres, provavelmente é
    # porque o "Total" de trimestres diferentes veio de um CodInst_limpo
    # diferente (código individual vs código de conglomerado apontando pra
    # escopos diferentes, mesmo padrão do bug já resolvido nesse projeto
    # antes) - mostra TODOS os CodInst_limpo distintos que contribuíram pro
    # 'Total' desse banco, não só o que "ganhou" cada trimestre.
    if banco_key == "caixa" and "CodInst_limpo" in sub.columns:
        print(f"[diag2]   >>> códigos distintos que contribuíram pro Total do '{banco_key}': "
              f"{sorted(total['CodInst_limpo'].unique().tolist())}")
        # e o que CADA código reportou em CADA trimestre, mesmo o que não "ganhou"
        # (recalcula direto do df bruto retornado por get_ifdata_cartao, filtrando
        # só por CodInst_limpo em vez de por NomeInstituicao já mapeado)
        codigos = sorted(total["CodInst_limpo"].unique().tolist())
        for cod in codigos:
            linhas_cod = df[(df["CodInst_limpo"] == cod) & (df["NomeColuna"] == "Total")].sort_values("AnoMes")
            vals = [(int(r["AnoMes"]), round(r["Saldo"] / 1e9, 4)) for _, r in linhas_cod.iterrows()]
            print(f"[diag2]     CodInst_limpo={cod}: {vals}")
