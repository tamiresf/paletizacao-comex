from datetime import datetime
from itertools import combinations, permutations
import math
import os
import re
import pandas as pd
import streamlit as st

# Importação condicional do FPDF para geração do PDF
try:
    from fpdf import FPDF
    FPDF_DISPONIVEL = True
except ImportError:
    FPDF_DISPONIVEL = False

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Paletização - MUSTAD", page_icon="📦", layout="wide"
)

# Estilização CSS personalizada
st.markdown(
    """
    <style>
    .cliente-box {
        background-color: #EBF3FA;
        border-left: 6px solid #0055B8;
        padding: 15px 20px;
        border-radius: 6px;
        margin-bottom: 20px;
    }
    .total-caixas-destaque {
        color: #0055B8;
        font-weight: bold;
        font-size: 1.25em;
        background-color: #E6F0FA;
        padding: 10px 18px;
        border-radius: 6px;
        border: 1px solid #0055B8;
        display: inline-block;
        margin-top: 10px;
        margin-bottom: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("📦 Sistema de Paletização - COMEX (12 Pallets)")
st.markdown("---")

# --- 2. BASE DE DADOS E CARREGAMENTO ---
COLUNAS_ESSENCIAIS = [
    "NUMERO DA CAIXA",
    "QUANTIDADE DE PEÇAS",
    "QUANTIDADE DE CAIXAS NO PALLET",
    "QUANTIDADE DE CAIXAS POR FILEIRA",
    "ALTURA",
]


def _fileiras_efetivas(cx_fileira, altura, capacidade):
    cx_fileira = max(int(cx_fileira), 1)
    return max(min(int(altura), max(int(capacidade) // cx_fileira, 1)), 1)


def _cpf_padrao_por_tipo(df, coluna_tipo="Ordem_Caixa"):
    return {
        int(t): int(g["QUANTIDADE DE CAIXAS POR FILEIRA"].mode().iloc[0])
        for t, g in df.groupby(coluna_tipo)
    }


@st.cache_data
def carregar_base(caminho_excel, versao=None):
    df = pd.read_excel(caminho_excel, sheet_name=0)
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=COLUNAS_ESSENCIAIS).copy()

    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["NOME DO PRODUTO"] = df["NOME DO PRODUTO"].astype(str).str.strip()

    num_caixa = pd.to_numeric(df["NUMERO DA CAIXA"], errors="coerce")
    df["NUMERO DA CAIXA"] = [
        str(int(n)) if pd.notna(n) else str(orig).strip()
        for n, orig in zip(num_caixa, df["NUMERO DA CAIXA"])
    ]

    colunas_numericas = [
        "QUANTIDADE DE PEÇAS",
        "QUANTIDADE DE CAIXAS NO PALLET",
        "QUANTIDADE DE UNIDADE DE PEÇAS NO PALLET",
        "QUANTIDADE DE CAIXAS POR FILEIRA",
        "ALTURA",
    ]

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(1).astype(int)
        else:
            df[col] = 1

    def extrair_num_caixa(val):
        try:
            return int(re.sub(r"\D", "", str(val)))
        except Exception:
            return 0

    df["Ordem_Caixa"] = df["NUMERO DA CAIXA"].apply(extrair_num_caixa)
    return df.reset_index(drop=True)


@st.cache_data
def listar_skus_descartados(caminho_excel, versao=None):
    """SKUs da planilha sem dados de caixa/altura (não entram na busca)."""
    bruto = pd.read_excel(caminho_excel, sheet_name=0)
    bruto.columns = bruto.columns.str.strip()
    ruins = bruto[bruto[COLUNAS_ESSENCIAIS].isna().any(axis=1)]
    return [f"{r['SKU']} - {r['NOME DO PRODUTO']}" for _, r in ruins.iterrows()]


caminhos_possiveis = ["COMEX.xlsx", "data/COMEX.xlsx"]
CAMINHO_EXCEL = next((c for c in caminhos_possiveis if os.path.exists(c)), None)

if not CAMINHO_EXCEL:
    st.error("⚠️ O arquivo 'COMEX.xlsx' não foi encontrado no diretório.")
    st.stop()

VERSAO_PLANILHA = os.path.getmtime(CAMINHO_EXCEL)

try:
    df_produtos = carregar_base(CAMINHO_EXCEL, VERSAO_PLANILHA)
except Exception as e:
    st.error(f"Erro ao carregar a base de dados: {e}")
    st.stop()

skus_descartados = listar_skus_descartados(CAMINHO_EXCEL, VERSAO_PLANILHA)
if skus_descartados:
    with st.expander(f"⚠️ {len(skus_descartados)} SKU(s) da planilha sem dados de caixa (não aparecem na busca)"):
        st.write("Complete NUMERO DA CAIXA, QUANTIDADE DE PEÇAS, CAIXAS NO PALLET, CAIXAS POR FILEIRA e ALTURA na planilha:")
        for linha in skus_descartados:
            st.write(f"• {linha}")

# --- 3. ESTADO DA SESSÃO ---
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

if "processado" not in st.session_state:
    st.session_state.processado = False

# --- 4. PAINEL LATERAL ---
st.sidebar.header("📋 Inserir Pedido")
opcoes_produtos = df_produtos["SKU"] + " - " + df_produtos["NOME DO PRODUTO"]
produto_selecionado = st.sidebar.selectbox("Pesquisar Produto (SKU ou Nome):", options=opcoes_produtos)

sku_sel = produto_selecionado.split(" - ")[0]
prod_info = df_produtos[df_produtos["SKU"] == sku_sel].iloc[0]

st.sidebar.info(f"""
**Informações do SKU:**  
• **Caixa Nº:** {prod_info['NUMERO DA CAIXA']}  
• **Peças / Caixa:** {prod_info['QUANTIDADE DE PEÇAS']}  
• **Caixas / Fileira:** {prod_info['QUANTIDADE DE CAIXAS POR FILEIRA']}  
• **Altura Máxima:** {prod_info['ALTURA']} fileiras  
• **Capacidade / Pallet:** {prod_info['QUANTIDADE DE CAIXAS NO PALLET']} cx
""")

qtd_solicitada = st.sidebar.number_input(
    "Qtd de Caixas Solicitada:",
    min_value=1,
    value=int(prod_info["QUANTIDADE DE CAIXAS NO PALLET"]),
    step=1,
)

if st.sidebar.button("➕ Adicionar ao Pedido"):
    existente = False
    for item in st.session_state.carrinho:
        if item["SKU"] == sku_sel:
            item["Qtd_Caixas"] += qtd_solicitada
            existente = True
            break
    if not existente:
        st.session_state.carrinho.append({
            "SKU": sku_sel,
            "Produto": prod_info["NOME DO PRODUTO"],
            "Nº Caixa": str(prod_info["NUMERO DA CAIXA"]),
            "Qtd_Caixas": qtd_solicitada,
            "Pecas_Por_Caixa": int(prod_info["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": int(prod_info["QUANTIDADE DE CAIXAS POR FILEIRA"]),
            "Quantidade_Fileiras": int(prod_info["ALTURA"]),
            "Capacidade_Pallet_Caixas": int(prod_info["QUANTIDADE DE CAIXAS NO PALLET"]),
        })
    st.session_state.processado = False
    st.sidebar.success("Item adicionado ao pedido!")

# --- 5. IDENTIFICAÇÃO DO CLIENTE E CARRINHO ---
st.markdown(
    """
<div class="cliente-box">
    <h4 style="color: #0055B8; margin: 0 0 5px 0;">👤 Identificação do Cliente</h4>
    <p style="color: #333; margin: 0; font-size: 0.9em;">Informe a Razão Social/Cliente para personalização do relatório.</p>
</div>
""",
    unsafe_allow_html=True,
)

nome_cliente_input = st.text_input("Nome do Cliente / Razão Social:", placeholder="Ex: Cliente COMEX")
st.subheader("🛒 Itens do Pedido Atual")

if st.session_state.carrinho:
    total_caixas_pedido = sum(item["Qtd_Caixas"] for item in st.session_state.carrinho)
    total_pecas_pedido = sum(item["Qtd_Caixas"] * item["Pecas_Por_Caixa"] for item in st.session_state.carrinho)

    for index in range(len(st.session_state.carrinho) - 1, -1, -1):
        item = st.session_state.carrinho[index]

        c1, c2, c3, c4, c5 = st.columns([1.5, 3.5, 1.5, 1.5, 0.8])
        c1.write(f"**SKU:** {item['SKU']}")
        c2.write(f"**Produto:** {item['Produto']}")
        c3.write(f"**Caixa Nº:** {item['Nº Caixa']}")
        c4.write(f"**Qtd:** {item['Qtd_Caixas']} cx")

        if c5.button("🗑️", key=f"rem_{index}_{item['SKU']}"):
            st.session_state.carrinho.pop(index)
            st.session_state.processado = False
            st.rerun()

    st.markdown("---")
    m1, m2, m3 = st.columns([2.5, 2.5, 2])
    m1.metric("📦 Total de Caixas no Pedido", f"{total_caixas_pedido:,} cx".replace(",", "."))
    m2.metric("🧩 Total de Peças no Pedido", f"{total_pecas_pedido:,} pçs".replace(",", "."))

    with m3:
        if st.button("🔴 Limpar Pedido", use_container_width=True):
            st.session_state.carrinho = []
            st.session_state.processado = False
            st.rerun()
else:
    st.info("Nenhum item adicionado ao pedido.")

st.markdown("---")

# --- 6. REGRA DE PALETIZAÇÃO COMEX (AGRUPAMENTO E ORDENAÇÃO DE CAIXAS) ---
ALTURA_MAXIMA_FILEIRAS = 6
EPS = 1e-9

TIPO_SEQUENCIAL = "Pallet Fechado - SKU único, sequencial"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura"
TIPO_ALTURAS_DIF = "Pallet Fechado - mesma caixa, alturas diferentes"
TIPO_MISTO = "Pallet Fechado - tipos de caixa diferentes"
TIPO_FILEIRAS_SOBRAS = "Pallet Fechado - fileiras de sobras"
TIPO_INCOMPLETO = "Pallet Incompleto - fileiras restantes"
TIPO_FINAL = "Pallet Final (caixas soltas e sobras)"


def _combo_exato(lotes, alvo):
    """Escolhe, entre lotes inteiros (cada um com 'rows' fileiras), os que somam
    exatamente `alvo` fileiras usando o MENOR número de lotes (menos SKUs = menos paradas)."""
    lotes = sorted(lotes, key=lambda l: (-l["rows"], l["tipo"], l["sku"] or ""))
    n = len(lotes)
    memo = {}

    def rec(i, resto):
        if resto == 0:
            return ()
        if i >= n or resto < 0:
            return None
        chave = (i, resto)
        if chave in memo:
            return memo[chave]
        melhor = rec(i + 1, resto)
        if lotes[i]["rows"] <= resto:
            sub = rec(i + 1, resto - lotes[i]["rows"])
            if sub is not None:
                cand = (i,) + sub
                if melhor is None or len(cand) < len(melhor):
                    melhor = cand
        memo[chave] = melhor
        return melhor

    achado = rec(0, alvo)
    return [lotes[i] for i in achado] if achado is not None else None


def _gerar_pallets(carrinho, df_produtos):
    padrao_tipo = _cpf_padrao_por_tipo(df_produtos)

    # ---------- 0. PREPARAÇÃO: cada SKU vira "fileiras completas" + "caixas soltas" ----------
    skus = {}
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]
        ordem = int(prod.get("Ordem_Caixa", 0))
        cx_fileira = max(padrao_tipo.get(ordem, int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"])), 1)
        altura = min(
            _fileiras_efetivas(cx_fileira, prod["ALTURA"], prod["QUANTIDADE DE CAIXAS NO PALLET"]),
            ALTURA_MAXIMA_FILEIRAS,
        )
        skus[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": ordem,
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": cx_fileira,
            "Altura": altura,
            "Restante": int(item["Qtd_Caixas"]),
        }

    cpf_tipo = {}
    for s in skus.values():
        cpf_tipo[s["Ordem_Caixa"]] = s["Caixas_Por_Fileira"]
    tipos = sorted(cpf_tipo)

    lotes = []        # lotes de fileiras completas (de um SKU ou "fileira mista" de sobras)
    solta_sku = {}    # caixas que não fecham fileira
    for s in sorted(skus.values(), key=lambda s: (s["Ordem_Caixa"], s["SKU"])):
        cpf = s["Caixas_Por_Fileira"]
        rows, resto = divmod(s["Restante"], cpf)
        s["Restante"] = 0
        if rows:
            lotes.append({"tipo": s["Ordem_Caixa"], "hmax": s["Altura"], "rows": rows,
                          "sku": s["SKU"], "itens": None})
        if resto:
            solta_sku[s["SKU"]] = resto

    pallets = []

    def camada_vol(c):
        return sum(q / cpf_tipo[c["tipo"]] for q in c["itens"].values())

    def criar(tipo_txt, partes, limite, final=False, obs=""):
        camadas = []
        for lote, n in partes:
            lote["rows"] -= n
            for _ in range(n):
                itens = dict(lote["itens"]) if lote["itens"] else {lote["sku"]: cpf_tipo[lote["tipo"]]}
                camadas.append({"tipo": lote["tipo"], "itens": itens, "cheia": True})
        p = {"tipo": tipo_txt, "camadas": camadas, "limite": limite, "obs": obs, "final": final}
        pallets.append(p)
        return p

    def vivos(tipo=None):
        return sorted(
            [l for l in lotes if l["rows"] > 0 and (tipo is None or l["tipo"] == tipo)],
            key=lambda l: (l["tipo"], l["sku"] is None, l["sku"] or ""),
        )

    def candidatos_altura(base):
        qtd = {}
        for l in base:
            qtd[l["hmax"]] = qtd.get(l["hmax"], 0) + l["rows"]
        return sorted(qtd, key=lambda h: (-qtd[h], h))  # maior quantidade manda; empate = menor altura

    def elegiveis(base, H, modo):
        return [l for l in base if (l["hmax"] == H if modo == "igual" else l["hmax"] >= H)]

    # ---------- 1. PALLETS FECHADOS DE UM ÚNICO SKU (sequenciais) ----------
    for l in list(lotes):
        while l["rows"] >= l["hmax"]:
            criar(TIPO_SEQUENCIAL, [(l, l["hmax"])], l["hmax"])

    # ---------- 2 e 3. MESMO TIPO DE CAIXA ----------
    def montar_fileiras_mistas(t):
        """Caixas soltas do mesmo tipo viram fileiras completas (agrupando por mesma altura)."""
        cpf = cpf_tipo[t]
        pend = [(s, q) for s, q in solta_sku.items() if skus[s]["Ordem_Caixa"] == t and q > 0]
        novas, sobras = [], []

        def consumir(fila):
            atual, cheia = {}, 0
            for sku, qtd in fila:
                while qtd > 0:
                    pega = min(cpf - cheia, qtd)
                    atual[sku] = atual.get(sku, 0) + pega
                    cheia += pega
                    qtd -= pega
                    if cheia == cpf:
                        novas.append(atual)
                        atual, cheia = {}, 0
            return list(atual.items())

        for h in sorted({skus[s]["Altura"] for s, _ in pend}, reverse=True):
            grupo = sorted([x for x in pend if skus[x[0]]["Altura"] == h], key=lambda r: (-r[1], r[0]))
            sobras.extend(consumir(grupo))
        sobras.sort(key=lambda r: (-skus[r[0]]["Altura"], -r[1], r[0]))
        resto = dict(consumir(sobras))
        for s, _ in pend:
            solta_sku.pop(s, None)
        for row in novas:
            lotes.append({"tipo": t, "hmax": min(skus[k]["Altura"] for k in row), "rows": 1,
                          "sku": None, "itens": row})
        return resto

    soltas_tipo = {}
    for t in tipos:
        # 2. mesma caixa + mesma altura: soma exata de fileiras = altura
        for h in sorted({l["hmax"] for l in vivos(t)}, reverse=True):
            while True:
                combo = _combo_exato([l for l in vivos(t) if l["hmax"] == h], h)
                if not combo:
                    break
                criar(TIPO_MESMA_ALTURA, [(l, l["rows"]) for l in combo], h)

        # 3. mesma caixa, alturas diferentes: limite = altura onde há mais caixas
        while True:
            base = vivos(t)
            feito = False
            for H in candidatos_altura(base):
                combo = _combo_exato(elegiveis(base, H, "maior"), H)
                if combo:
                    criar(TIPO_ALTURAS_DIF, [(l, l["rows"]) for l in combo], H)
                    feito = True
                    break
            if not feito:
                break

        # sobras de caixas do tipo viram fileiras completas (SKUs misturados na mesma fileira)
        resto = montar_fileiras_mistas(t)
        if resto:
            soltas_tipo[t] = resto

        # fecha pallets do mesmo tipo dividindo um SKU apenas se for necessário
        while True:
            base = vivos(t)
            feito = False
            for modo in ("igual", "maior"):
                for H in candidatos_altura(base):
                    elig = elegiveis(base, H, modo)
                    if sum(l["rows"] for l in elig) < H:
                        continue
                    ordem = sorted(elig, key=lambda l: (l["sku"] is None, -l["rows"], l["sku"] or ""))
                    falta, partes = H, []
                    for l in ordem:                       # primeiro lotes inteiros
                        if l["rows"] <= falta:
                            partes.append((l, l["rows"]))
                            falta -= l["rows"]
                    if falta:                             # divide o menor lote que cobre o que falta
                        usados_ids = {id(x) for x, _ in partes}
                        livres = [l for l in ordem if l["rows"] > falta and id(l) not in usados_ids]
                        l = min(livres, key=lambda l: (l["rows"], l["sku"] or ""))
                        partes.append((l, falta))
                    criar(TIPO_MESMA_ALTURA if modo == "igual" else TIPO_ALTURAS_DIF, partes, H)
                    feito = True
                    break
                if feito:
                    break
            if not feito:
                break

    # ---------- 4. TIPOS DE CAIXA DIFERENTES NO MESMO PALLET ----------
    def valido_apos(tomadas):
        por_tipo = {}
        for l in lotes:
            r = l["rows"] - tomadas.get(id(l), 0)
            if r > 0:
                por_tipo[l["tipo"]] = por_tipo.get(l["tipo"], 0) + r
        if not por_tipo:
            return not any(soltas_tipo.values())
        return max(por_tipo.values()) >= 2          # o que sobrar vira o último pallet (≥ 2 fileiras)

    def fechar_inteiro():
        vs = vivos()
        tps = sorted({l["tipo"] for l in vs})
        for k in range(1, len(tps) + 1):
            for sub in combinations(tps, k):
                base = [l for l in vs if l["tipo"] in sub]
                for modo in ("igual", "maior"):
                    for H in candidatos_altura(base):
                        combo = _combo_exato(elegiveis(base, H, modo), H)
                        if combo and valido_apos({id(l): l["rows"] for l in combo}):
                            if len(sub) == 1:
                                rot = TIPO_MESMA_ALTURA if modo == "igual" else TIPO_ALTURAS_DIF
                            else:
                                rot = TIPO_MISTO
                            criar(rot, [(l, l["rows"]) for l in combo], H)
                            return True
        return False

    def fechar_dividindo():
        vs = vivos()
        for modo in ("igual", "maior"):
            for H in candidatos_altura(vs):
                elig = elegiveis(vs, H, modo)
                if sum(l["rows"] for l in elig) < H:
                    continue
                tps = sorted({l["tipo"] for l in elig})
                melhor = None
                for ordem_t in permutations(tps):
                    falta, tomadas, partes, usados, divs = H, {}, [], set(), 0
                    for t in ordem_t:
                        for l in sorted([x for x in elig if x["tipo"] == t],
                                        key=lambda x: (x["sku"] is None, -x["rows"], x["sku"] or "")):
                            if not falta:
                                break
                            n = min(l["rows"], falta)
                            partes.append((l, n))
                            tomadas[id(l)] = n
                            falta -= n
                            usados.add(t)
                            divs += n < l["rows"]
                    if falta or not valido_apos(tomadas):
                        continue
                    chave = (len(usados), divs)
                    if melhor is None or chave < melhor[0]:
                        melhor = (chave, partes, len(usados))
                if melhor:
                    rot = TIPO_MISTO if melhor[2] > 1 else (TIPO_MESMA_ALTURA if modo == "igual" else TIPO_ALTURAS_DIF)
                    criar(rot, melhor[1], H)
                    return True
        return False

    def montar_final(vs, soltas, hfin):
        p = criar(TIPO_FINAL if soltas else TIPO_FILEIRAS_SOBRAS, [(l, l["rows"]) for l in vs], hfin, final=True)
        for t, itens in soltas.items():
            p["camadas"].append({"tipo": t, "itens": dict(itens), "cheia": False})
        return p

    def montar_final_forcado(vs, soltas):
        """Não há pallet fechado possível sem violar o mínimo de 2 fileiras no último pallet.
        O último pallet recebe 2+ fileiras completas do tipo com mais fileiras e as soltas que couberem;
        o que sobrar vai para pallet(s) incompleto(s) logo antes dele."""
        por_tipo = {}
        for l in vs:
            por_tipo[l["tipo"]] = por_tipo.get(l["tipo"], 0) + l["rows"]
        base = max(por_tipo, key=lambda t: (por_tipo[t], -t)) if por_tipo else None
        unidades = []
        for l in sorted(vs, key=lambda l: (l["tipo"] != base, l["tipo"], -l["hmax"], l["sku"] or "")):
            unidades += [l] * l["rows"]

        vol, hfin = 0.0, ALTURA_MAXIMA_FILEIRAS
        incl, resto_un, sol_fin, sol_resto = {}, [], {}, {}
        for l in unidades[:2]:                       # base mínima do último pallet
            incl[id(l)] = incl.get(id(l), 0) + 1
            vol += 1
            hfin = min(hfin, l["hmax"])
        for t, itens in sorted(soltas.items()):      # soltas que couberem
            v = sum(q / cpf_tipo[t] for q in itens.values())
            nh = min([hfin] + [skus[k]["Altura"] for k in itens])
            if vol + v <= nh + EPS:
                sol_fin[t] = itens
                vol += v
                hfin = nh
            else:
                sol_resto[t] = itens
        for l in unidades[2:]:                       # mais fileiras se ainda couber
            nh = min(hfin, l["hmax"])
            if vol + 1 <= nh + EPS:
                incl[id(l)] = incl.get(id(l), 0) + 1
                vol += 1
                hfin = nh
            else:
                resto_un.append(l)

        abertos = []
        i = 0
        while i < len(resto_un):
            lim, grupo = ALTURA_MAXIMA_FILEIRAS, []
            while i < len(resto_un) and len(grupo) + 1 <= min(lim, resto_un[i]["hmax"]):
                lim = min(lim, resto_un[i]["hmax"])
                grupo.append(resto_un[i])
                i += 1
            if not grupo:
                grupo, i = [resto_un[i]], i + 1
            cont = {}
            for l in grupo:
                cont[id(l)] = (l, cont.get(id(l), (l, 0))[1] + 1)
            abertos.append(criar(TIPO_INCOMPLETO, list(cont.values()), lim,
                                 obs="Fileiras restantes que não fecham um pallet (para o último pallet ficar com 2+ fileiras completas)."))
        for t, itens in sol_resto.items():           # soltas que não couberam no último
            v = sum(q / cpf_tipo[t] for q in itens.values())
            alt = min(skus[k]["Altura"] for k in itens)
            destino = None
            for p in abertos:
                if sum(camada_vol(c) for c in p["camadas"]) + v <= min(p["limite"], alt) + EPS:
                    destino = p
                    break
            if destino is None:
                destino = criar(TIPO_INCOMPLETO, [], alt,
                                obs="Caixas soltas que não couberam no último pallet.")
                abertos.append(destino)
            destino["camadas"].append({"tipo": t, "itens": dict(itens), "cheia": False})
            destino["limite"] = min(destino["limite"], alt)

        partes = [(l, incl[id(l)]) for l in vivos_ids(incl)]
        p = criar(TIPO_FINAL if sol_fin else TIPO_FILEIRAS_SOBRAS, partes, hfin, final=True)
        for t, itens in sol_fin.items():
            p["camadas"].append({"tipo": t, "itens": dict(itens), "cheia": False})

    def vivos_ids(incl):
        return [l for l in lotes if id(l) in incl]

    while True:
        vs = vivos()
        soltas = {t: i for t, i in soltas_tipo.items() if i}
        if not vs and not soltas:
            break
        vol = sum(l["rows"] for l in vs) + sum(q / cpf_tipo[t] for t, i in soltas.items() for q in i.values())
        hfin = min([l["hmax"] for l in vs] + [skus[s]["Altura"] for i in soltas.values() for s in i])
        if vol <= hfin + EPS:
            montar_final(vs, soltas, hfin)
            break
        if fechar_inteiro() or fechar_dividindo():
            continue
        montar_final_forcado(vs, soltas)
        break

    # ---------- 5. ÚLTIMO PALLET: MÍNIMO 2 FILEIRAS COMPLETAS DO MESMO TIPO ----------
    def garantir_minimo_duas():
        if not pallets or not pallets[-1]["final"]:
            return
        fin = pallets[-1]
        cont = {}
        for c in fin["camadas"]:
            if c["cheia"]:
                cont[c["tipo"]] = cont.get(c["tipo"], 0) + 1
        if cont and max(cont.values()) >= 2:
            return
        alvo_tipos = [max(cont, key=cont.get)] if cont else tipos
        precisa = 2 - (max(cont.values()) if cont else 0)
        vol_fin = sum(camada_vol(c) for c in fin["camadas"])
        for p in reversed(pallets[:-1]):
            for t in alvo_tipos:
                cams = [c for c in p["camadas"] if c["tipo"] == t and c["cheia"]]
                if len(cams) < precisa:
                    continue
                mover = cams[-precisa:]
                lim = min([fin["limite"]] + [skus[s]["Altura"] for c in mover for s in c["itens"]])
                if vol_fin + precisa > lim + EPS:
                    continue
                for c in mover:
                    p["camadas"].remove(c)
                fin["camadas"] = mover + fin["camadas"]
                fin["limite"] = lim
                if p["camadas"]:
                    p["obs"] = (f"{precisa} fileira(s) a menos que o fechado: movida(s) para o último pallet "
                                f"para garantir o mínimo de 2 fileiras completas lá.")
                else:
                    pallets.remove(p)
                return
        fin["obs"] = "ATENÇÃO: não foi possível garantir 2 fileiras completas no último pallet (pedido pequeno)."

    garantir_minimo_duas()

    # ---------- 6. SAÍDA ----------
    def faixas(nums):
        out, ini, ant = [], None, None
        for n in nums:
            if ini is None:
                ini = ant = n
            elif n == ant + 1:
                ant = n
            else:
                out.append((ini, ant))
                ini = ant = n
        if ini is not None:
            out.append((ini, ant))
        return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)

    linhas = []
    for idx, p in enumerate(pallets, 1):
        cams = sorted(p["camadas"], key=lambda c: (not c["cheia"], c["tipo"], min(c["itens"])))
        vol = sum(camada_vol(c) for c in cams)
        n_fileiras = int(math.ceil(vol - EPS))
        por_sku = {}
        for pos, c in enumerate(cams, 1):
            for sku, q in c["itens"].items():
                d = por_sku.setdefault(sku, {"qtd": 0, "pos": [], "flag": set()})
                d["qtd"] += q
                if not c["cheia"]:
                    d["flag"].add("soltas no topo")
                else:
                    d["pos"].append(pos)
                    if len(c["itens"]) > 1:
                        d["flag"].add("fileira mista")
        for sku in sorted(por_sku, key=lambda k: (skus[k]["Ordem_Caixa"], k)):
            s, d = skus[sku], por_sku[sku]
            flags = ", ".join(sorted(d["flag"]))
            txt = faixas(d["pos"])
            txt = f"{txt} ({flags})" if txt and flags else (txt or flags)
            linhas.append({
                "Pallet_Num": idx,
                "ID": f"Pallet {idx}",
                "Tipo": p["tipo"],
                "SKU": sku,
                "Produto": s["Produto"],
                "Nº Caixa": s["Nº Caixa"],
                "Quantidade de Caixas": d["qtd"],
                "Caixas por Fileira": s["Caixas_Por_Fileira"],
                "Altura (Fileiras)": s["Altura"],
                "Fileiras (base→topo)": txt,
                "Fileiras no Pallet": n_fileiras,
                "Observação": p["obs"],
            })
    return pd.DataFrame(linhas)


def _validar_pallets(df_pallets, carrinho):
    """Conferência automática: retorna lista de erros (vazia = tudo certo)."""
    erros = []
    pedido = {str(i["SKU"]).strip(): int(i["Qtd_Caixas"]) for i in carrinho}
    saida = df_pallets.groupby("SKU")["Quantidade de Caixas"].sum().to_dict()
    for sku in sorted(set(pedido) | set(saida)):
        if pedido.get(sku, 0) != saida.get(sku, 0):
            erros.append(f"SKU {sku}: pedido {pedido.get(sku, 0)} cx, paletizado {saida.get(sku, 0)} cx.")
    for pn, g in df_pallets.groupby("Pallet_Num"):
        volume = float((g["Quantidade de Caixas"] / g["Caixas por Fileira"]).sum())
        limite = int(g["Altura (Fileiras)"].min())
        if volume > limite + 1e-6:
            erros.append(f"Pallet {pn}: {volume:.2f} fileiras, acima do limite de {limite}.")
    return erros


# --- 7. GERADOR DE PDF ---
def _latin(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")


def gerar_pdf(df_pallets, cliente, data_str):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "MUSTAD - Relatorio de Paletizacao", align="C")
    pdf.ln(7)

    nome_cliente = cliente.strip() if cliente else "Nao Informado"
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Cliente: {_latin(nome_cliente)}", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Data de Emissao: {data_str}", align="C")
    pdf.ln(5)

    n_pallets = int(df_pallets["Pallet_Num"].nunique())
    total_cx = int(df_pallets["Quantidade de Caixas"].sum())
    pdf.cell(0, 5, f"{n_pallets} pallets | TOTAL DE CAIXAS: {total_cx}", align="C")
    pdf.ln(8)

    pdf.set_fill_color(0, 85, 184)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, f"TOTAL GERAL DA CARGA: {total_cx} CAIXAS", align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(15)

    for pn in sorted(df_pallets["Pallet_Num"].unique()):
        df_p = df_pallets[df_pallets["Pallet_Num"] == pn]
        cx_pallet = int(df_p["Quantidade de Caixas"].sum())

        if pdf.get_y() + (len(df_p) * 6) + 35 > 285:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"Pallet {pn}", border="B")
        pdf.ln(8)

        headers = ["SKU", "Produto", "N. Cx", "Qtd Cx", "Cx / Fileira", "Fileiras (base-topo)"]
        larg = [28, 62, 14, 18, 22, 46]
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(235, 235, 235)

        for w, t in zip(larg, headers):
            pdf.cell(w, 6, t, border=1, fill=True, align="C")
        pdf.ln()

        for _, row in df_p.iterrows():
            pdf.set_font("Helvetica", size=8)
            pdf.cell(larg[0], 6, str(row["SKU"]), border=1)
            pdf.cell(larg[1], 6, _latin(row["Produto"])[:40], border=1)
            pdf.cell(larg[2], 6, str(row["Nº Caixa"]), border=1, align="C")
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(larg[3], 6, str(row["Quantidade de Caixas"]), border=1, align="C")
            pdf.set_font("Helvetica", size=8)
            pdf.cell(larg[4], 6, str(row["Caixas por Fileira"]), border=1, align="C")
            pdf.cell(larg[5], 6, _latin(row["Fileiras (base→topo)"]), border=1, align="C")
            pdf.ln()

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, f"Quantidade de caixas no Pallet {pn}: {cx_pallet} caixas", align="R")
        pdf.ln(7)
        obs = str(df_p["Observação"].iloc[0] or "").strip()
        if obs:
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 5, _latin("Obs.: " + obs)[:150])
            pdf.ln(5)
        pdf.ln(3)

    return bytes(pdf.output())


# --- 8. EXECUÇÃO E EXIBIÇÃO DE RESULTADOS ---
if st.button("⚙️ CALCULAR E GERAR PALLETS"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

if st.session_state.processado and st.session_state.carrinho:
    df_pallets = _gerar_pallets(st.session_state.carrinho, df_produtos)
    erros_validacao = _validar_pallets(df_pallets, st.session_state.carrinho)
    if erros_validacao:
        st.error("❌ A conferência automática encontrou erros. O relatório foi bloqueado; avise o responsável pelo sistema.")
        for e in erros_validacao:
            st.write(f"• {e}")
        st.stop()
    n_pallets = int(df_pallets["Pallet_Num"].nunique())

    st.subheader("📦 Resultado da Paletização")
    st.success(f"**Total de Pallets Gerados:** {n_pallets} Pallets")

    if FPDF_DISPONIVEL:
        data_atual = datetime.now()
        pdf_bytes = gerar_pdf(
            df_pallets, nome_cliente_input, data_atual.strftime("%d/%m/%Y")
        )
        cliente_limpo = re.sub(r'[\\/*?:"<>|]', "", nome_cliente_input.strip()) or "CLIENTE"

        st.download_button(
            label="📄 Baixar Relatório em PDF",
            data=pdf_bytes,
            file_name=f"PALETIZACAO_{cliente_limpo}_{data_atual.strftime('%d-%m-%Y')}.pdf",
            mime="application/pdf",
        )

    st.markdown("---")

    # Roteiro de separação: cada SKU é retirado UMA vez e distribuído nos pallets indicados
    with st.expander("🧭 Roteiro de separação (retirar cada SKU uma única vez)", expanded=False):
        roteiro = (
            df_pallets.groupby(["SKU", "Produto", "Nº Caixa"], sort=False)
            .agg(
                Total_Caixas=("Quantidade de Caixas", "sum"),
                Pallets=("Pallet_Num", lambda x: ", ".join(str(n) for n in sorted(set(x)))),
            )
            .reset_index()
            .sort_values(["Nº Caixa", "SKU"])
            .rename(columns={"Total_Caixas": "Total de Caixas", "Pallets": "Vai para os Pallets"})
        )
        st.dataframe(roteiro, use_container_width=True, hide_index=True)

    for pn in sorted(df_pallets["Pallet_Num"].unique()):
        df_p = df_pallets[df_pallets["Pallet_Num"] == pn]
        total_cx_pallet = int(df_p["Quantidade de Caixas"].sum())

        with st.expander(f"📌 Pallet {pn}", expanded=True):
            df_exibicao = df_p[[
                "SKU",
                "Produto",
                "Nº Caixa",
                "Quantidade de Caixas",
                "Caixas por Fileira",
                "Fileiras (base→topo)",
            ]].copy()

            obs_pallet = str(df_p["Observação"].iloc[0] or "").strip()
            if obs_pallet:
                st.warning(obs_pallet)
            st.caption(f"{df_p['Tipo'].iloc[0]}  |  {int(df_p['Fileiras no Pallet'].iloc[0])} fileira(s) de altura")
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

            st.markdown(
                f"""
                <div style="text-align: right;">
                    <span class="total-caixas-destaque">
                        📦 Quantidade de Caixas no Pallet {pn}: <b>{total_cx_pallet} caixas</b>
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
