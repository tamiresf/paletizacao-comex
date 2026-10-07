from datetime import datetime
from fractions import Fraction
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

# --- 6. REGRA DE PALETIZAÇÃO COMEX (TRAVA DE 5 FILEIRAS E ALOCAÇÃO PENÚLTIMO/ÚLTIMO PALLET) ---
ALTURA_MAXIMA_GERAL = 5

TIPO_SEQUENCIAL = "Pallet Fechado - SKU único, sequencial"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura"
TIPO_FILEIRAS_SOBRAS = "Pallet Fechado - fileiras de sobras"
TIPO_FINAL = "Pallet Final (caixas soltas e sobras)"


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


def _gerar_pallets(carrinho, df_produtos):
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
            ALTURA_MAXIMA_GERAL,
        )
        skus[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": int(prod.get("Ordem_Caixa", 0)),
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": cx_fileira,
            "Altura": altura,
            "Capacidade_Max": min(cx_fileira * altura, int(prod["QUANTIDADE DE CAIXAS NO PALLET"])),
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

    ordem_skus = sorted(skus.values(), key=lambda s: (s["Ordem_Caixa"], s["SKU"]))

    # 1. PALLETS SEQUENCIAIS FECHADOS
    for s in ordem_skus:
        while s["Restante"] >= s["Capacidade_Max"]:
            novo_pallet(TIPO_SEQUENCIAL, {s["SKU"]: s["Capacidade_Max"]})
            s["Restante"] -= s["Capacidade_Max"]

    # 2. COMBINAÇÃO DE MESMO TIPO DE CAIXA/ALTURA
    tipos = sorted({s["Ordem_Caixa"] for s in skus.values()})
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

    # 3. FORMANDO FILEIRAS FECHADAS NO PENÚLTIMO PALLET A PARTIR DAS SOBRAS
    fileiras_completas_sobras = []
    caixas_soltas_acumuladas = {}

    for tipo in tipos:
        cpf = cx_fileira_do_tipo(tipo)
        sobras = [s for s in ordem_skus if s["Ordem_Caixa"] == tipo and s["Restante"] > 0]

        for s in sobras:
            n_fileiras_cheias = s["Restante"] // cpf
            resto_solto = s["Restante"] % cpf

            for _ in range(n_fileiras_cheias):
                fileiras_completas_sobras.append({
                    "tipo": tipo,
                    "altura": s["Altura"],
                    "itens": {s["SKU"]: cpf}
                })

            if resto_solto > 0:
                caixas_soltas_acumuladas[s["SKU"]] = caixas_soltas_acumuladas.get(s["SKU"], 0) + resto_solto

            s["Restante"] = 0

    # Tenta combinar caixas soltas do mesmo tipo para fechar fileiras completas adicionais
    if caixas_soltas_acumuladas:
        for tipo in tipos:
            cpf = cx_fileira_do_tipo(tipo)
            soltas_tipo = [sku for sku in caixas_soltas_acumuladas if skus[sku]["Ordem_Caixa"] == tipo]
            soma_cx = sum(caixas_soltas_acumuladas[sku] for sku in soltas_tipo)

            if soma_cx >= cpf:
                fileiras_formadas = soma_cx // cpf
                qtd_a_consumir = fileiras_formadas * cpf
                itens_fileira = {}

                for sku in soltas_tipo:
                    if qtd_a_consumir <= 0:
                        break
                    pega = min(caixas_soltas_acumuladas[sku], qtd_a_consumir)
                    itens_fileira[sku] = pega
                    caixas_soltas_acumuladas[sku] -= pega
                    qtd_a_consumir -= pega
                    if caixas_soltas_acumuladas[sku] == 0:
                        del caixas_soltas_acumuladas[sku]

                alt = min(skus[k]["Altura"] for k in itens_fileira)
                for _ in range(fileiras_formadas):
                    fileiras_completas_sobras.append({
                        "tipo": tipo,
                        "altura": alt,
                        "itens": itens_fileira
                    })

    def juntar(lista_fileiras):
        itens = {}
        for f in lista_fileiras:
            for sku, qtd in f["itens"].items():
                itens[sku] = itens.get(sku, 0) + qtd
        return itens

    # Empacota as fileiras de sobras sem estourar o limite de 5 fileiras por pallet
    curr_pallet_rows = []
    curr_fileiras_count = 0.0

    for f in fileiras_completas_sobras:
        limite_pallet = min(min([skus[sku]["Altura"] for sku in f["itens"].keys()]), ALTURA_MAXIMA_GERAL)

        if (curr_fileiras_count + 1.0 > limite_pallet) and curr_pallet_rows:
            novo_pallet(TIPO_FILEIRAS_SOBRAS, juntar(curr_pallet_rows))
            curr_pallet_rows = []
            curr_fileiras_count = 0.0

        curr_pallet_rows.append(f)
        curr_fileiras_count += 1.0

    if curr_pallet_rows:
        novo_pallet(TIPO_FILEIRAS_SOBRAS, juntar(curr_pallet_rows))

    # 4. ALOCAÇÃO EQUILIBRADA PARA O PENÚLTIMO E ÚLTIMO PALLET (Máx 5 Fileiras e Limite de Caixas)
    if caixas_soltas_acumuladas:
        sobras_restantes = dict(caixas_soltas_acumuladas)

        # Tenta aproveitar espaço livre no penúltimo pallet existente
        if pallets:
            penultimo = pallets[-1]
            cx_atuais = sum(penultimo["itens"].values())
            fileiras_atuais = fileiras_do_lote(penultimo["itens"])

            limite_fileiras_pen = min([skus[k]["Altura"] for k in penultimo["itens"].keys()] + [ALTURA_MAXIMA_GERAL])
            limite_cx_pen = min([skus[k]["Capacidade_Max"] for k in penultimo["itens"].keys()] + [100])

            espaco_fileiras = limite_fileiras_pen - fileiras_atuais
            espaco_cx = limite_cx_pen - cx_atuais

            if espaco_fileiras > 0 and espaco_cx > 0:
                for sku in list(sobras_restantes.keys()):
                    qtd = sobras_restantes[sku]
                    pode_pegar = min(qtd, espaco_cx)
                    if pode_pegar > 0:
                        penultimo["itens"][sku] = penultimo["itens"].get(sku, 0) + pode_pegar
                        sobras_restantes[sku] -= pode_pegar
                        espaco_cx -= pode_pegar
                        if sobras_restantes[sku] == 0:
                            del sobras_restantes[sku]

        # Sobras finais direcionadas ao ÚLTIMO PALLET respeitando no máximo 5 fileiras e capacidade
        if sobras_restantes:
            curr_ult_itens = {}
            curr_ult_cx = 0

            for sku in list(sobras_restantes.keys()):
                qtd = sobras_restantes[sku]
                cpf = skus[sku]["Caixas_Por_Fileira"]
                cap_max_sku = min(skus[sku]["Capacidade_Max"], cpf * ALTURA_MAXIMA_GERAL)

                while qtd > 0:
                    pode_colocar = min(qtd, cap_max_sku - curr_ult_cx)
                    if pode_colocar <= 0:
                        novo_pallet(TIPO_FINAL, curr_ult_itens)
                        curr_ult_itens = {}
                        curr_ult_cx = 0
                        pode_colocar = min(qtd, cap_max_sku)

                    curr_ult_itens[sku] = curr_ult_itens.get(sku, 0) + pode_colocar
                    curr_ult_cx += pode_colocar
                    qtd -= pode_colocar

            if curr_ult_itens:
                novo_pallet(TIPO_FINAL, curr_ult_itens)

    linhas = []
    for idx, p in enumerate(pallets, 1):
        def chave_empilhamento(kv):
            sku, qtd = kv
            s = skus[sku]
            return (s["Ordem_Caixa"], sku)

        itens_ord = sorted(p["itens"].items(), key=chave_empilhamento)
        fileiras_pallet = fileiras_do_lote(p["itens"])
        for sku, qtd in itens_ord:
            s = skus[sku]
            linhas.append({
                "Pallet_Num": idx,
                "ID": f"Pallet {idx}",
                "Tipo": p["tipo"],
                "SKU": sku,
                "Produto": s["Produto"],
                "Nº Caixa": s["Nº Caixa"],
                "Quantidade de Caixas": qtd,
                "Caixas por Fileira": s["Caixas_Por_Fileira"],
                "Altura (Fileiras)": s["Altura"],
                "Fileiras no Pallet": fileiras_pallet,
            })
    return pd.DataFrame(linhas)


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

        if pdf.get_y() + (len(df_p) * 7) + 25 > 275:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"Pallet {pn}", border="B")
        pdf.ln(8)

        headers = ["SKU", "Produto", "N. Cx", "Qtd Cx", "Cx / Fileira", "Altura"]
        larg = [30, 75, 20, 22, 25, 18]
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(235, 235, 235)

        for w, t in zip(larg, headers):
            pdf.cell(w, 6, t, border=1, fill=True, align="C")
        pdf.ln()

        for _, row in df_p.iterrows():
            pdf.set_font("Helvetica", size=8)
            pdf.cell(larg[0], 6, str(row["SKU"]), border=1)
            pdf.cell(larg[1], 6, _latin(row["Produto"])[:42], border=1)
            pdf.cell(larg[2], 6, str(row["Nº Caixa"]), border=1, align="C")
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(larg[3], 6, str(row["Quantidade de Caixas"]), border=1, align="C")
            pdf.set_font("Helvetica", size=8)
            pdf.cell(larg[4], 6, str(row["Caixas por Fileira"]), border=1, align="C")
            pdf.cell(larg[5], 6, str(row["Altura (Fileiras)"]), border=1, align="C")
            pdf.ln()

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, f"Quantidade de caixas no Pallet {pn}: {cx_pallet} caixas", align="R")
        pdf.ln(10)

    return bytes(pdf.output())


# --- 8. EXECUÇÃO E EXIBIÇÃO DE RESULTADOS ---
if st.button("⚙️ CALCULAR E GERAR PALLETS"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

if st.session_state.processado and st.session_state.carrinho:
    df_pallets = _gerar_pallets(st.session_state.carrinho, df_produtos)
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
                "Altura (Fileiras)",
            ]].copy()

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
