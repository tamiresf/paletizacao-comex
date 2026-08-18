import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Importação do FPDF para geração de PDF
try:
    from fpdf import FPDF

    FPDF_DISPONIVEL = True
except ImportError:
    FPDF_DISPONIVEL = False

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Paletização 3D Real - COMEX",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Sistema de Paletização 3D - Montagem Operacional Real")
st.caption(
    "Pallet Fumigado (0,75m x 1,20m) | Arranjo Físico por Camadas, Amarração e Estabilidade"
)

# --- 2. CONSTANTES E DIMENSÕES DAS CAIXAS (em metros) ---
DIMENSOES_CAIXAS = {
    "CAIXA 0": {"comp": 0.230, "larg": 0.145, "alt": 0.125},
    "CAIXA 1": {"comp": 0.285, "larg": 0.155, "alt": 0.125},
    "CAIXA 2": {"comp": 0.295, "larg": 0.185, "alt": 0.130},
    "CAIXA 3": {"comp": 0.375, "larg": 0.195, "alt": 0.145},
}

PALLET_COMP = 1.20  # 1200 mm
PALLET_LARG = 0.75  # 750 mm


def obter_dimensoes_caixa(num_caixa):
    num_str = str(num_caixa).upper().strip()
    key = f"CAIXA {num_str}" if "CAIXA" not in num_str else num_str
    return DIMENSOES_CAIXAS.get(key, {"comp": 0.300, "larg": 0.200, "alt": 0.150})


def calcular_arranjo_camada(comp_cx, larg_cx, pallet_comp, pallet_larg):
    """Calcula o melhor padrão de encaixe por camada aproveitando a área do pallet."""
    # Opção A: Caixas alinhadas na orientação normal
    nx_a = max(1, int(np.floor(pallet_comp / comp_cx)))
    ny_a = max(1, int(np.floor(pallet_larg / larg_cx)))
    total_a = nx_a * ny_a

    # Opção B: Caixas alinhadas rotacionadas 90°
    nx_b = max(1, int(np.floor(pallet_comp / larg_cx)))
    ny_b = max(1, int(np.floor(pallet_larg / comp_cx)))
    total_b = nx_b * ny_b

    if total_b > total_a:
        return larg_cx, comp_cx, nx_b, ny_b
    return comp_cx, larg_cx, nx_a, ny_a


# --- 3. CARREGAMENTO DA BASE DE DADOS ---
@st.cache_data
def carregar_base(caminho_excel):
    df = pd.read_excel(caminho_excel)
    df.columns = df.columns.str.strip()
    df["SKU"] = df["SKU"].astype(str).str.strip()

    def extrair_num_caixa(val):
        try:
            return int(str(val).upper().replace("CAIXA", "").strip())
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
    st.error(f"Erro ao carregar a base de dados: {e}")
    st.stop()

# --- 4. ESTADO DA SESSÃO ---
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

if "processado" not in st.session_state:
    st.session_state.processado = False

# --- 5. INTERFACE LATERAL ---
st.sidebar.header("📋 Inserir Pedido")
opcoes_produtos = df_produtos["SKU"] + " - " + df_produtos["NOME DO PRODUTO"]
produto_selecionado = st.sidebar.selectbox(
    "Pesquisar Produto (SKU ou Nome):", options=opcoes_produtos
)

sku_sel = produto_selecionado.split(" - ")[0]
prod_info = df_produtos[df_produtos["SKU"] == sku_sel].iloc[0]

st.sidebar.info(f"""
**Informações do Cadastro:**  
• **Caixa Tipo:** {prod_info['NUMERO DA CAIXA']}  
• **Peças/Caixa:** {prod_info['QUANTIDADE DE PEÇAS']}  
• **Capacidade Pallet Fechado:** {prod_info['QUANTIDADE DE CAIXAS NO PALLET']} cx  
• **Dimensão Pallet:** 0,75m x 1,20m
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
        })
    st.session_state.processado = False
    st.sidebar.success("Item adicionado ao pedido!")

# --- 6. EXIBIÇÃO DO CARRINHO ---
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


# --- 7. ALGORITMO DE PALETIZAÇÃO E SEPARAÇÃO ---
def processar_pallets_operador(carrinho, df_produtos):
    pallets_lista = []
    pallet_id = 1
    sobras_por_sku = []

    for item in carrinho:
        sku = str(item["SKU"]).strip()
        qtd = int(item["Qtd_Caixas"])

        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]
        cap_pallet = int(prod["QUANTIDADE DE CAIXAS NO PALLET"])
        ordem_cx = int(prod.get("Ordem_Caixa", 0))
        num_caixa = str(prod["NUMERO DA CAIXA"]).strip()

        qtd_pallets_fechados = qtd // cap_pallet
        resto = qtd % cap_pallet

        for _ in range(qtd_pallets_fechados):
            pallets_lista.append({
                "ID": f"Pallet {pallet_id}",
                "Tipo": "Fechado 🟢",
                "SKU": sku,
                "Produto": prod["NOME DO PRODUTO"],
                "Qtd Caixas": cap_pallet,
                "Nº Caixa": num_caixa,
                "Ordem_Caixa": ordem_cx,
                "Capacidade_Max": cap_pallet,
            })
            pallet_id += 1

        if resto > 0:
            sobras_por_sku.append({
                "SKU": sku,
                "Produto": prod["NOME DO PRODUTO"],
                "Qtd Caixas": resto,
                "Nº Caixa": num_caixa,
                "Ordem_Caixa": ordem_cx,
                "Capacidade_Max": cap_pallet,
            })

    if sobras_por_sku:
        df_sobras = pd.DataFrame(sobras_por_sku)
        sobras_finais_para_misturar = []

        # Agrupa por tipo de caixa
        for ordem_cx, df_grupo in df_sobras.groupby("Ordem_Caixa"):
            num_caixa_tipo = df_grupo["Nº Caixa"].iloc[0]
            cap_max_tipo = df_grupo["Capacidade_Max"].iloc[0]
            fracao_unidade = 1.0 / cap_max_tipo

            pallet_mesmo_tipo_id = (
                f"Pallet {pallet_id} (Sobras - Caixa {num_caixa_tipo})"
            )
            capacidade_usada = 0.0
            itens_no_pallet_atual = []

            for _, row in df_grupo.iterrows():
                qtd_restante = row["Qtd Caixas"]

                while qtd_restante > 0:
                    espaco_disponivel = 1.0 - capacidade_usada
                    caixas_que_cabem = int(
                        np.floor((espaco_disponivel + 1e-9) / fracao_unidade)
                    )

                    if caixas_que_cabem == 0:
                        for it in itens_no_pallet_atual:
                            pallets_lista.append(it)
                        pallet_id += 1
                        pallet_mesmo_tipo_id = f"Pallet {pallet_id} (Sobras - Caixa {num_caixa_tipo})"
                        capacidade_usada = 0.0
                        itens_no_pallet_atual = []
                        caixas_que_cabem = cap_max_tipo

                    qtd_alocar = min(qtd_restante, caixas_que_cabem)
                    fracao_alocada = qtd_alocar * fracao_unidade

                    itens_no_pallet_atual.append({
                        "ID": pallet_mesmo_tipo_id,
                        "Tipo": "Misto (Mesma Caixa) 🟡",
                        "SKU": row["SKU"],
                        "Produto": row["Produto"],
                        "Qtd Caixas": qtd_alocar,
                        "Nº Caixa": row["Nº Caixa"],
                        "Ordem_Caixa": ordem_cx,
                        "Capacidade_Max": cap_max_tipo,
                    })

                    capacidade_usada += fracao_alocada
                    qtd_restante -= qtd_alocar

            if abs(capacidade_usada - 1.0) < 1e-6:
                for it in itens_no_pallet_atual:
                    pallets_lista.append(it)
                pallet_id += 1
            else:
                for it in itens_no_pallet_atual:
                    sobras_finais_para_misturar.append(it)

        # Último Pallet Misto
        if sobras_finais_para_misturar:
            df_ultimas_sobras = pd.DataFrame(sobras_finais_para_misturar)
            df_ultimas_sobras = df_ultimas_sobras.sort_values(
                by=["Ordem_Caixa", "SKU"], ascending=[False, True]
            )

            ultimo_pallet_id = f"Pallet {pallet_id} (Misto Final)"
            cap_usada_ultimo = 0.0

            for _, row in df_ultimas_sobras.iterrows():
                cap_max = row["Capacidade_Max"]
                fracao_unidade = 1.0 / cap_max
                qtd_restante = row["Qtd Caixas"]

                while qtd_restante > 0:
                    espaco_disponivel = 1.0 - cap_usada_ultimo
                    caixas_que_cabem = int(
                        np.floor((espaco_disponivel + 1e-9) / fracao_unidade)
                    )

                    if caixas_que_cabem == 0:
                        pallet_id += 1
                        ultimo_pallet_id = f"Pallet {pallet_id} (Misto Final)"
                        cap_usada_ultimo = 0.0
                        caixas_que_cabem = int(
                            np.floor((1.0 + 1e-9) / fracao_unidade)
                        )

                    qtd_alocar = min(qtd_restante, caixas_que_cabem)
                    fracao_alocada = qtd_alocar * fracao_unidade

                    pallets_lista.append({
                        "ID": ultimo_pallet_id,
                        "Tipo": "Misto Diversos 🟠",
                        "SKU": row["SKU"],
                        "Produto": row["Produto"],
                        "Qtd Caixas": qtd_alocar,
                        "Nº Caixa": row["Nº Caixa"],
                        "Ordem_Caixa": row["Ordem_Caixa"],
                        "Capacidade_Max": cap_max,
                    })

                    cap_usada_ultimo += fracao_alocada
                    qtd_restante -= qtd_alocar

    return pd.DataFrame(pallets_lista)


# --- 8. SIMULAÇÃO 3D FIDEDIGNA À REALIDADE ---
def gerar_grafico_3d_realista(df_pallet_especifico, titulo):
    fig = go.Figure()

    paleta_cores = [
        "#2563EB",
        "#059669",
        "#DC2626",
        "#7C3AED",
        "#D97706",
        "#0891B2",
    ]
    skus_unicos = df_pallet_especifico["SKU"].unique()
    cor_map = {
        sku: paleta_cores[i % len(paleta_cores)]
        for i, sku in enumerate(skus_unicos)
    }

    # Ordenação Física Real: Caixas maiores/pesadas em baixo, menores no topo
    df_ordenado = df_pallet_especifico.sort_values(
        by=["Ordem_Caixa", "SKU"], ascending=[False, True]
    )

    i_mesh = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j_mesh = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k_mesh = [0, 7, 2, 3, 6, 7, 1, 1, 1, 5, 2, 7]

    z_base_camada = 0.0
    camada_num = 0

    # Agrupa por tipo de caixa para garantir fiadas uniformes e planas
    for ordem_cx, grupo_tipo in df_ordenado.groupby(
        "Ordem_Caixa", sort=False
    ):
        num_caixa = grupo_tipo["Nº Caixa"].iloc[0]
        dims = obter_dimensoes_caixa(num_caixa)

        dx, dy, cols_x, cols_y = calcular_arranjo_camada(
            dims["comp"], dims["larg"], PALLET_COMP, PALLET_LARG
        )
        dz = dims["alt"]
        cap_por_camada = cols_x * cols_y

        offset_x = (PALLET_COMP - (cols_x * dx)) / 2.0
        offset_y = (PALLET_LARG - (cols_y * dy)) / 2.0

        # Monta a fila de caixas deste tipo
        fila_caixas = []
        for _, row in grupo_tipo.iterrows():
            for _ in range(int(row["Qtd Caixas"])):
                fila_caixas.append({"sku": row["SKU"], "cor": cor_map[row["SKU"]]})

        idx_cx = 0
        total_cx_tipo = len(fila_caixas)

        while idx_cx < total_cx_tipo:
            camada_num += 1
            # Amarração real: Alterna x e y em camadas pares do mesmo tipo de caixa
            inverter = camada_num % 2 == 0 and cols_x != cols_y

            for pos in range(cap_por_camada):
                if idx_cx >= total_cx_tipo:
                    break

                item = fila_caixas[idx_cx]

                if not inverter:
                    cx_i = pos % cols_x
                    cy_i = pos // cols_x
                    x_pos = offset_x + cx_i * dx
                    y_pos = offset_y + cy_i * dy
                    dim_x_box = dx
                    dim_y_box = dy
                else:
                    # Inversão para amarração de carga
                    cx_i = pos % cols_y
                    cy_i = pos // cols_y
                    x_pos = offset_y + cx_i * dy
                    y_pos = offset_x + cy_i * dx
                    dim_x_box = dy
                    dim_y_box = dx

                # Vértices do cubo 3D da caixa
                x_cube = [
                    x_pos,
                    x_pos + dim_x_box * 0.97,
                    x_pos + dim_x_box * 0.97,
                    x_pos,
                    x_pos,
                    x_pos + dim_x_box * 0.97,
                    x_pos + dim_x_box * 0.97,
                    x_pos,
                ]
                y_cube = [
                    y_pos,
                    y_pos,
                    y_pos + dim_y_box * 0.97,
                    y_pos + dim_y_box * 0.97,
                    y_pos,
                    y_pos,
                    y_pos + dim_y_box * 0.97,
                    y_pos + dim_y_box * 0.97,
                ]
                z_cube = [
                    z_base_camada,
                    z_base_camada,
                    z_base_camada,
                    z_base_camada,
                    z_base_camada + dz * 0.97,
                    z_base_camada + dz * 0.97,
                    z_base_camada + dz * 0.97,
                    z_base_camada + dz * 0.97,
                ]

                fig.add_trace(
                    go.Mesh3d(
                        x=x_cube,
                        y=y_cube,
                        z=z_cube,
                        i=i_mesh,
                        j=j_mesh,
                        k=k_mesh,
                        color=item["cor"],
                        flatshading=True,
                        lighting=dict(
                            ambient=0.8, diffuse=0.9, roughness=0.1
                        ),
                        hoverinfo="text",
                        text=f"<b>SKU:</b> {item['sku']}<br><b>Caixa:</b> {num_caixa}<br><b>Camada:</b> {camada_num}",
                        showscale=False,
                    )
                )

                idx_cx += 1

            z_base_camada += dz  # Sobe o nível para a próxima camada física

    # Desenho do Pallet de Madeira Fumigado
    fig.add_trace(
        go.Mesh3d(
            x=[0, PALLET_COMP, PALLET_COMP, 0, 0, PALLET_COMP, PALLET_COMP, 0],
            y=[0, 0, PALLET_LARG, PALLET_LARG, 0, 0, PALLET_LARG, PALLET_LARG],
            z=[-0.12, -0.12, -0.12, -0.12, 0, 0, 0, 0],
            i=i_mesh,
            j=j_mesh,
            k=k_mesh,
            color="#8B5A2B",
            opacity=0.9,
            hoverinfo="text",
            text="Pallet Fumigado (1.20m x 0.75m)",
            showscale=False,
        )
    )

    total_cx_pallet = int(df_pallet_especifico["Qtd Caixas"].sum())
    fig.update_layout(
        title=f"{titulo} ({total_cx_pallet} caixas)",
        scene=dict(
            xaxis=dict(
                title="Comprimento (1.20m)", range=[-0.05, 1.25], showgrid=True
            ),
            yaxis=dict(
                title="Largura (0.75m)", range=[-0.05, 0.80], showgrid=True
            ),
            zaxis=dict(title="Altura Carga (m)", showgrid=True),
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, b=0, t=35),
        showlegend=False,
    )
    return fig


# --- 9. GERADOR DE PDF ---
def gerar_pdf(df_pallets):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Relatorio de Paletizacao - COMEX", align="C")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 5, "Pallet Fumigado 0,75m x 1,20m", align="C")
    pdf.ln(12)

    for p_id in df_pallets["ID"].unique():
        df_p = df_pallets[df_pallets["ID"] == p_id]
        tipo_raw = str(df_p["Tipo"].iloc[0])
        tipo_limpo = (
            tipo_raw.replace("🟢", "")
            .replace("🟡", "")
            .replace("🟠", "")
            .strip()
        )
        total_cx = int(df_p["Qtd Caixas"].sum())

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(
            0,
            8,
            f"{p_id} | Tipo: {tipo_limpo} | Total: {total_cx} caixas",
            border="B",
        )
        pdf.ln(10)

        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 6, "SKU", border=1)
        pdf.cell(100, 6, "Produto", border=1)
        pdf.cell(25, 6, "N. Caixa", border=1)
        pdf.cell(25, 6, "Qtd Caixas", border=1)
        pdf.ln()

        pdf.set_font("Helvetica", size=9)
        for _, row in df_p.iterrows():
            prod_nome = (
                str(row["Produto"])
                .encode("latin-1", "replace")
                .decode("latin-1")[:45]
            )
            pdf.cell(30, 6, str(row["SKU"]), border=1)
            pdf.cell(100, 6, prod_nome, border=1)
            pdf.cell(25, 6, str(row["Nº Caixa"]), border=1)
            pdf.cell(25, 6, str(row["Qtd Caixas"]), border=1)
            pdf.ln()

        pdf.ln(6)

    return bytes(pdf.output())


# --- 10. EXECUÇÃO ---
if st.button("⚙️ CALCULAR E GERAR PALLETS 3D"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

if st.session_state.processado and st.session_state.carrinho:
    df_pallets = processar_pallets_operador(
        st.session_state.carrinho, df_produtos
    )

    st.subheader("📦 Detalhamento e Arranjo 3D Realista")
    pallets_unicos = df_pallets["ID"].unique()
    st.success(f"**Total de Pallets Gerados:** {len(pallets_unicos)}")

    if FPDF_DISPONIVEL:
        try:
            pdf_bytes = gerar_pdf(df_pallets)
            st.download_button(
                label="📄 Baixar Relatório em PDF",
                data=pdf_bytes,
                file_name="plano_de_paletizacao.pdf",
                mime="application/pdf",
            )
        except Exception as err:
            st.error(f"Erro ao gerar PDF: {err}")

    st.markdown("---")

    for p_id in pallets_unicos:
        df_p = df_pallets[df_pallets["ID"] == p_id]
        tipo_pallet = df_p["Tipo"].iloc[0]
        total_cx = int(df_p["Qtd Caixas"].sum())

        with st.expander(
            f"📌 {p_id} - Total: {total_cx} caixas ({tipo_pallet})",
            expanded=True,
        ):
            col_tabela, col_3d = st.columns([1, 1])

            with col_tabela:
                st.markdown("**Composição da Carga:**")
                st.dataframe(
                    df_p[["SKU", "Produto", "Nº Caixa", "Qtd Caixas"]],
                    use_container_width=True,
                )

            with col_3d:
                fig_3d = gerar_grafico_3d_realista(
                    df_p, f"Montagem Realista - {p_id}"
                )
                st.plotly_chart(fig_3d, use_container_width=True)
