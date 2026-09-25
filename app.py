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
            "Nº Caixa": prod_info["NUMERO DA CAIXA"],
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


# --- 6. ALGORITMO DE PALETIZAÇÃO DE EXPORTAÇÃO (MÁXIMA OTIMIZAÇÃO POR BLOCO DE CAIXA) ---
def processar_pallets_operador(carrinho, df_produtos):
    pallets_bruto = []
    pallet_num = 1
    
    pedidos_por_num_caixa = {}

    for item in carrinho:
        sku = str(item["SKU"]).strip()
        qtd_total_caixas = int(item["Qtd_Caixas"])
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]

        cap_max_caixas = int(prod["QUANTIDADE DE CAIXAS NO PALLET"])
        ordem_cx = int(prod.get("Ordem_Caixa", 0))
        num_caixa = str(prod["NUMERO DA CAIXA"]).strip()
        pecas_por_caixa = int(prod["QUANTIDADE DE PEÇAS"])
        caixas_por_fileira = int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"])
        quantidade_fileiras = int(prod["ALTURA"])

        if num_caixa not in pedidos_por_num_caixa:
            pedidos_por_num_caixa[num_caixa] = []

        pedidos_por_num_caixa[num_caixa].append({
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Qtd_Total": qtd_total_caixas,
            "Capacidade_Max": cap_max_caixas,
            "Ordem_Caixa": ordem_cx,
            "Nº Caixa": num_caixa,
            "Pecas_Por_Caixa": pecas_por_caixa,
            "Caixas_Por_Fileira": caixas_por_fileira,
            "Quantidade_Fileiras": quantidade_fileiras,
        })

    num_caixas_ordenadas = sorted(
        pedidos_por_num_caixa.keys(),
        key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0,
        reverse=True
    )

    for num_cx in num_caixas_ordenadas:
        itens_da_caixa = pedidos_por_num_caixa[num_cx]
        caixas_individuais = []
        
        for prod_item in itens_da_caixa:
            cap_max = prod_item["Capacidade_Max"]
            for _ in range(prod_item["Qtd_Total"]):
                caixas_individuais.append({
                    "SKU": prod_item["SKU"],
                    "Produto": prod_item["Produto"],
                    "Nº Caixa": prod_item["Nº Caixa"],
                    "Ordem_Caixa": prod_item["Ordem_Caixa"],
                    "Pecas_Por_Caixa": prod_item["Pecas_Por_Caixa"],
                    "Caixas_Por_Fileira": prod_item["Caixas_Por_Fileira"],
                    "Quantidade_Fileiras": prod_item["Quantidade_Fileiras"],
                    "Capacidade_Max": cap_max,
                })

        if not caixas_individuais:
            continue

        cap_alvo = caixas_individuais[0]["Capacidade_Max"]
        pallets_deste_bloco = []

        # Separa em lotes exatos da capacidade máxima do pallet para este tipo de caixa
        while len(caixas_individuais) >= cap_alvo:
            lote_cheio = caixas_individuais[:cap_alvo]
            caixas_individuais = caixas_individuais[cap_alvo:]
            pallets_deste_bloco.append(lote_cheio)

        # Se houver sobra final menor que a capacidade, aplicamos o algoritmo de absorção inteligente
        if caixas_individuais:
            if pallets_deste_bloco:
                # Tenta absorver as caixas restantes distribuindo no último pallet aberto do mesmo bloco
                ultimo_pallet = pallets_deste_bloco[-1]
                espaco_livre = cap_alvo - len(ultimo_pallet)
                
                if len(caixas_individuais) <= espaco_livre + (cap_alvo * 0.3): # Flexibilidade controlada de otimização
                    ultimo_pallet.extend(caixas_individuais)
                    caixas_individuais = []
            
            if caixas_individuais:
                pallets_deste_bloco.append(caixas_individuais)

        # Constrói os pallets do bloco atual
        for lote in pallets_deste_bloco:
            sku_counts = {}
            for item in lote:
                s = item["SKU"]
                if s not in sku_counts:
                    sku_counts[s] = {
                        "SKU": s,
                        "Produto": item["Produto"],
                        "Nº Caixa": item["Nº Caixa"],
                        "Ordem_Caixa": item["Ordem_Caixa"],
                        "Qtd Caixas": 0,
                        "Total Peças": 0,
                        "Caixas_Por_Fileira": item["Caixas_Por_Fileira"],
                        "Quantidade_Fileiras": item["Quantidade_Fileiras"],
                    }
                sku_counts[s]["Qtd Caixas"] += 1
                sku_counts[s]["Total Peças"] += item["Pecas_Por_Caixa"]

            total_cx_lote = sum(i["Qtd Caixas"] for i in sku_counts.values())
            
            if total_cx_lote >= cap_alvo or (len(pallets_deste_bloco) == 1 and total_cx_lote >= (cap_alvo * 0.5)):
                tipo_p = "Misto Fechado 🟡" if len(sku_counts) > 1 else "Fechado 🟢"
            else:
                tipo_p = "Pallet Final (Fracionado) 🟠"

            pallet_label = f"Pallet {pallet_num:02d}"
            for s_info in sku_counts.values():
                pallets_bruto.append({
                    "Pallet_Num": pallet_num,
                    "ID": pallet_label,
                    "Tipo": tipo_p,
                    **s_info
                })
            pallet_num += 1

    df_temp = pd.DataFrame(pallets_bruto)
    if df_temp.empty:
        return df_temp

    df_consolidado = (
        df_temp.sort_values(
            by=["Pallet_Num", "Ordem_Caixa"], ascending=[True, False]
        )
        .groupby(
            [
                "Pallet_Num",
                "ID",
                "Tipo",
                "SKU",
                "Produto",
                "Nº Caixa",
                "Caixas_Por_Fileira",
                "Quantidade_Fileiras",
            ],
            as_index=False,
        )
        .agg({"Qtd Caixas": "sum", "Total Peças": "sum", "Ordem_Caixa": "first"})
    )

    return df_consolidado


# --- 7. GERADOR DE PDF ---
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
            f"📌 {p_id} - Total de Caixas: {total_cx} cx | Total de Peças: {total_pc} peças ({tipo_pallet})",
            expanded=True,
        ):
            st.markdown(
                "**Composição detalhada (organizada da base para o topo - caixas maiores embaixo, respeitando fileiras):**"
            )
            st.dataframe(
                df_p[[
                    "SKU",
                    "Produto",
                    "Nº Caixa",
                    "Qtd Caixas",
                    "Total Peças",
                    "Caixas_Por_Fileira",
                    "Quantidade_Fileiras",
                ]],
                use_container_width=True,
            )

            st.markdown(
                f"""
                <div style="text-align: right;">
                    <span class="total-caixas-destaque">📦 Total de Caixas do Pallet: {total_cx} cx</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
