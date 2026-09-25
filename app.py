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


# --- 6. ALGORITMO DE PALETIZAÇÃO COM ABSORÇÃO DE SOBRAS (EVITA PALLETS VAZIOS) ---
def processar_pallets_operador(carrinho, df_produtos):
    pallets_bruto = []
    pallet_num = 1
    todas_as_caixas = []

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

        for _ in range(qtd_total_caixas):
            todas_as_caixas.append({
                "SKU": sku,
                "Produto": prod["NOME DO PRODUTO"],
                "Nº Caixa": num_caixa,
                "Ordem_Caixa": ordem_cx,
                "Pecas_Por_Caixa": pecas_por_caixa,
                "Caixas_Por_Fileira": caixas_por_fileira,
                "Quantidade_Fileiras": quantidade_fileiras,
                "Capacidade_Max_Caixas": cap_max_caixas,
            })

    if not todas_as_caixas:
        return pd.DataFrame()

    # Organiza em lotes por numeração de caixa
    caixas_por_tipo = {}
    for cx in todas_as_caixas:
        num_cx = cx["Nº Caixa"]
        if num_cx not in caixas_por_tipo:
            caixas_por_tipo[num_cx] = []
        caixas_por_tipo[num_cx].append(cx)

    tipos_ordenados = sorted(
        caixas_por_tipo.keys(),
        key=lambda x: int(re.sub(r"\D", "", x) or 0),
        reverse=True
    )

    # Lista para acumular todos os pallets formados
    pallets_em_construcao = []

    for num_cx in tipos_ordenados:
        lista_cx = caixas_por_tipo[num_cx]
        cap_pallet = lista_cx[0]["Capacidade_Max_Caixas"] if lista_cx else 64

        # 1. Cria pallets inteiros (cheios)
        while len(lista_cx) >= cap_pallet:
            lote_cheio = lista_cx[:cap_pallet]
            lista_cx = lista_cx[cap_pallet:]
            
            sku_counts = {}
            for item in lote_cheio:
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

            pallets_em_construcao.append({
                "itens": list(sku_counts.values()),
                "num_caixa": num_cx,
                "capacidade": cap_pallet,
                "fechado": True
            })

        # 2. O que sobrou deste tipo de caixa, guarda temporariamente
        if lista_cx:
            sku_counts = {}
            for item in lista_cx:
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

            pallets_em_construcao.append({
                "itens": list(sku_counts.values()),
                "num_caixa": num_cx,
                "capacidade": cap_pallet,
                "fechado": False
            })

    # TENTATIVA DE COMPACTAÇÃO: Encaixar sobras em pallets abertos do mesmo tamanho de caixa
    # Procura pallets não fechados e tenta passá-los para outros pallets que tenham espaço livre do mesmo tipo
    pallets_abertos = [p for p in pallets_em_construcao if not p["fechado"]]
    pallets_fechados = [p for p in pallets_em_construcao if p["fechado"]]

    # Se houver mais de um pallet aberto, tenta fundir os do mesmo tamanho de caixa
    if len(pallets_abertos) > 1:
        # Ordena abertos por tamanho de caixa para juntar os iguais
        pallets_abertos.sort(key=lambda x: x["num_caixa"])
        
        i = 0
        while i < len(pallets_abertos) - 1:
            p1 = pallets_abertos[i]
            p2 = pallets_abertos[i+1]
            
            # Se forem da mesma numeração de caixa, tenta fundir
            if p1["num_caixa"] == p2["num_caixa"]:
                total_cx_p1 = sum(item["Qtd Caixas"] for item in p1["itens"])
                total_cx_p2 = sum(item["Qtd Caixas"] for item in p2["itens"])
                
                # Se a soma couber na capacidade máxima do pallet, junta ambos em p1 e elimina p2
                if total_cx_p1 + total_cx_p2 <= p1["capacidade"]:
                    for item_p2 in p2["itens"]:
                        encontrado = False
                        for item_p1 in p1["itens"]:
                            if item_p1["SKU"] == item_p2["SKU"]:
                                item_p1["Qtd Caixas"] += item_p2["Qtd Caixas"]
                                item_p1["Total Peças"] += item_p2["Total Peças"]
                                encontrado = True
                                break
                        if not encontrado:
                            p1["itens"].append(item_p2)
                    
                    if total_cx_p1 + total_cx_p2 == p1["capacidade"]:
                        p1["fechado"] = True
                    
                    pallets_abertos.pop(i+1)
                    continue
            i += 1

    # Reconstri a lista final ordenada de pallets
    pallets_finais_ordenados = pallets_fechados + pallets_abertos

    for p in pallets_finais_ordenados:
        total_n_cx = sum(item["Qtd Caixas"] for item in p["itens"])
        if total_n_cx == p["capacidade"]:
            tipo_p = "Misto Fechado 🟡" if len(p["itens"]) > 1 else "Fechado 🟢"
        else:
            tipo_p = "Pallet Final (Fracionado) 🟠"

        pallet_label = f"Pallet {pallet_num:02d}"
        for s_info in p["itens"]:
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
