import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Importação condicional do FPDF
try:
    from fpdf import FPDF

    FPDF_DISPONIVEL = True
except ImportError:
    FPDF_DISPONIVEL = False

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Paletização 3D - COMEX", page_icon="📦", layout="wide"
)

st.title("📦 Sistema de Paletização e Visualização 3D")
st.caption(
    "Pallet Fumigado (0,75m x 1,20m) — Regra de Separação Estreita de Tipos de Caixas"
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


def obter_melhor_orientacao(comp, larg, p_comp, p_larg):
    nx1 = max(1, int(np.floor(p_comp / comp)))
    ny1 = max(1, int(np.floor(p_larg / larg)))

    nx2 = max(1, int(np.floor(p_comp / larg)))
    ny2 = max(1, int(np.floor(p_larg / comp)))

    if (nx2 * ny2) > (nx1 * ny1):
        return larg, comp, nx2, ny2
    return comp, larg, nx1, ny1


# --- 3. CARREGAMENTO DE DADOS ---
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


# Localização do arquivo Excel
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
    st.info(
        "Certifique-se de que o arquivo 'COMEX.xlsx' está salvo na raiz do projeto ou na pasta 'data/'."
    )
    st.stop()

try:
    df_produtos = carregar_base(CAMINHO_EXCEL)
except Exception as e:
    st.error(f"Erro ao carregar a base de dados ({CAMINHO_EXCEL}): {e}")
    st.stop()

# --- 4. ESTADO DA SESSÃO ---
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

if "processado" not in st.session_state:
    st.session_state.processado = False

# --- 5. PAINEL LATERAL (INSERÇÃO DO PEDIDO) ---
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

# --- 6. EXIBIÇÃO DO CARRINHO DE COMPRAS ---
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


# --- 7. ALGORITMO DE PALETIZAÇÃO ---
def processar_pallets_operador(carrinho, df_produtos):
    pallets_lista = []
    pallet_id = 1
    sobras_por_sku = []

    # 1. Pallets Fechados e Separação das Sobras
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        qtd = int(item["Qtd_Caixas"])

        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]
        cap_pallet = int(prod["QUANTIDADE DE CAIXAS NO PALLET"])
        ordem_cx = int(prod.get("Ordem_Caixa", 0))
        num_caixa = str(prod["NUMERO DA CAIXA"]).strip()

        qtd_pallets_fechados = qtd // cap_pallet
        resto = qtd % cap_pallet

        # Pallets Monoproduto Fechados
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

    # 2. Consolidação Exclusiva por Tipo de Caixa
    if sobras_por_sku:
        df_sobras = pd.DataFrame(sobras_por_sku)
        sobras_finais_para_misturar = []

        # Agrupa por tipo de caixa (Ordem_Caixa)
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
                        # Pallet cheio do mesmo tipo
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

            # Se o pallet do mesmo tipo encheu 100%, consolida.
            if abs(capacidade_usada - 1.0) < 1e-6:
                for it in itens_no_pallet_atual:
                    pallets_lista.append(it)
                pallet_id += 1
            else:
                # Armazena as sobras remanescentes deste tipo de caixa
                for it in itens_no_pallet_atual:
                    sobras_finais_para_misturar.append(it)

        # 3. ÚLTIMO PALLET MISTO (Sobras incompletas de tipos diferentes)
        if sobras_finais_para_misturar:
            df_ultimas_sobras = pd.DataFrame(sobras_finais_para_misturar)
            df_ultimas_sobras = df_ultimas_sobras.sort_values(
                by=["Ordem_Caixa", "SKU"]
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


# --- 8. GERADOR DE MODELO 3D ---
def gerar_grafico_3d_otimizado(df_pallet_especifico, titulo):
    fig = go.Figure()

    paleta_cores = [
        "#3B82F6",
        "#10B981",
        "#EF4444",
        "#8B5CF6",
        "#F59E0B",
        "#D9A036",
    ]
    skus_unicos = df_pallet_especifico["SKU"].unique()
    cor_map = {
        sku: paleta_cores[i % len(paleta_cores)]
        for i, sku in enumerate(skus_unicos)
    }

    df_ordenado = df_pallet_especifico.sort_values(
        by=["Ordem_Caixa", "SKU"], ascending=[False, True]
    )

    lista_caixas_individuais = []
    for _, row in df_ordenado.iterrows():
        sku = row["SKU"]
        qtd = int(row["Qtd Caixas"])
        cor = cor_map[sku]
        cx_nome = row["Nº Caixa"]
        dims = obter_dimensoes_caixa(cx_nome)
        ordem = row["Ordem_Caixa"]

        for _ in range(qtd):
            lista_caixas_individuais.append({
                "sku": sku,
                "cor": cor,
                "cx_nome": cx_nome,
                "ordem": ordem,
                "dims": dims,
            })

    if not lista_caixas_individuais:
        return fig

    x_cube = [0, 1, 1, 0, 0, 1, 1, 0]
    y_cube = [0, 0, 1, 1, 0, 0, 1, 1]
    z_cube = [0, 0, 0, 0, 1, 1, 1, 1]
    i_mesh = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j_mesh = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k_mesh = [0, 7, 2, 3, 6, 7, 1, 1, 1, 5, 2, 7]

    z_atual = 0.0
    idx = 0
    total_caixas = len(lista_caixas_individuais)

    while idx < total_caixas:
        cx_referencia = lista_caixas_individuais[idx]
        dims = cx_referencia["dims"]

        dx, dy, cols_x, cols_y = obter_melhor_orientacao(
            dims["comp"], dims["larg"], PALLET_COMP, PALLET_LARG
        )
        dz = dims["alt"]
        caixas_por_camada = max(1, cols_x * cols_y)

        offset_x = (PALLET_COMP - (cols_x * dx)) / 2.0
        offset_y = (PALLET_LARG - (cols_y * dy)) / 2.0

        qtd_camada = min(total_caixas - idx, caixas_por_camada)

        for i in range(qtd_camada):
            item = lista_caixas_individuais[idx + i]
            cx_i = i % cols_x
            cy_i = i // cols_x

            x0 = offset_x + cx_i * dx
            y0 = offset_y + cy_i * dy

            x_box = [x0 + vx * (dx * 0.98) for vx in x_cube]
            y_box = [y0 + vy * (dy * 0.98) for vy in y_cube]
            z_box = [z_atual + vz * dz for vz in z_cube]

            fig.add_trace(
                go.Mesh3d(
                    x=x_box,
                    y=y_box,
                    z=z_box,
                    i=i_mesh,
                    j=j_mesh,
                    k=k_mesh,
                    color=item["cor"],
                    flatshading=True,
                    lighting=dict(ambient=0.85, diffuse=0.9),
                    hoverinfo="text",
                    text=f"<b>SKU:</b> {item['sku']}<br><b>Tipo:</b> {item['cx_nome']}<br><b>Dimensões:</b> {int(dx*1000)}x{int(dy*1000)}x{int(dz*1000)} mm",
                    showscale=False,
                )
            )

        idx += qtd_camada
        z_atual += dz

    # Base do Pallet de Madeira
    fig.add_trace(
        go.Mesh3d(
            x=[0, PALLET_COMP, PALLET_COMP, 0, 0, PALLET_COMP, PALLET_COMP, 0],
            y=[0, 0, PALLET_LARG, PALLET_LARG, 0, 0, PALLET_LARG, PALLET_LARG],
            z=[-0.05, -0.05, -0.05, -0.05, 0, 0, 0, 0],
            i=i_mesh,
            j=j_mesh,
            k=k_mesh,
            color="#7C4700",
            opacity=0.8,
            hoverinfo="none",
            showscale=False,
        )
    )

    fig.update_layout(
        title=f"{titulo} ({total_caixas} caixas)",
        scene=dict(
            xaxis=dict(title="Comp (1.20m)", showgrid=True),
            yaxis=dict(title="Larg (0.75m)", showgrid=True),
            zaxis=dict(title="Alt (m)", showgrid=True),
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

    # Título
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Relatorio de Paletizacao - COMEX", align="C")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 5, "Pallet Fumigado 0,75m x 1,20m", align="C")
    pdf.ln(12)

    pallets_unicos = df_pallets["ID"].unique()

    for p_id in pallets_unicos:
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

        # Cabeçalho da Tabela
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 6, "SKU", border=1)
        pdf.cell(100, 6, "Produto", border=1)
        pdf.cell(25, 6, "N. Caixa", border=1)
        pdf.cell(25, 6, "Qtd Caixas", border=1)
        pdf.ln()

        # Linhas da Tabela
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


# --- 10. EXECUÇÃO E RESULTADOS ---
if st.button("⚙️ CALCULAR E GERAR PALLETS 3D"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

if st.session_state.processado and st.session_state.carrinho:
    df_pallets = processar_pallets_operador(
        st.session_state.carrinho, df_produtos
    )

    st.subheader("📦 Detalhamento Individual por Pallet")
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
                st.markdown("**Composição das Caixas:**")
                st.dataframe(
                    df_p[["SKU", "Produto", "Nº Caixa", "Qtd Caixas"]],
                    use_container_width=True,
                )

            with col_3d:
                fig_3d = gerar_grafico_3d_otimizado(
                    df_p, f"Estrutura 3D - {p_id}"
                )
                st.plotly_chart(fig_3d, use_container_width=True)
