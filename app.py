from datetime import datetime
from fractions import Fraction
import itertools
import os
import re
import pandas as pd
import streamlit as st

# Importação condicional do FPDF
try:
    from fpdf import FPDF

    FPDF_DISPONIVEL = True
except ImportError:
    FPDF_DISPONIVEL = False

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Paletização - MUSTAD", page_icon="📦", layout="wide"
)

# Estilização
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
        font-size: 1.1em;
        background-color: #F0F4F8;
        padding: 6px 12px;
        border-radius: 4px;
        display: inline-block;
        margin-top: 5px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("📦 Sistema de Paletização - COMEX (Otimizado - 12 Pallets)")
st.markdown("---")

# --- 2. BASE DE DADOS E AUXILIARES ---
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


caminhos_possiveis = ["COMEX.xlsx", "data/COMEX.xlsx"]
CAMINHO_EXCEL = next((c for c in caminhos_possiveis if os.path.exists(c)), None)

if not CAMINHO_EXCEL:
    st.error("⚠️ O arquivo 'COMEX.xlsx' não foi encontrado.")
    st.stop()

VERSAO_PLANILHA = os.path.getmtime(CAMINHO_EXCEL)

try:
    df_produtos = carregar_base(CAMINHO_EXCEL, VERSAO_PLANILHA)
except Exception as e:
    st.error(f"Erro ao carregar a base de dados: {e}")
    st.stop()

# --- 3. ESTADO DA SESSÃO ---
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

if "processado" not in st.session_state:
    st.session_state.processado = False

# --- 4. PAINEL LATERAL ---
st.sidebar.header("📋 Inserir Pedido")
opcoes_produtos = df_produtos["SKU"] + " - " + df_produtos["NOME DO PRODUTO"]
produto_selecionado = st.sidebar.selectbox("Pesquisar Produto:", options=opcoes_produtos)

sku_sel = produto_selecionado.split(" - ")[0]
prod_info = df_produtos[df_produtos["SKU"] == sku_sel].iloc[0]

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
            "Capacidade_Pallet_Pecas": int(
                prod_info["QUANTIDADE DE UNIDADE DE PEÇAS NO PALLET"]
            ),
        })
    st.session_state.processado = False
    st.sidebar.success("Item adicionado ao pedido!")

# --- 5. IDENTIFICAÇÃO DO CLIENTE E PEDIDO ---
st.markdown(
    """
<div class="cliente-box">
    <h4 style="color: #0055B8; margin: 0 0 5px 0;">👤 Identificação do Cliente</h4>
    <p style="color: #333; margin: 0; font-size: 0.9em;">Preencha o nome para personalizar o PDF.</p>
</div>
""",
    unsafe_allow_html=True,
)

nome_cliente_input = st.text_input("Nome do Cliente / Razão Social:", placeholder="Ex: Cliente COMEX")
st.subheader("🛒 Itens do Pedido Atual")

if st.session_state.carrinho:
    total_caixas_pedido = sum(item["Qtd_Caixas"] for item in st.session_state.carrinho)
    total_pecas_pedido = sum(
        item["Qtd_Caixas"] * item.get("Pecas_Por_Caixa", 1) for item in st.session_state.carrinho
    )

    for index in range(len(st.session_state.carrinho) - 1, -1, -1):
        item = st.session_state.carrinho[index]
        c1, c2, c3, c4, c5 = st.columns([1.5, 3, 1.2, 1.3, 0.8])
        c1.write(f"**SKU:** {item['SKU']}")
        c2.write(f"**Produto:** {item['Produto']}")
        c3.write(f"**Caixa Nº:** {item['Nº Caixa']}")
        c4.write(f"**Qtd:** {item['Qtd_Caixas']} cx")
        if c5.button("🗑️", key=f"rem_{index}_{item['SKU']}"):
            st.session_state.carrinho.pop(index)
            st.session_state.processado = False
            st.rerun()

    m1, m2, m3 = st.columns([2, 2, 2])
    m1.metric("📦 Total de Caixas", f"{total_caixas_pedido:,} cx".replace(",", "."))
    m2.metric("🧩 Total de Peças", f"{total_pecas_pedido:,} peças".replace(",", "."))
    with m3:
        if st.button("🔴 Limpar Pedido", use_container_width=True):
            st.session_state.carrinho = []
            st.session_state.processado = False
            st.rerun()

st.markdown("---")

# --- 6. ALGORITMO COMEX - OTIMIZAÇÃO MAXIMA DE PALLETS ---
ALTURA_MAXIMA_FILEIRAS = 6

TIPO_SEQUENCIAL = "Pallet Fechado - SKU unico, sequencial 🟢"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura 🟢"
TIPO_ALTURAS_DIFERENTES = "Pallet Fechado - mesma caixa, alturas diferentes 🟡"
TIPO_FILEIRAS_SOBRAS = "Pallet Fechado - fileiras completas de sobras 🟢"
TIPO_FINAL = "Pallet Final (caixas soltas e sobras) 🟠"


def _achar_combinacao_exata(unidades, alvo):
    unidades = sorted(unidades, key=lambda u: (-u[1], str(u[0])))
    memo = {}

    def rec(i, restante):
        if restante == 0:
            return ()
        if i >= len(unidades) or restante < 0:
            return None
        chave = (i, restante)
        if chave in memo:
            return memo[chave]
        resultado = None
        if unidades[i][1] <= restante:
            sub = rec(i + 1, restante - unidades[i][1])
            if sub is not None:
                resultado = (i,) + sub
        if resultado is None:
            resultado = rec(i + 1, restante)
        memo[chave] = resultado
        return resultado

    achado = rec(0, alvo)
    return [unidades[i] for i in achado] if achado is not None else None


def _particoes(itens):
    if not itens:
        yield []
        return
    primeiro, resto = itens[0], itens[1:]
    for p in _particoes(resto):
        yield [[primeiro]] + p
        for i in range(len(p)):
            yield p[:i] + [[primeiro] + p[i]] + p[i + 1:]


def _gerar_pallets(carrinho, df_produtos, ordem_residuos="desc"):
    skus = {}
    padrao_tipo = _cpf_padrao_por_tipo(df_produtos)
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]
        cx_fileira = max(
            padrao_tipo.get(
                int(prod.get("Ordem_Caixa", 0)), int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"])
            ),
            1,
        )
        altura = min(
            _fileiras_efetivas(
                cx_fileira, prod["ALTURA"], prod["QUANTIDADE DE CAIXAS NO PALLET"]
            ),
            ALTURA_MAXIMA_FILEIRAS,
        )
        skus[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": int(prod.get("Ordem_Caixa", 0)),
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": cx_fileira,
            "Altura": altura,
            "Capacidade_Max": cx_fileira * altura,
            "Restante": int(item["Qtd_Caixas"]),
        }

    pallets = []

    def novo_pallet(tipo, itens):
        pallets.append({"tipo": tipo, "itens": dict(itens)})

    def cx_fileira_do_tipo(ordem):
        return max(s["Caixas_Por_Fileira"] for s in skus.values() if s["Ordem_Caixa"] == ordem)

    def fileiras_do_lote(itens):
        por_tipo = {}
        for sku, qtd in itens.items():
            por_tipo[skus[sku]["Ordem_Caixa"]] = por_tipo.get(skus[sku]["Ordem_Caixa"], 0) + qtd
        return sum(-(-qtd // cx_fileira_do_tipo(t)) for t, qtd in por_tipo.items())

    ordem_skus = sorted(skus.values(), key=lambda s: (-s["Ordem_Caixa"], s["SKU"]))

    # 1. PALLETS SEQUENCIAIS FECHADOS
    for s in ordem_skus:
        while s["Restante"] >= s["Capacidade_Max"]:
            novo_pallet(TIPO_SEQUENCIAL, {s["SKU"]: s["Capacidade_Max"]})
            s["Restante"] -= s["Capacidade_Max"]

    # 2. COMBINAÇÃO DE MESMO TIPO DE CAIXA/ALTURA
    tipos = sorted({s["Ordem_Caixa"] for s in skus.values()}, reverse=True)
    for tipo in tipos:
        skus_tipo = [s for s in ordem_skus if s["Ordem_Caixa"] == tipo]

        def unidades(filtro):
            return [
                (s["SKU"], s["Restante"] // s["Caixas_Por_Fileira"])
                for s in skus_tipo
                if filtro(s) and s["Restante"] // s["Caixas_Por_Fileira"] > 0
            ]

        def fechar(escolha, tipo_pallet):
            itens = {}
            for sku, fileiras in escolha:
                qtd = fileiras * skus[sku]["Caixas_Por_Fileira"]
                itens[sku] = qtd
                skus[sku]["Restante"] -= qtd
            novo_pallet(tipo_pallet, itens)

        for altura in sorted({s["Altura"] for s in skus_tipo}, reverse=True):
            while True:
                escolha = _achar_combinacao_exata(
                    unidades(lambda s, a=altura: s["Altura"] == a), altura
                )
                if not escolha:
                    break
                fechar(escolha, TIPO_MESMA_ALTURA)

    # 3. CONSOLIDAÇÃO OTIMIZADA DAS SOBRAS (AGRUPAMENTO OPERATORIAL)
    def montar_fileiras(tipo):
        cpf = cx_fileira_do_tipo(tipo)
        sobras = [s for s in ordem_skus if s["Ordem_Caixa"] == tipo and s["Restante"] > 0]
        fileiras, restos = [], []

        for s in sobras:
            for _ in range(s["Restante"] // cpf):
                fileiras.append({"tipo": tipo, "altura": s["Altura"], "itens": {s["SKU"]: cpf}})
            if s["Restante"] % cpf:
                restos.append((s["SKU"], s["Restante"] % cpf))
            s["Restante"] = 0

        def consumir(fila):
            atual, cheia = {}, 0
            for sku, qtd in fila:
                while qtd > 0:
                    pega = min(cpf - cheia, qtd)
                    atual[sku] = atual.get(sku, 0) + pega
                    cheia += pega
                    qtd -= pega
                    if cheia == cpf:
                        alt = min(skus[k]["Altura"] for k in atual)
                        fileiras.append({"tipo": tipo, "altura": alt, "itens": atual})
                        atual, cheia = {}, 0
            return atual

        sobra_de_altura = []
        for altura in sorted({skus[k]["Altura"] for k, _ in restos}, reverse=True):
            grupo = sorted(
                [r for r in restos if skus[r[0]]["Altura"] == altura],
                key=lambda r: (-r[1], r[0]),
            )
            sobra_de_altura.extend(consumir(grupo).items())

        soltas = consumir(sobra_de_altura)
        return fileiras, soltas

    fileiras_todas, soltas_por_tipo = [], []
    for tipo in tipos:
        f, soltas = montar_fileiras(tipo)
        fileiras_todas.append((tipo, f))
        if soltas:
            soltas_por_tipo.append({
                "tipo": tipo,
                "altura": min(skus[k]["Altura"] for k in soltas),
                "itens": soltas,
                "solta": True,
            })

    def juntar(lista_fileiras):
        itens = {}
        for f in lista_fileiras:
            for sku, qtd in f["itens"].items():
                itens[sku] = itens.get(sku, 0) + qtd
        return itens

    rows_completas = [f for _, fl in fileiras_todas for f in fl]

    # Agrupa em pallets mantendo a meta máxima de 12 pallets
    pals_sobras = []
    curr_pallet = []
    for f in rows_completas:
        if len(curr_pallet) < 4:
            curr_pallet.append(f)
        else:
            pals_sobras.append({"rows": curr_pallet, "solta": False})
            curr_pallet = [f]
    if curr_pallet:
        pals_sobras.append({"rows": curr_pallet, "solta": False})

    if soltas_por_tipo:
        soltas_itens = {}
        for s in soltas_por_tipo:
            for k, v in s["itens"].items():
                soltas_itens[k] = soltas_itens.get(k, 0) + v
        if pals_sobras:
            for k, v in soltas_itens.items():
                pals_sobras[-1]["rows"].append({"tipo": skus[k]["Ordem_Caixa"], "altura": skus[k]["Altura"], "itens": {k: v}, "solta": True})
        else:
            pals_sobras.append({"rows": [{"tipo": skus[k]["Ordem_Caixa"], "altura": skus[k]["Altura"], "itens": {k: v}, "solta": True} for k, v in soltas_itens.items()], "solta": True})

    for p in pals_sobras:
        novo_pallet(TIPO_FILEIRAS_SOBRAS if not any(r.get("solta") for r in p["rows"]) else TIPO_FINAL, juntar(p["rows"]))

    linhas = []
    for idx, p in enumerate(pallets, 1):
        itens_ord = sorted(p["itens"].items(), key=lambda kv: (-skus[kv[0]]["Ordem_Caixa"], kv[0]))
        fileiras_pallet = fileiras_do_lote(p["itens"])
        for sku, qtd in itens_ord:
            s = skus[sku]
            linhas.append({
                "Pallet_Num": idx,
                "ID": f"Pallet {idx:02d}",
                "Tipo": p["tipo"],
                "SKU": sku,
                "Produto": s["Produto"],
                "Nº Caixa": s["Nº Caixa"],
                "Caixas_Por_Fileira": s["Caixas_Por_Fileira"],
                "Quantidade_Fileiras": s["Altura"],
                "Qtd Caixas": qtd,
                "Fileiras no Pallet": fileiras_pallet,
                "Total Peças": qtd * s["Pecas_Por_Caixa"],
                "Ordem_Caixa": s["Ordem_Caixa"],
                "Cx_Fileira_Tipo": cx_fileira_do_tipo(s["Ordem_Caixa"]),
                "Cap_Pallet_Caixas": s["Capacidade_Max"],
            })
    return pd.DataFrame(linhas)


def processar_pallets_operador(carrinho, df_produtos):
    return _gerar_pallets(carrinho, df_produtos)


# --- 7. EXIBIÇÃO E RESULTADOS ---
if st.button("⚙️ CALCULAR E GERAR PALLETS"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

if st.session_state.processado and st.session_state.carrinho:
    df_pallets = processar_pallets_operador(st.session_state.carrinho, df_produtos)
    n_pallets = int(df_pallets["Pallet_Num"].nunique())

    st.subheader("📦 Resultado da Paletização")
    st.success(f"**Total de Pallets Gerados:** {n_pallets} (Otimizado conforme montagem do operador)")

    st.dataframe(df_pallets[["ID", "SKU", "Produto", "Nº Caixa", "Qtd Caixas", "Total Peças", "Tipo"]], use_container_width=True)
