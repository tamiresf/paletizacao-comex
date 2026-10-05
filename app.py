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


# --- 6. ALGORITMO COMEX - REGRAS SEQUENCIAIS, TIPO DE CAIXA E ALTURA ---
def processar_pallets_operador(carrinho, df_produtos):
    estoque_por_sku = {}
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]
        estoque_por_sku[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": int(prod.get("Ordem_Caixa", 0)),
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"]),
            "Quantidade_Fileiras": min(int(prod["ALTURA"]), 5),  # Respeita teto de 5 fileiras
            "Capacidade_Max": int(prod["QUANTIDADE DE CAIXAS NO PALLET"]),
            "Qtd_Disponivel": int(item["Qtd_Caixas"])
        }

    pallets_gerados = []

    # ETAPA 1: Gerar pallets completos e sequenciais por SKU individual (fechando lotes máximos)
    skus_lista = list(estoque_por_sku.values())
    skus_lista.sort(key=lambda x: (x["Ordem_Caixa"], x["Qtd_Disponivel"]), reverse=True)

    for s in skus_lista:
        cap_max = s["Capacidade_Max"]
        while s["Qtd_Disponivel"] >= cap_max:
            lote_pallet = []
            for _ in range(cap_max):
                lote_pallet.append({
                    "SKU": s["SKU"],
                    "Produto": s["Produto"],
                    "Nº Caixa": s["Nº Caixa"],
                    "Ordem_Caixa": s["Ordem_Caixa"],
                    "Pecas_Por_Caixa": s["Pecas_Por_Caixa"],
                    "Caixas_Por_Fileira": s["Caixas_Por_Fileira"],
                    "Quantidade_Fileiras": s["Quantidade_Fileiras"],
                    "Capacidade_Max": cap_max
                })
                s["Qtd_Disponivel"] -= 1
            pallets_gerados.append(lote_pallet)

    # ETAPA 2: Formar pallets mistos priorizando RIGOROSAMENTE o mesmo Tipo de Caixa e a Mesma Altura
    # Agrupando por Tipo de Caixa (Ordem_Caixa)
    tipos_caixa_unicos = sorted(list(set(s["Ordem_Caixa"] for s in estoque_por_sku.values())), reverse=True)

    for tipo_cx in tipos_caixa_unicos:
        skus_deste_tipo = [s for s in estoque_por_sku.values() if s["Ordem_Caixa"] == tipo_cx and s["Qtd_Disponivel"] > 0]
        if not skus_deste_tipo:
            continue

        # Sub-etapa 2.1: Tentar agrupar por MESMA ALTURA dentro do mesmo tipo de caixa
        alturas_unicas = sorted(list(set(s["Quantidade_Fileiras"] for s in skus_deste_tipo)), reverse=True)
        for alt in alturas_unicas:
            skus_mesma_altura = [s for s in skus_deste_tipo if s["Quantidade_Fileiras"] == alt and s["Qtd_Disponivel"] >= s["Caixas_Por_Fileira"]]
            if not skus_mesma_altura:
                continue

            cap_max_ref = skus_mesma_altura[0]["Capacidade_Max"]
            continuar_alt = True
            while continuar_alt:
                continuar_alt = False
                lote_pallet = []
                for s in skus_mesma_altura:
                    cx_fileira = s["Caixas_Por_Fileira"]
                    while s["Qtd_Disponivel"] >= cx_fileira and len(lote_pallet) + cx_fileira <= cap_max_ref:
                        for _ in range(cx_fileira):
                            lote_pallet.append({
                                "SKU": s["SKU"],
                                "Produto": s["Produto"],
                                "Nº Caixa": s["Nº Caixa"],
                                "Ordem_Caixa": s["Ordem_Caixa"],
                                "Pecas_Por_Caixa": s["Pecas_Por_Caixa"],
                                "Caixas_Por_Fileira": s["Caixas_Por_Fileira"],
                                "Quantidade_Fileiras": s["Quantidade_Fileiras"],
                                "Capacidade_Max": cap_max_ref
                            })
                            s["Qtd_Disponivel"] -= 1
                        continuar_alt = True

                if len(lote_pallet) >= cx_fileira and len(lote_pallet) <= cap_max_ref:
                    # Se fechou uma fileira ou pallet consistente
                    if len(lote_pallet) == cap_max_ref or not any(s["Qtd_Disponivel"] >= s["Caixas_Por_Fileira"] for s in skus_mesma_altura):
                        pallets_gerados.append(lote_pallet)
                    else:
                        # Devolve se não compensar
                        for item in lote_pallet:
                            for s in skus_mesma_altura:
                                if s["SKU"] == item["SKU"]:
                                    s["Qtd_Disponivel"] += 1
                        break

        # Sub-etapa 2.2: Esgotadas as combinações de altura exata, permite misturar alturas DIFERENTES mas estritamente do MESMO TIPO DE CAIXA
        skus_restantes_tipo = [s for s in skus_deste_tipo if s["Qtd_Disponivel"] >= s["Caixas_Por_Fileira"]]
        if skus_restantes_tipo:
            cap_max_ref = skus_restantes_tipo[0]["Capacidade_Max"]
            continuar_tipo = True
            while continuar_tipo:
                continuar_tipo = False
                lote_pallet = []
                for s in skus_restantes_tipo:
                    cx_fileira = s["Caixas_Por_Fileira"]
                    while s["Qtd_Disponivel"] >= cx_fileira and len(lote_pallet) + cx_fileira <= cap_max_ref:
                        for _ in range(cx_fileira):
                            lote_pallet.append({
                                "SKU": s["SKU"],
                                "Produto": s["Produto"],
                                "Nº Caixa": s["Nº Caixa"],
                                "Ordem_Caixa": s["Ordem_Caixa"],
                                "Pecas_Por_Caixa": s["Pecas_Por_Caixa"],
                                "Caixas_Por_Fileira": s["Caixas_Por_Fileira"],
                                "Quantidade_Fileiras": s["Quantidade_Fileiras"],
                                "Capacidade_Max": cap_max_ref
                            })
                            s["Qtd_Disponivel"] -= 1
                        continuar_tipo = True
                
                if len(lote_pallet) > 0:
                    pallets_gerados.append(lote_pallet)
                    continuar_tipo = True

    # ETAPA 3: Tratamento rigoroso do Último Pallet (Alocação das sobras finais de caixas)
    sobras_finais = []
    for s in estoque_por_sku.values():
        if s["Qtd_Disponivel"] > 0:
            for _ in range(s["Qtd_Disponivel"]):
                sobras_finais.append({
                    "SKU": s["SKU"],
                    "Produto": s["Produto"],
                    "Nº Caixa": s["Nº Caixa"],
                    "Ordem_Caixa": s["Ordem_Caixa"],
                    "Pecas_Por_Caixa": s["Pecas_Por_Caixa"],
                    "Caixas_Por_Fileira": s["Caixas_Por_Fileira"],
                    "Quantidade_Fileiras": s["Quantidade_Fileiras"],
                    "Capacidade_Max": s["Capacidade_Max"]
                })
            s["Qtd_Disponivel"] = 0

    if sobras_finais:
        sobras_finais.sort(key=lambda x: (x["Ordem_Caixa"], x["SKU"]), reverse=True)
        cap_max_padrao = sobras_finais[0]["Capacidade_Max"] if sobras_finais else 32
        
        while len(sobras_finais) > cap_max_padrao:
            lote_parcial = sobras_finais[:cap_max_padrao]
            sobras_finais = sobras_finais[cap_max_padrao:]
            pallets_gerados.append(lote_parcial)
            
        if sobras_finais:
            pallets_gerados.append(sobras_finais)

    # Consolidar estrutura final para exibição e relatórios
    pallets_bruto = []
    for idx, lote in enumerate(pallets_gerados, 1):
        sku_counts = {}
        for item in lote:
            sku = item["SKU"]
            if sku not in sku_counts:
                sku_counts[sku] = {
                    "SKU": sku,
                    "Produto": item["Produto"],
                    "Nº Caixa": item["Nº Caixa"],
                    "Ordem_Caixa": item["Ordem_Caixa"],
                    "Qtd Caixas": 0,
                    "Total Peças": 0,
                    "Caixas_Por_Fileira": item["Caixas_Por_Fileira"],
                    "Quantidade_Fileiras": item["Quantidade_Fileiras"],
                    "Capacidade_Max": item["Capacidade_Max"]
                }
            sku_counts[sku]["Qtd Caixas"] += 1
            sku_counts[sku]["Total Peças"] += item["Pecas_Por_Caixa"]

        total_cx_lote = sum(i["Qtd Caixas"] for i in sku_counts.values())
        cap_max_lote = list(sku_counts.values())[0]["Capacidade_Max"]
        is_ultimo = (idx == len(pallets_gerados) and total_cx_lote < cap_max_lote)
        
        if is_ultimo:
            tipo_p = "Pallet Final Fracionado (Contém Incompletudes/Buracos) 🟠"
        else:
            tipo_p = "Pallet Fechado (Fileiras Exatas) 🟢"

        pallet_label = f"Pallet {idx:02d}"
        for s_info in sku_counts.values():
            pallets_bruto.append({
                "Pallet_Num": idx,
                "ID": pallet_label,
                "Tipo": tipo_p,
                **s_info
            })

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
        .sort_values(by=["Pallet_Num", "Ordem_Caixa"], ascending=[True, False])
    )

    return df_consolidado


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
            f"📌 {p_id} - Total de Caixas: {total_cx} cx | Total de Peças: {total_pc} peças ({tipo_pallet})",
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
