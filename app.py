import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
from fpdf import FPDF

# Configuração da página Streamlit
st.set_page_config(
    page_title="Sistema de Paletização 3D - COMEX",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Sistema de Paletização e Visualização 3D")
st.caption("Automação de montagem de pallets fechados, consolidação de mistos por capacidade e renderização 3D em escala real.")

# --- DICIONÁRIO DE DIMENSÕES FÍSICAS REAIS DAS CAIXAS (em metros) ---
DIMENSOES_CAIXAS = {
    "CAIXA 0": {"comp": 0.230, "larg": 0.145, "alt": 0.125},
    "CAIXA 1": {"comp": 0.285, "larg": 0.155, "alt": 0.125},
    "CAIXA 2": {"comp": 0.295, "larg": 0.185, "alt": 0.130},
    "CAIXA 3": {"comp": 0.375, "larg": 0.195, "alt": 0.145},
}

def obter_dimensoes_caixa(num_caixa):
    """Retorna comprimento, largura e altura em metros baseado na identificação da caixa."""
    num_str = str(num_caixa).upper().strip()
    if "CAIXA" not in num_str:
        key = f"CAIXA {num_str}"
    else:
        key = num_str
    
    return DIMENSOES_CAIXAS.get(key, {"comp": 0.300, "larg": 0.200, "alt": 0.150})

# --- CARREGAR BASE ---
@st.cache_data
def carregar_base(caminho_excel):
    df = pd.read_excel(caminho_excel)
    df.columns = df.columns.str.strip()
    df['SKU'] = df['SKU'].astype(str).str.strip()
    def extrair_num_caixa(val):
        try:
            val_str = str(val).upper().replace("CAIXA", "").strip()
            return int(val_str)
        except:
            return 0
    df['Ordem_Caixa'] = df['NUMERO DA CAIXA'].apply(extrair_num_caixa)
    return df

CAMINHO_EXCEL = "COMEX.xlsx"
if not os.path.exists(CAMINHO_EXCEL) and os.path.exists("data/COMEX.xlsx"):
    CAMINHO_EXCEL = "data/COMEX.xlsx"

try:
    df_produtos = carregar_base(CAMINHO_EXCEL)
except Exception as e:
    st.error(f"Erro ao carregar a planilha COMEX.xlsx: {e}")
    st.stop()

# --- SESSÃO DO PEDIDO E PROCESSAMENTO ---
if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []

if 'processado' not in st.session_state:
    st.session_state.processado = False

# --- PAINEL LATERAL ---
st.sidebar.header("📋 Inserir Pedido")
opcoes_produtos = df_produtos['SKU'] + " - " + df_produtos['NOME DO PRODUTO']
produto_selecionado = st.sidebar.selectbox("Pesquisar Produto (SKU ou Nome):", options=opcoes_produtos)

sku_sel = produto_selecionado.split(" - ")[0]
prod_info = df_produtos[df_produtos['SKU'] == sku_sel].iloc[0]

st.sidebar.info(f"""
**Informações do Cadastro:**  
• **Caixa Tipo:** {prod_info['NUMERO DA CAIXA']}  
• **Peças/Caixa:** {prod_info['QUANTIDADE DE PEÇAS']}  
• **Capacidade Pallet Fechado:** {prod_info['QUANTIDADE DE CAIXAS NO PALLET']} cx
""")

qtd_solicitada = st.sidebar.number_input("Qtd de Caixas Solicitada:", min_value=1, value=int(prod_info['QUANTIDADE DE CAIXAS NO PALLET']), step=1)

if st.sidebar.button("➕ Adicionar ao Pedido"):
    existente = False
    for item in st.session_state.carrinho:
        if item['SKU'] == sku_sel:
            item['Qtd_Caixas'] += qtd_solicitada
            existente = True
            break
    if not existente:
        st.session_state.carrinho.append({
            'SKU': sku_sel,
            'Produto': prod_info['NOME DO PRODUTO'],
            'Nº Caixa': prod_info['NUMERO DA CAIXA'],
            'Qtd_Caixas': qtd_solicitada,
            'Pecas_Por_Caixa': int(prod_info['QUANTIDADE DE PEÇAS'])
        })
    st.session_state.processado = False
    st.sidebar.success("Item adicionado ao pedido!")

# --- CORPO PRINCIPAL: PEDIDO ATUAL E LIXEIRA ---
st.subheader("🛒 Itens do Pedido Atual")

if st.session_state.carrinho:
    total_caixas_pedido = 0
    total_pecas_pedido = 0

    for index in range(len(st.session_state.carrinho) - 1, -1, -1):
        item = st.session_state.carrinho[index]
        pecas_cx = item.get('Pecas_Por_Caixa', 1)
        total_pecas_item = item['Qtd_Caixas'] * pecas_cx
        
        total_caixas_pedido += item['Qtd_Caixas']
        total_pecas_pedido += total_pecas_item

        c1, c2, c3, c4, c5, c6 = st.columns([1.5, 3, 1.2, 1.3, 1.5, 0.8])
        
        c1.write(f"**SKU:** {item['SKU']}")
        c2.write(f"**Produto:** {item['Produto']}")
        c3.write(f"**Caixa Nº:** {item['Nº Caixa']}")
        c4.write(f"**Qtd:** {item['Qtd_Caixas']} cx")
        c5.write(f"**Total Peças:** {total_pecas_item:,}".replace(",", "."))
        
        if c6.button("🗑️", key=f"remover_{index}_{item['SKU']}", help="Remover item"):
            st.session_state.carrinho.pop(index)
            st.session_state.processado = False
            st.rerun()

    st.markdown("---")
    
    # --- LINHA DE TOTALIZAÇÃO DO PEDIDO ---
    m1, m2, m3 = st.columns([2, 2, 2])
    m1.metric(label="📦 Total de Caixas no Pedido", value=f"{total_caixas_pedido:,} cx".replace(",", "."))
    m2.metric(label="🧩 Total de Peças no Pedido", value=f"{total_pecas_pedido:,} peças".replace(",", "."))
    
    with m3:
        st.write("")
        if st.button("🔴 Limpar Todo o Pedido", use_container_width=True):
            st.session_state.carrinho = []
            st.session_state.processado = False
            st.rerun()
else:
    st.info("Nenhum item inserido no pedido até o momento. Utilize o menu lateral para adicionar.")

st.markdown("---")

# --- FUNÇÕES DE PROCESSAMENTO E RELATÓRIO ---
def processar_pallets_detalhado(carrinho, df_produtos):
    pallets_lista = []
    pallet_id = 1
    sobras_para_misto = []

    for item in carrinho:
        sku = str(item['SKU']).strip()
        qtd = int(item['Qtd_Caixas'])
        
        prod = df_produtos[df_produtos['SKU'] == sku].iloc[0]
        cap_pallet = int(prod['QUANTIDADE DE CAIXAS NO PALLET'])
        ordem_cx = int(prod['Ordem_Caixa'])
        
        qtd_pallets_fechados = qtd // cap_pallet
        resto = qtd % cap_pallet

        for _ in range(qtd_pallets_fechados):
            pallets_lista.append({
                'ID': f"Pallet {pallet_id}",
                'Tipo': "Fechado 🟢",
                'SKU': sku,
                'Produto': prod['NOME DO PRODUTO'],
                'Qtd Caixas': cap_pallet,
                'Nº Caixa': prod['NUMERO DA CAIXA'],
                'Ordem_Caixa': ordem_cx,
                'Capacidade_Max': cap_pallet
            })
            pallet_id += 1

        if resto > 0:
            sobras_para_misto.append({
                'SKU': sku,
                'Produto': prod['NOME DO PRODUTO'],
                'Qtd Caixas': resto,
                'Nº Caixa': prod['NUMERO DA CAIXA'],
                'Ordem_Caixa': ordem_cx,
                'Capacidade_Max': cap_pallet
            })

    if sobras_para_misto:
        df_sobras = pd.DataFrame(sobras_para_misto).sort_values(by='Ordem_Caixa', ascending=False)
        
        misto_atual_id = f"Pallet {pallet_id} (Misto)"
        ocupacao_atual = 0.0

        for _, row in df_sobras.iterrows():
            sku = row['SKU']
            prod_nome = row['Produto']
            num_caixa = row['Nº Caixa']
            qtd_restante = row['Qtd Caixas']
            cap_max = row['Capacidade_Max']
            ordem_cx = row['Ordem_Caixa']

            custo_unitario = 1.0 / cap_max

            while qtd_restante > 0:
                espaco_disponivel_pct = 1.0 - ocupacao_atual
                
                if espaco_disponivel_pct <= 0.001:
                    pallet_id += 1
                    misto_atual_id = f"Pallet {pallet_id} (Misto)"
                    ocupacao_atual = 0.0
                    espaco_disponivel_pct = 1.0

                caixas_que_cabem = int(np.floor(espaco_disponivel_pct / custo_unitario))

                if caixas_que_cabem == 0:
                    pallet_id += 1
                    misto_atual_id = f"Pallet {pallet_id} (Misto)"
                    ocupacao_atual = 0.0
                    caixas_que_cabem = int(np.floor(1.0 / custo_unitario))

                qtd_alocar = min(qtd_restante, caixas_que_cabem)
                
                pallets_lista.append({
                    'ID': misto_atual_id,
                    'Tipo': "Misto 🟡",
                    'SKU': sku,
                    'Produto': prod_nome,
                    'Qtd Caixas': qtd_alocar,
                    'Nº Caixa': num_caixa,
                    'Ordem_Caixa': ordem_cx,
                    'Capacidade_Max': cap_max
                })

                ocupacao_atual += qtd_alocar * custo_unitario
                qtd_restante -= qtd_alocar

    return pd.DataFrame(pallets_lista)

def gerar_grafico_3d_fidedigno(df_pallet_especifico, titulo):
    """
    Gera a estrutura 3D com dimensões físicas em metros (mm -> m) das caixas especificadas na imagem.
    """
    fig = go.Figure()

    paleta_cores = ['#D9A036', '#3B82F6', '#10B981', '#EF4444', '#8B5CF6', '#F59E0B']
    skus_unicos = df_pallet_especifico['SKU'].unique()
    cor_map = {sku: paleta_cores[i % len(paleta_cores)] for i, sku in enumerate(skus_unicos)}

    total_caixas = int(df_pallet_especifico['Qtd Caixas'].sum())
    if total_caixas == 0:
        return fig

    # Configuração de arranjo da base
    if total_caixas <= 12:
        nx, ny = 2, 2
    elif total_caixas <= 30:
        nx, ny = 3, 3
    elif total_caixas <= 60:
        nx, ny = 4, 3
    elif total_caixas <= 90:
        nx, ny = 4, 4
    else:
        nx, ny = 5, 4

    nz = int(np.ceil(total_caixas / (nx * ny)))

    caixas_fisicas = []
    for _, row in df_pallet_especifico.iterrows():
        sku = row['SKU']
        qtd = int(row['Qtd Caixas'])
        cor = cor_map[sku]
        cx_nome = row['Nº Caixa']
        dims = obter_dimensoes_caixa(cx_nome)
        for _ in range(qtd):
            caixas_fisicas.append({
                'SKU': sku, 
                'Cor': cor, 
                'Caixa': cx_nome,
                'dx': dims['comp'],
                'dy': dims['larg'],
                'dz': dims['alt']
            })

    # Vértices unitários
    x_cube = [0, 1, 1, 0, 0, 1, 1, 0]
    y_cube = [0, 0, 1, 1, 0, 0, 1, 1]
    z_cube = [0, 0, 0, 0, 1, 1, 1, 1]

    i_mesh = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j_mesh = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k_mesh = [0, 7, 2, 3, 6, 7, 1, 1, 1, 5, 2, 7]

    box_idx = 0

    for z in range(nz):
        for y in range(ny):
            for x in range(nx):
                if box_idx < len(caixas_fisicas):
                    item = caixas_fisicas[box_idx]
                    
                    dx, dy, dz = item['dx'], item['dy'], item['dz']

                    # Posição acumulada no espaço (com pequenos espaçamentos estéticos)
                    x0 = x * (dx + 0.02)
                    y0 = y * (dy + 0.02)
                    z0 = z * (dz + 0.01)

                    x_box = [x0 + vx * dx for vx in x_cube]
                    y_box = [y0 + vy * dy for vy in y_cube]
                    z_box = [z0 + vz * dz for vz in z_cube]

                    fig.add_trace(go.Mesh3d(
                        x=x_box, y=y_box, z=z_box,
                        i=i_mesh, j=j_mesh, k=k_mesh,
                        color=item['Cor'],
                        flatshading=True,
                        lighting=dict(ambient=0.75, diffuse=0.85),
                        hoverinfo="text",
                        text=f"SKU: {item['SKU']}<br>Tipo: {item['Caixa']}<br>Dimensões: {int(dx*1000)}x{int(dy*1000)}x{int(dz*1000)} mm<br>Caixa #{box_idx+1}",
                        showscale=False
                    ))
                    box_idx += 1

    fig.update_layout(
        title=f"{titulo} ({total_caixas} caixas)",
        scene=dict(
            xaxis=dict(title="Comp (m)", showgrid=True),
            yaxis=dict(title="Larg (m)", showgrid=True),
            zaxis=dict(title="Alt (m)", showgrid=True),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=35),
        showlegend=False
    )
    return fig

def gerar_pdf(df_pallets):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "Relatorio de Paletizacao - COMEX", ln=True, align='C')
    pdf.ln(10)

    pallets_unicos = df_pallets['ID'].unique()

    for p_id in pallets_unicos:
        df_p = df_pallets[df_pallets['ID'] == p_id]
        tipo_raw = str(df_p['Tipo'].iloc[0])
        tipo_limpo = tipo_raw.replace("🟢", "").replace("🟡", "").strip()
        total_cx = df_p['Qtd Caixas'].sum()

        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 8, f"{p_id} | Tipo: {tipo_limpo} | Total: {total_cx} caixas", ln=True)
        
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(35, 7, "SKU", border=1)
        pdf.cell(95, 7, "Produto", border=1)
        pdf.cell(30, 7, "N. Caixa", border=1)
        pdf.cell(30, 7, "Qtd Caixas", border=1)
        pdf.ln()

        pdf.set_font("Helvetica", size=10)
        for _, row in df_p.iterrows():
            prod_nome = str(row['Produto']).encode('latin-1', 'replace').decode('latin-1')[:40]
            pdf.cell(35, 6, str(row['SKU']), border=1)
            pdf.cell(95, 6, prod_nome, border=1)
            pdf.cell(30, 6, str(row['Nº Caixa']), border=1)
            pdf.cell(30, 6, str(row['Qtd Caixas']), border=1)
            pdf.ln()
        
        pdf.ln(5)

    return bytes(pdf.output())

# --- BOTÃO DE PROCESSAMENTO ---
if st.button("⚙️ CALCULAR E GERAR PALLETS 3D"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

# --- EXIBIÇÃO PERMANENTE APÓS O CÁLCULO ---
if st.session_state.processado and st.session_state.carrinho:
    df_pallets = processar_pallets_detalhado(st.session_state.carrinho, df_produtos)
    
    st.subheader("📦 Detalhamento Individual por Pallet")
    pallets_unicos = df_pallets['ID'].unique()
    st.success(f"**Total de Pallets Gerados:** {len(pallets_unicos)}")

    # --- BOTÃO DE BAIXAR PDF ---
    try:
        pdf_bytes = gerar_pdf(df_pallets)
        st.download_button(
            label="📄 Baixar Relatório em PDF",
            data=pdf_bytes,
            file_name="plano_de_paletizacao.pdf",
            mime="application/pdf"
        )
    except Exception as err:
        st.error(f"Erro ao gerar PDF: {err}")

    st.markdown("---")

    for p_id in pallets_unicos:
        df_p = df_pallets[df_pallets['ID'] == p_id]
        tipo_pallet = df_p['Tipo'].iloc[0]
        total_cx = int(df_p['Qtd Caixas'].sum())

        with st.expander(f"📌 {p_id} - Total: {total_cx} caixas ({tipo_pallet})", expanded=True):
            col_tabela, col_3d = st.columns([1, 1])
            
            with col_tabela:
                st.markdown("**Composição das Caixas:**")
                st.dataframe(df_p[['SKU', 'Produto', 'Nº Caixa', 'Qtd Caixas']], use_container_width=True)
            
            with col_3d:
                fig_3d = gerar_grafico_3d_fidedigno(df_p, f"Estrutura 3D - {p_id}")
                st.plotly_chart(fig_3d, use_container_width=True)
