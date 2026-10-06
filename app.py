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


# --- 6. ALGORITMO COMEX - PALLETS SEQUENCIAIS, TIPO DE CAIXA E ALTURA ---
ALTURA_MAXIMA_FILEIRAS = 5

TIPO_SEQUENCIAL = "Pallet Fechado - SKU unico, sequencial 🟢"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura 🟢"
TIPO_ALTURAS_DIFERENTES = "Pallet Fechado - mesma caixa, alturas diferentes 🟡"
TIPO_FINAL = "Pallet Final (caixas soltas e sobras) 🟠"


def _achar_combinacao_exata(unidades, alvo):
    """Procura combinação de blocos inteiros (SKU, fileiras) cuja soma de
    fileiras seja exatamente 'alvo'. Prefere blocos maiores (menos SKUs no pallet)."""
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
    # --- Preparação dos SKUs do pedido ---
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

    # Cada pallet: {"tipo": str, "itens": {sku: caixas}}
    pallets = []

    def novo_pallet(tipo, itens):
        pallets.append({"tipo": tipo, "itens": dict(itens)})

    def cx_fileira_do_tipo(ordem):
        return max(s["Caixas_Por_Fileira"] for s in skus.values() if s["Ordem_Caixa"] == ordem)

    def fileiras_do_lote(itens):
        """Fileiras ocupadas: caixas do mesmo tipo dividem fileiras entre si."""
        por_tipo = {}
        for sku, qtd in itens.items():
            por_tipo[skus[sku]["Ordem_Caixa"]] = por_tipo.get(skus[sku]["Ordem_Caixa"], 0) + qtd
        return sum(-(-qtd // cx_fileira_do_tipo(t)) for t, qtd in por_tipo.items())

    def so_fileiras_completas(itens):
        por_tipo = {}
        for sku, qtd in itens.items():
            por_tipo[skus[sku]["Ordem_Caixa"]] = por_tipo.get(skus[sku]["Ordem_Caixa"], 0) + qtd
        return all(qtd % cx_fileira_do_tipo(t) == 0 for t, qtd in por_tipo.items())

    def limite_fileiras(itens):
        return min([ALTURA_MAXIMA_FILEIRAS] + [skus[sku]["Altura"] for sku in itens])

    ordem_skus = sorted(skus.values(), key=lambda s: (-s["Ordem_Caixa"], s["SKU"]))

    # ETAPA 1: pallets completos de um único SKU, SEQUENCIAIS (Pallet 01, 02, ...)
    for s in ordem_skus:
        while s["Restante"] >= s["Capacidade_Max"]:
            novo_pallet(TIPO_SEQUENCIAL, {s["SKU"]: s["Capacidade_Max"]})
            s["Restante"] -= s["Capacidade_Max"]

    # ETAPA 2: pallets mistos, SEMPRE separados por tipo de caixa.
    # Só entram fileiras completas; blocos de um SKU não são divididos.
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

        # 2.1: MESMA ALTURA dentro do mesmo tipo de caixa
        for altura in sorted({s["Altura"] for s in skus_tipo}, reverse=True):
            while True:
                escolha = _achar_combinacao_exata(
                    unidades(lambda s, a=altura: s["Altura"] == a), altura
                )
                if not escolha:
                    break
                fechar(escolha, TIPO_MESMA_ALTURA)

        # 2.2: esgotada a mesma altura, mistura ALTURAS DIFERENTES (mesmo tipo de caixa)
        achou = True
        while achou:
            achou = False
            for alvo in sorted({s["Altura"] for s in skus_tipo}, reverse=True):
                elegiveis = unidades(lambda s, a=alvo: s["Altura"] >= a)
                # precisa de ao menos um SKU com a altura-limite do pallet
                for sku_base, fil_base in [u for u in elegiveis if skus[u[0]]["Altura"] == alvo]:
                    outros = [u for u in elegiveis if u[0] != sku_base]
                    resto = _achar_combinacao_exata(outros, alvo - fil_base) if fil_base < alvo else []
                    if resto is not None:
                        fechar([(sku_base, fil_base)] + resto, TIPO_ALTURAS_DIFERENTES)
                        achou = True
                        break
                if achou:
                    break

    # ETAPA 3: sobras. Regra: fechar a fileira do tipo de caixa antes de entrar
    # outro tipo. Só as caixas que NÃO completam fileira vão para o último pallet.
    def montar_fileiras(tipo):
        """Divide as sobras de um tipo em fileiras completas + caixas soltas.
        Primeiro por mesma altura; depois mistura alturas (mesmo tipo)."""
        cpf = cx_fileira_do_tipo(tipo)
        sobras = [s for s in ordem_skus if s["Ordem_Caixa"] == tipo and s["Restante"] > 0]
        fileiras, residuos = [], []

        def consumir(fila, altura_fixa):
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

        for altura in sorted({s["Altura"] for s in sobras}, reverse=True):
            grupo = sorted(
                [s for s in sobras if s["Altura"] == altura],
                key=lambda s: (-s["Restante"], s["SKU"]),
            )
            resto = consumir([(s["SKU"], s["Restante"]) for s in grupo], altura)
            residuos.extend(resto.items())
        # mistura alturas diferentes só com o que sobrou (mesmo tipo de caixa)
        residuos.sort(key=lambda kv: (-skus[kv[0]]["Altura"], -kv[1], kv[0]))
        soltas = consumir(residuos, None)
        for s in sobras:
            s["Restante"] = 0
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

    # tipos com mais fileiras primeiro (empate: menor número de caixa)
    fileiras_todas.sort(key=lambda tf: (-len(tf[1]), tf[0]))

    def juntar(lista_fileiras):
        itens = {}
        for f in lista_fileiras:
            for sku, qtd in f["itens"].items():
                itens[sku] = itens.get(sku, 0) + qtd
        return itens

    def cabe(lista_fileiras, nova):
        alt = min([ALTURA_MAXIMA_FILEIRAS] + [f["altura"] for f in lista_fileiras + [nova]])
        return len(lista_fileiras) + 1 <= alt

    TIPO_FILEIRAS_SOBRAS = "Pallet Fechado - fileiras completas de sobras 🟢"
    fechados_sobras = []
    parciais = []
    for altura in sorted({f["altura"] for _, fl in fileiras_todas for f in fl}, reverse=True):
        atual = []
        for _, fl in fileiras_todas:
            for f in [x for x in fl if x["altura"] == altura]:
                if atual and not cabe(atual, f):
                    fechados_sobras.append(list(atual))
                    atual = []
                atual.append(f)
                if len(atual) == min(ALTURA_MAXIMA_FILEIRAS, altura):
                    fechados_sobras.append(list(atual))
                    atual = []
        if atual:
            parciais.append(atual)

    # pallets incompletos de alturas diferentes: juntar se couber
    parciais.sort(key=lambda b: -len(b))
    blocos = []
    for b in parciais:
        for bloco in blocos:
            if all(cabe(bloco, f) for f in b) and len(bloco) + len(b) <= min(
                [ALTURA_MAXIMA_FILEIRAS] + [f["altura"] for f in bloco + b]
            ):
                bloco.extend(b)
                break
        else:
            blocos.append(list(b))
    blocos.sort(key=lambda b: -len(b))

    # caixas soltas: vão para o ÚLTIMO pallet (ou novo, se não couber)
    for solta in soltas_por_tipo:
        for bloco in reversed(blocos):
            if cabe(bloco, solta):
                bloco.append(solta)
                break
        else:
            blocos.append([solta])

    # Exportação: pallet com sobras deve ter, sempre que possível, ao menos
    # 2 fileiras COMPLETAS. Se faltar, traz fileiras completas de outros pallets
    # (primeiro dos pallets de sobras; depois dos pallets mistos; por último dos
    # pallets sequenciais de SKU único), sem deixar o doador com menos de 2 fileiras.
    TIPO_REAJUSTADO = "Pallet Fechado - fileiras completas (reajustado) 🟢"
    TIPO_SEQ_OU_MISTO = {TIPO_SEQUENCIAL: 2, TIPO_MESMA_ALTURA: 1, TIPO_ALTURAS_DIFERENTES: 1}

    for bloco in reversed(blocos):
        while sum(1 for f in bloco if not f.get("solta")) < 2:
            tipos_bloco = {f["tipo"] for f in bloco}
            alt_bloco = min([ALTURA_MAXIMA_FILEIRAS] + [f["altura"] for f in bloco])
            # 1) doadores: pallets de sobras (listas de fileiras)
            candidatos = []
            for doador in fechados_sobras:
                if len(doador) <= 2:
                    continue
                for f in doador:
                    if cabe(bloco, f):
                        prioridade = (
                            0, 0 if f["tipo"] in tipos_bloco else 1,
                            0 if f["altura"] == alt_bloco else 1, -len(doador),
                        )
                        candidatos.append((prioridade, doador, f))
            if candidatos:
                _, doador, f = min(candidatos, key=lambda c: c[0])
                doador.remove(f)
                bloco.append(f)
                continue
            # 2) doadores: pallets já formados nas etapas 1 e 2
            candidatos = []
            for idx_p, pal in enumerate(pallets):
                if pal["tipo"] not in TIPO_SEQ_OU_MISTO and pal["tipo"] != TIPO_REAJUSTADO:
                    continue
                if fileiras_do_lote(pal["itens"]) <= 2:
                    continue
                for sku, qtd in pal["itens"].items():
                    s = skus[sku]
                    if qtd < s["Caixas_Por_Fileira"]:
                        continue
                    f = {"tipo": s["Ordem_Caixa"], "altura": s["Altura"],
                         "itens": {sku: s["Caixas_Por_Fileira"]}}
                    if cabe(bloco, f):
                        prioridade = (
                            TIPO_SEQ_OU_MISTO.get(pal["tipo"], 1),
                            0 if s["Ordem_Caixa"] in tipos_bloco else 1,
                            0 if s["Altura"] == alt_bloco else 1, -idx_p,
                        )
                        candidatos.append((prioridade, pal, sku, f))
            if not candidatos:
                break
            _, pal, sku, f = min(candidatos, key=lambda c: c[0])
            pal["itens"][sku] -= f["itens"][sku]
            if pal["itens"][sku] == 0:
                del pal["itens"][sku]
            pal["tipo"] = TIPO_REAJUSTADO
            bloco.append(f)

    for fileiras_pallet_sobras in fechados_sobras:
        novo_pallet(TIPO_FILEIRAS_SOBRAS, juntar(fileiras_pallet_sobras))
    for bloco in blocos:
        novo_pallet(TIPO_FINAL, juntar(bloco))

    # --- Estrutura final para exibição e relatórios ---
    linhas = []
    for idx, p in enumerate(pallets, 1):
        itens_ord = sorted(
            p["itens"].items(), key=lambda kv: (-skus[kv[0]]["Ordem_Caixa"], kv[0])
        )
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
            })
    return pd.DataFrame(linhas)


# --- 7. GERADOR DE PDF COM CONTROLE DE QUEBRA DE PÁGINA ---
def gerar_pdf(df_pallets, cliente, data_str):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "MUSTAD - Relatório de Paletização", align="C")
    pdf.ln(7)

    nome_cliente_formatado = cliente.strip() if cliente else "Não Informado"
    cliente_pdf = nome_cliente_formatado.encode("latin-1", "replace").decode("latin-1")

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Cliente: {cliente_pdf}", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Data de Emissão: {data_str}", align="C")
    pdf.ln(12)

    pallets_ordenados = df_pallets.sort_values("Pallet_Num")["ID"].unique()

    for p_id in pallets_ordenados:
        df_p = df_pallets[df_pallets["ID"] == p_id]
        tipo_raw = str(df_p["Tipo"].iloc[0])
        tipo_limpo = (
            tipo_raw.replace("🟢", "").replace("🟡", "").replace("🟠", "").strip()
        )
        total_cx = int(df_p["Qtd Caixas"].sum())
        total_pecas = int(df_p["Total Peças"].sum())

        linhas_tabela = len(df_p)
        altura_bloco = 20 + (linhas_tabela + 1) * 6

        if pdf.get_y() + altura_bloco > 270:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(
            0,
            8,
            f"{p_id} | Tipo: {tipo_limpo} | Total de Caixas: {total_cx} cx ({total_pecas} peças)",
            border="B",
        )
        pdf.ln(10)

        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(25, 6, "SKU", border=1)
        pdf.cell(65, 6, "Produto", border=1)
        pdf.cell(18, 6, "N. Caixa", border=1)
        pdf.cell(20, 6, "Qtd Caixas", border=1)
        pdf.cell(22, 6, "Qtd Peças", border=1)
        pdf.cell(20, 6, "Cx/Fileira", border=1)
        pdf.cell(20, 6, "Fileiras", border=1)
        pdf.ln()

        pdf.set_font("Helvetica", size=8)
        for _, row in df_p.iterrows():
            prod_nome = (
                str(row["Produto"])
                .encode("latin-1", "replace")
                .decode("latin-1")[:32]
            )
            pdf.cell(25, 6, str(row["SKU"]), border=1)
            pdf.cell(65, 6, prod_nome, border=1)
            pdf.cell(18, 6, str(row["Nº Caixa"]), border=1)
            pdf.cell(20, 6, str(row["Qtd Caixas"]), border=1)
            pdf.cell(22, 6, str(row["Total Peças"]), border=1)
            pdf.cell(20, 6, str(row["Caixas_Por_Fileira"]), border=1)
            pdf.cell(20, 6, str(row["Quantidade_Fileiras"]), border=1)
            pdf.ln()

        pdf.ln(6)

    return bytes(pdf.output())


# --- 8. EXECUÇÃO E RESULTADOS ---
if st.button("⚙️ CALCULAR E GERAR PALLETS"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

if st.session_state.processado and st.session_state.carrinho:
    df_pallets = processar_pallets_operador(
        st.session_state.carrinho, df_produtos
    )

    st.subheader("📦 Detalhamento Individual por Pallet")
    pallets_unicos = (
        df_pallets.sort_values("Pallet_Num")["ID"].unique()
    )
    st.success(f"**Total de Pallets Gerados:** {len(pallets_unicos)}")

    if FPDF_DISPONIVEL:
        try:
            data_atual = datetime.now()
            data_formatada_pdf = data_atual.strftime("%d/%m/%Y")
            data_formatada_arquivo = data_atual.strftime("%d-%m-%Y")

            cliente_informado = nome_cliente_input.strip()
            cliente_limpo = (
                re.sub(r'[\\/*?:"<>|]', "", cliente_informado)
                if cliente_informado
                else "CLIENTE"
            )

            nome_arquivo_pdf = (
                f"PALETIZACAO_{cliente_limpo}_{data_formatada_arquivo}.pdf"
            )

            pdf_bytes = gerar_pdf(
                df_pallets, cliente_informado, data_formatada_pdf
            )

            st.download_button(
                label="📄 Baixar Relatório em PDF",
                data=pdf_bytes,
                file_name=nome_arquivo_pdf,
                mime="application/pdf",
                key="download_pdf_btn",
            )
        except Exception as err:
            st.error(f"Erro ao gerar PDF: {err}")

    st.markdown("---")

    for p_id in pallets_unicos:
        df_p = df_pallets[df_pallets["ID"] == p_id]
        tipo_pallet = df_p["Tipo"].iloc[0]
        total_cx = int(df_p["Qtd Caixas"].sum())
        total_pc = int(df_p["Total Peças"].sum())

        with st.expander(
            f"📌 {p_id} - Total de Caixas: {total_cx} cx | Total de Peças: {total_pc} peças | {int(df_p['Fileiras no Pallet'].iloc[0])} fileiras ({tipo_pallet})",
            expanded=True,
        ):
            st.markdown(
                "**Composição detalhada (organizada da base para o topo - fileiras completas e ordenadas por numeração de caixa):**"
            )
            st.dataframe(
                df_p[[
                    "SKU",
                    "Produto",
                    "Nº Caixa",
                    "Qtd Caixas",
                    "Total Peças",
                    "Fileiras no Pallet",
                    "Caixas_Por_Fileira",
                    "Quantidade_Fileiras",
                ]],
                use_container_width=True,
            )

            str_destaque = f"""
                <div style="text-align: right;">
                    <span class="total-caixas-destaque">📦 Total de Caixas do Pallet: {total_cx} cx</span>
                </div>
                """
            st.markdown(str_destaque, unsafe_allow_html=True)
