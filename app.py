from datetime import datetime
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

# CSS para estilo visual
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

# --- CABEÇALHO DA PÁGINA ---
st.title("📦 Sistema de Paletização - COMEX")
st.markdown("---")


# --- 2. CARREGAMENTO E TRATAMENTO DA BASE DE DADOS ---
@st.cache_data
def carregar_base(caminho_excel):
    df = pd.read_excel(caminho_excel)
    df.columns = df.columns.str.strip()

    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["NOME DO PRODUTO"] = df["NOME DO PRODUTO"].astype(str).str.strip()
    df["NUMERO DA CAIXA"] = df["NUMERO DA CAIXA"].astype(str).str.strip()

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

    return df


caminhos_possiveis = ["COMEX.xlsx", "data/COMEX.xlsx"]
CAMINHO_EXCEL = None

for c in caminhos_possiveis:
    if os.path.exists(c):
        CAMINHO_EXCEL = c
        break

if not CAMINHO_EXCEL:
    st.error(
        "⚠️ O arquivo 'COMEX.xlsx' não foi encontrado no diretório do projeto."
    )
    st.stop()

try:
    df_produtos = carregar_base(CAMINHO_EXCEL)
except Exception as e:
    st.error(f"Erro ao carregar a base de dados ({CAMINHO_EXCEL}): {e}")
    st.stop()

# --- 3. ESTADO DA SESSÃO ---
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

if "processado" not in st.session_state:
    st.session_state.processado = False

# --- 4. PAINEL LATERAL ---
st.sidebar.header("📋 Inserir Pedido")
opcoes_produtos = df_produtos["SKU"] + " - " + df_produtos["NOME DO PRODUTO"]
produto_selecionado = st.sidebar.selectbox(
    "Pesquisar Produto (SKU ou Nome):", options=opcoes_produtos
)

sku_sel = produto_selecionado.split(" - ")[0]
prod_info = df_produtos[df_produtos["SKU"] == sku_sel].iloc[0]

st.sidebar.info(f"""
**Informações de Cadastro do SKU:**  
• **Tipo da Caixa:** Caixa {prod_info['NUMERO DA CAIXA']}  
• **Peças / Caixa:** {prod_info['QUANTIDADE DE PEÇAS']}  
• **Caixas / Fileira:** {prod_info['QUANTIDADE DE CAIXAS POR FILEIRA']}  
• **Quantidade de Fileiras no Pallet:** {prod_info['ALTURA']}  
• **Capacidade Caixas / Pallet:** {prod_info['QUANTIDADE DE CAIXAS NO PALLET']} cx  
• **Capacidade Peças / Pallet:** {prod_info['QUANTIDADE DE UNIDADE DE PEÇAS NO PALLET']} peças
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
            "Capacidade_Pallet_Pecas": int(
                prod_info["QUANTIDADE DE UNIDADE DE PEÇAS NO PALLET"]
            ),
        })
    st.session_state.processado = False
    st.sidebar.success("Item adicionado ao pedido!")

# --- 5. IDENTIFICAÇÃO DO CLIENTE ---
st.markdown(
    """
<div class="cliente-box">
    <h4 style="color: #0055B8; margin: 0 0 5px 0;">👤 Identificação do Cliente</h4>
    <p style="color: #333; margin: 0 0 10px 0; font-size: 0.9em;">Preencha o nome do cliente para personalizar o relatório PDF final.</p>
</div>
""",
    unsafe_allow_html=True,
)

nome_cliente_input = st.text_input(
    "Nome do Cliente / Razão Social:",
    placeholder="Ex: Distribuidora Silva",
    key="nome_cliente_key",
)

st.subheader("🛒 Itens do Pedido Atual")

if st.session_state.carrinho:
    total_caixas_pedido = 0
    total_pecas_pedido = 0

    for index in range(len(st.session_state.carrinho) - 1, -1, -1):
        item = st.session_state.carrinho[index]
        pecas_cx = item.get("Pecas_Por_Caixa", 1)
        total_pecas_item = item["Qtd_Caixas"] * pecas_cx

        total_caixas_pedido += item["Qtd_Caixas"]
        total_pecas_pedido += total_pecas_item

        c1, c2, c3, c4, c5, c6 = st.columns([1.5, 3, 1.2, 1.3, 1.5, 0.8])
        c1.write(f"**SKU:** {item['SKU']}")
        c2.write(f"**Produto:** {item['Produto']}")
        c3.write(f"**Caixa Nº:** {item['Nº Caixa']}")
        c4.write(f"**Qtd:** {item['Qtd_Caixas']} cx")
        c5.write(f"**Total Peças:** {total_pecas_item:,}".replace(",", "."))

        if c6.button(
            "🗑️", key=f"remover_{index}_{item['SKU']}", help="Remover item"
        ):
            st.session_state.carrinho.pop(index)
            st.session_state.processado = False
            st.rerun()

    st.markdown("---")
    m1, m2, m3 = st.columns([2, 2, 2])
    m1.metric(
        label="📦 Total de Caixas",
        value=f"{total_caixas_pedido:,} cx".replace(",", "."),
    )
    m2.metric(
        label="🧩 Total de Peças",
        value=f"{total_pecas_pedido:,} peças".replace(",", "."),
    )

    with m3:
        st.write("")
        if st.button("🔴 Limpar Pedido", use_container_width=True):
            st.session_state.carrinho = []
            st.session_state.processado = False
            st.rerun()
else:
    st.info("Nenhum item inserido no pedido até o momento.")

st.markdown("---")


# --- 6. ALGORITMO COMEX - REGRAS REVISADAS DE PALETIZAÇÃO ---
ALTURA_MAXIMA_FILEIRAS = 5
MINIMO_FILEIRAS_ULTIMO_PALLET = 2

TIPO_SEQUENCIAL = "Pallet Fechado - SKU unico, sequencial 🟢"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura 🟢"
TIPO_ALTURAS_DIFERENTES = "Pallet Fechado - mesma caixa, alturas diferentes 🟡"
TIPO_FINAL = "Pallet Misto Inteligente / Final 🟠"


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
    if achado is None:
        return None
    return [unidades[i] for i in achado]


def processar_pallets_operador(carrinho, df_produtos):
    skus = {}
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]
        cx_fileira = max(int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"]), 1)
        altura = max(min(int(prod["ALTURA"]), ALTURA_MAXIMA_FILEIRAS), 1)
        skus[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": int(prod.get("Ordem_Caixa", 0)),
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": cx_fileira,
            "Altura": altura,
            "Capacidade_Max": max(int(prod["QUANTIDADE DE CAIXAS NO PALLET"]), 1),
            "Restante": int(item["Qtd_Caixas"]),
        }

    pallets = []

    def novo_pallet(tipo, itens):
        pallets.append({"tipo": tipo, "itens": dict(itens)})

    def cx_fileira_do_tipo(ordem):
        return max(
            s["Caixas_Por_Fileira"]
            for s in skus.values()
            if s["Ordem_Caixa"] == ordem
        )

    def fileiras_do_lote(itens):
        por_tipo = {}
        for sku, qtd in itens.items():
            por_tipo[skus[sku]["Ordem_Caixa"]] = (
                por_tipo.get(skus[sku]["Ordem_Caixa"], 0) + qtd
            )
        return sum(
            -(-qtd // cx_fileira_do_tipo(t)) for t, qtd in por_tipo.items()
        )

    ordem_skus = sorted(
        skus.values(), key=lambda s: (-s["Ordem_Caixa"], s["SKU"])
    )

    # ETAPA 1: Pallets completos de um único SKU (Sequenciais)
    for s in ordem_skus:
        while s["Restante"] >= s["Capacidade_Max"]:
            novo_pallet(TIPO_SEQUENCIAL, {s["SKU"]: s["Capacidade_Max"]})
            s["Restante"] -= s["Capacidade_Max"]

    # ETAPA 2: Pallets fechados do mesmo tipo de caixa e mesma altura ou alturas diferentes
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

        achou = True
        while achou:
            achou = False
            for alvo in sorted(
                {s["Altura"] for s in skus_tipo}, reverse=True
            ):
                elegiveis = unidades(lambda s, a=alvo: s["Altura"] >= a)
                for sku_base, fil_base in [
                    u for u in elegiveis if skus[u[0]]["Altura"] == alvo
                ]:
                    outros = [u for u in elegiveis if u[0] != sku_base]
                    resto = (
                        _achar_combinacao_exata(outros, alvo - fil_base)
                        if fil_base < alvo
                        else []
                    )
                    if resto is not None:
                        fechar(
                            [(sku_base, fil_base)] + resto,
                            TIPO_ALTURAS_DIFERENTES,
                        )
                        achou = True
                        break
                if achou:
                    break

    # ETAPA 3: Montagem inteligente de sobras e pallets finais por tipo de caixa (respeitando no máximo 2 tipos por pallet e completando fileiras)
    def montar_fileiras_e_sobras(tipo):
        cpf = cx_fileira_do_tipo(tipo)
        sobras = [
            s
            for s in ordem_skus
            if s["Ordem_Caixa"] == tipo and s["Restante"] > 0
        ]
        fileiras = []
        residuos = []

        def consumir_e_completar(fila):
            atual, cheia = {}, 0
            for sku, qtd in fila:
                while qtd > 0:
                    pega = min(cpf - cheia, qtd)
                    atual[sku] = atual.get(sku, 0) + pega
                    cheia += pega
                    qtd -= pega
                    if cheia == cpf:
                        alt = min(skus[k]["Altura"] for k in atual)
                        fileiras.append({
                            "tipo": tipo,
                            "altura": alt,
                            "itens": atual,
                        })
                        atual, cheia = {}, 0
            return atual, cheia

        # Tenta formar fileiras completas por SKU primeiro
        for s in sobras:
            qtd = s["Restante"]
            restantes_sku = s["Restante"] % cpf
            completas = qtd - restantes_sku
            if completas > 0:
                num_fil = completas // cpf
                fileiras.append({
                    "tipo": tipo,
                    "altura": s["Altura"],
                    "itens": {s["SKU"]: completas},
                })
                s["Restante"] = restantes_sku

        # Coleta o que sobrou para tentar complementar com SKUs do mesmo tipo e altura
        sobras_ativas = [(s["SKU"], s["Restante"], s["Altura"]) for s in sobras if s["Restante"] > 0]
        sobras_ativas.sort(key=lambda x: (-x[2], x[0]))

        i = 0
        while i < len(sobras_ativas):
            sku1, qtd1, alt1 = sobras_ativas[i]
            if qtd1 == 0:
                i += 1
                continue
            
            # Tenta preencher uma fileira com SKU1
            fileira_atual = {sku1: min(cpf, qtd1)}
            cheia = fileira_atual[sku1]
            qtd1 -= fileira_atual[sku1]
            
            # Se a fileira não estiver cheia, busca outro SKU do mesmo tipo e altura para completar
            if cheia < cpf:
                for j in range(i + 1, len(sobras_ativas)):
                    sku2, qtd2, alt2 = sobras_ativas[j]
                    if qtd2 > 0 and alt2 == alt1:
                        pega = min(cpf - cheia, qtd2)
                        fileira_atual[sku2] = fileira_atual.get(sku2, 0) + pega
                        cheia += pega
                        qtd2 -= pega
                        sobras_ativas[j] = (sku2, qtd2, alt2)
                        if cheia == cpf:
                            break

            fileiras.append({
                "tipo": tipo,
                "altura": min(skus[k]["Altura"] for k in fileira_atual),
                "itens": fileira_atual,
            })
            sobras_ativas[i] = (sku1, qtd1, alt1)
            if qtd1 == 0:
                i += 1

        for s in sobras:
            s["Restante"] = 0
        return fileiras

    fileiras_todas = []
    for tipo in tipos:
        fl = montar_fileiras_e_sobras
