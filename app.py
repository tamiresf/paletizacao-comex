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
st.caption("Automação de montagem de pallets fechados, consolidação de mistos e renderização 3D.")

# --- CARREGAR BASE ---
@st.cache_data
def carregar_base(caminho_excel):
    df = pd.read_excel(caminho_excel)
    df.columns = df.columns.str.strip()
    df['SKU'] = df['SKU'].astype(str).str.strip()
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

qtd_solicitada = st.sidebar.number_input("Qtd de Caixas Solicitada:", min_value=1, value=160, step=1)

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
            'Qtd_Caixas': qtd_solicitada
        })
    st.session_state.processado = False
    st.sidebar.success("Item adicionado ao pedido!")

# --- CORPO PRINCIPAL: PEDIDO ATUAL E LIXEIRA ---
st.subheader("🛒 Itens do Pedido Atual")

if st.session_state.carrinho:
    for index in range(len(st.session_state.carrinho) - 1, -1, -1):
        item = st.session_state.carrinho[index]
        c1, c2, c3, c4, c5 = st.columns([1.5, 3.5, 1.5, 1.5, 1])
        
        c1.write(f"**SKU:** {item['SKU']}")
        c2.write(f"**Produto:** {item['Produto']}")
        c3.write(f"**Caixa Nº:** {item['Nº Caixa']}")
        c4.write(f"**Qtd:** {item['Qtd_Caixas']} cx")
        
        if c5.button("🗑️ Excluir", key=f"remover_{index}_{item['SKU']}"):
            st.session_state.carrinho.pop(index)
            st.session_state.processado = False
            st.rerun()

    st.markdown("---")
    if st.button("🔴 Limpar Todo o Pedido"):
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
        
        qtd_pallets_fechados = qtd // cap_pallet
        resto = qtd % cap_pallet

        for _ in range(qtd_pallets_fechados):
            pallets_lista.append({
                'ID': f"Pallet {pallet_id}",
                'Tipo': "Fechado 🟢",
                'SKU': sku,
                'Produto': prod['NOME DO PRODUTO'],
                'Qtd Caixas': cap_pallet,
                'Nº Caixa': prod['NUMERO DA CAIXA']
            })
            pallet_id += 1

        if resto > 0:
            sobras_para_misto.append({
                'SKU': sku,
                'Produto': prod['NOME DO PRODUTO'],
                'Qtd Caixas': resto,
                'Nº Caixa': prod['NUMERO DA CAIXA']
            })

    if sobras_para_misto:
        df_sobras = pd.DataFrame(sobras_para_misto).sort_values(by='Nº Caixa')
        for _, row in df_sobras.iterrows():
            pallets_lista.append({
                'ID': f"Pallet {pallet_id} (Misto)",
                'Tipo': "Misto 🟡",
                'SKU': row['SKU'],
                'Produto': row['Produto'],
                'Qtd Caixas': row['Qtd Caixas'],
                'Nº Caixa': row['Nº Caixa']
            })

    return pd.DataFrame(pallets_lista)

def gerar_grafico_3d(qtd_caixas, titulo):
    dx, dy, dz = 0.9, 0.9, 0.7
    camada = int(np.ceil(qtd_caixas ** (1/3)))
    nx = camada
    ny = camada
    nz = int(np.ceil(qtd_caixas / (nx * ny)))

    fig = go.Figure()
    count = 0

    x_cube = [0, 1, 1, 0, 0, 1, 1, 0]
    y_cube = [0, 0, 1, 1, 0, 0, 1, 1]
    z_cube = [0, 0, 0, 0, 1, 1, 1, 1]

    i_mesh = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j_mesh = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k_mesh = [0, 7, 2, 3, 6, 7, 1, 1, 1, 5, 2, 7]

    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                if count < qtd_caixas:
                    x0 = i * 1.0
                    y0 = j * 1.0
                    z0 = k * 0.8

                    x_box = [x0 + vx * dx for vx in x_cube]
                    y_box = [y0 + vy * dy for vy in y_cube]
                    z_box = [z0 + vz * dz for vz in z_cube]

                    fig.add_trace(go.Mesh3d(
                        x=x_box, y=y_box, z=z_box,
                        i=i_mesh, j=j_mesh, k=k_mesh,
                        color='#C29B38',
                        flatshading=True,
                        lighting=dict(ambient=0.6, diffuse=0.8),
                        name=f'Caixa {count + 1}',
                        showscale=False
                    ))
                    count += 1

    fig.update_layout(
        title=titulo,
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=30),
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
            # Trata acentuação para padrão Latin-1
            prod_nome = str(row['Produto']).encode('latin-1', 'replace').decode('latin-1')[:40]
            pdf.cell(35, 6, str(row['SKU']), border=1)
            pdf.cell(95, 6, prod_nome, border=1)
            pdf.cell(30, 6, str(row['Nº Caixa']), border=1)
            pdf.cell(30, 6, str(row['Qtd Caixas']), border=1)
            pdf.ln()
        
        pdf.ln(5)

    # Retorna diretamente como bytes sem aplicar .encode()
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
        total_cx = df_p['Qtd Caixas'].sum()

        with st.expander(f"📌 {p_id} - Total: {total_cx} caixas ({tipo_pallet})", expanded=True):
            col_tabela, col_3d = st.columns([1, 1])
            
            with col_tabela:
                st.markdown("**Composição das Caixas:**")
                st.dataframe(df_p[['SKU', 'Produto', 'Nº Caixa', 'Qtd Caixas']], use_container_width=True)
            
            with col_3d:
                fig_3d = gerar_grafico_3d(total_cx, f"Estrutura 3D - {p_id}")
                st.plotly_chart(fig_3d, use_container_width=True)