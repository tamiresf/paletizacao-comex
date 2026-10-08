import io
import math
import os
import re
from datetime import datetime
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import streamlit as st

try:
    from fpdf import FPDF
    FPDF_DISPONIVEL = True
except ImportError:
    FPDF_DISPONIVEL = False

st.set_page_config(page_title="Sistema de Paletização - COMEX", page_icon="📦", layout="wide")

# Estilização CSS
st.markdown(
    """
    <style>
    .total-box-container {
        display: flex;
        justify-content: flex-end;
        gap: 15px;
        margin-top: 15px;
        margin-bottom: 10px;
    }
    .total-card {
        background-color: #E6F0FA;
        border: 1px solid #0055B8;
        border-radius: 6px;
        padding: 8px 18px;
        color: #0055B8;
        font-size: 1.05em;
    }
    .total-card b {
        font-size: 1.15em;
        color: #003366;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- CARREGAMENTO DA BASE MESTRE ---
CAMINHOS_BASE = ["COMEX.xlsx", "data/COMEX.xlsx"]
CAMINHO_EXCEL = next((c for c in CAMINHOS_BASE if os.path.exists(c)), None)

@st.cache_data
def carregar_base_mestre(caminho):
    df = pd.read_excel(caminho, sheet_name=0)
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=["SKU", "NUMERO DA CAIXA", "QUANTIDADE DE CAIXAS NO PALLET", "QUANTIDADE DE CAIXAS POR FILEIRA", "ALTURA"]).copy()
    
    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["NOME DO PRODUTO"] = df["NOME DO PRODUTO"].astype(str).str.strip()
    df["NUMERO DA CAIXA"] = pd.to_numeric(df["NUMERO DA CAIXA"], errors="coerce").fillna(0).astype(int)
    df["QUANTIDADE DE PEÇAS"] = pd.to_numeric(df["QUANTIDADE DE PEÇAS"], errors="coerce").fillna(1).astype(int)
    df["QUANTIDADE DE CAIXAS NO PALLET"] = pd.to_numeric(df["QUANTIDADE DE CAIXAS NO PALLET"], errors="coerce").fillna(1).astype(int)
    df["QUANTIDADE DE CAIXAS POR FILEIRA"] = pd.to_numeric(df["QUANTIDADE DE CAIXAS POR FILEIRA"], errors="coerce").fillna(1).astype(int)
    df["ALTURA"] = pd.to_numeric(df["ALTURA"], errors="coerce").fillna(1).astype(int)
    
    # Agrupamento interno por Família
    df["FAMILIA"] = df["SKU"].apply(lambda x: ".".join(x.split(".")[:2]) if "." in x else str(x)[:4])
    return df

if not CAMINHO_EXCEL:
    st.error("⚠️ Ficheiro 'COMEX.xlsx' não encontrado no diretório da aplicação.")
    st.stop()

df_mestre = carregar_base_mestre(CAMINHO_EXCEL)

# --- INTERFACE DE ENTRADA DO PEDIDO ---
st.title("📦 Otimizador de Paletização para Exportação")
st.markdown("Preencha os itens manualmente ou faça o carregamento da folha de cálculo enviada pelo COMEX.")

tab_upload, tab_manual = st.tabs(["📁 Importar Folha de Cálculo", "✍️ Inserção Manual"])

if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

with tab_upload:
    arquivo_pedido = st.file_uploader("Selecione o ficheiro do pedido (.xlsx ou .csv):", type=["xlsx", "xls", "csv"])
    if arquivo_pedido is not None:
        try:
            if arquivo_pedido.name.endswith(".csv"):
                df_ped = pd.read_csv(arquivo_pedido)
            else:
                df_ped = pd.read_excel(arquivo_pedido)
            df_ped.columns = df_ped.columns.str.strip().str.upper()
            
            col_sku = next((c for c in df_ped.columns if "SKU" in c), None)
            col_qtd = next((c for c in df_ped.columns if any(k in c for k in ["QTD", "QUANTIDADE", "CAIXAS"])), None)
            
            if col_sku and col_qtd:
                itens_importados = []
                for _, r in df_ped.iterrows():
                    sku_limpo = str(r[col_sku]).strip()
                    qtd = int(pd.to_numeric(r[col_qtd], errors="coerce") or 0)
                    if qtd > 0:
                        mestre_item = df_mestre[df_mestre["SKU"] == sku_limpo]
                        if not mestre_item.empty:
                            info = mestre_item.iloc[0]
                            itens_importados.append({
                                "SKU": sku_limpo,
                                "Produto": info["NOME DO PRODUTO"],
                                "Familia": info["FAMILIA"],
                                "Nº Caixa": int(info["NUMERO DA CAIXA"]),
                                "Qtd_Caixas": qtd,
                                "Pecas_Por_Caixa": int(info["QUANTIDADE DE PEÇAS"]),
                                "Caixas_Por_Fileira": int(info["QUANTIDADE DE CAIXAS POR FILEIRA"]),
                                "Altura": int(info["ALTURA"]),
                                "Capacidade_Pallet": int(info["QUANTIDADE DE CAIXAS NO PALLET"]),
                            })
                if st.button("📥 Carregar Itens para o Pedido"):
                    st.session_state.carrinho = itens_importados
                    st.success(f"{len(itens_importados)} SKUs carregados com sucesso!")
            else:
                st.warning("A folha de cálculo deve conter pelo menos as colunas 'SKU' e 'QUANTIDADE'.")
        except Exception as e:
            st.error(f"Erro ao processar o ficheiro: {e}")

with tab_manual:
    col_sel, col_qtd = st.columns([3, 1])
    opcoes = df_mestre["SKU"] + " - " + df_mestre["NOME DO PRODUTO"]
    prod_sel = col_sel.selectbox("Pesquisar SKU / Artigo:", options=opcoes)
    sku_man = prod_sel.split(" - ")[0]
    info_man = df_mestre[df_mestre["SKU"] == sku_man].iloc[0]
    qtd_man = col_qtd.number_input("Qtd Caixas:", min_value=1, value=int(info_man["QUANTIDADE DE CAIXAS NO PALLET"]), step=1)
    
    if st.button("➕ Adicionar SKU Manualmente"):
        achou = False
        for it in st.session_state.carrinho:
            if it["SKU"] == sku_man:
                it["Qtd_Caixas"] += qtd_man
                achou = True
                break
        if not achou:
            st.session_state.carrinho.append({
                "SKU": sku_man,
                "Produto": info_man["NOME DO PRODUTO"],
                "Familia": info_man["FAMILIA"],
                "Nº Caixa": int(info_man["NUMERO DA CAIXA"]),
                "Qtd_Caixas": qtd_man,
                "Pecas_Por_Caixa": int(info_man["QUANTIDADE DE PEÇAS"]),
                "Caixas_Por_Fileira": int(info_man["QUANTIDADE DE CAIXAS POR FILEIRA"]),
                "Altura": int(info_man["ALTURA"]),
                "Capacidade_Pallet": int(info_man["QUANTIDADE DE CAIXAS NO PALLET"]),
            })
        st.success("Artigo adicionado!")

# --- RESUMO DO PEDIDO ---
st.markdown("---")
nome_cliente = st.text_input("Identificação do Pedido / Cliente:", placeholder="Ex: Exportação Pedido #45882")

if st.session_state.carrinho:
    df_carrinho = pd.DataFrame(st.session_state.carrinho)
    st.dataframe(
        df_carrinho[["SKU", "Produto", "Nº Caixa", "Qtd_Caixas", "Caixas_Por_Fileira", "Altura"]],
        use_container_width=True
    )
    if st.button("🔴 Limpar Todo o Pedido"):
        st.session_state.carrinho = []
        st.rerun()

# --- MOTOR DE REGRAS DE PALETIZAÇÃO ---
def otimizar_paletizacao(itens_pedido):
    pallets = []
    itens = sorted(itens_pedido, key=lambda x: (x["Familia"], x["Nº Caixa"], x["SKU"]))
    
    pool_fileiras = []
    caixas_soltas = []
    
    # 1. Pallets Fechados de SKU Único
    for it in itens:
        cap = it["Capacidade_Pallet"]
        cpf = it["Caixas_Por_Fileira"]
        h_max = it["Altura"]
        qtd = it["Qtd_Caixas"]
        
        pallets_fechados = qtd // cap
        sobra_caixas = qtd % cap
        
        for _ in range(pallets_fechados):
            pallets.append({
                "tipo": "Pallet Fechado (SKU Único)",
                "limite_fileiras": h_max,
                "camadas": [{"tipo_cx": it["Nº Caixa"], "itens": {it["SKU"]: cpf}, "completa": True} for _ in range(h_max)],
                "obs": "Pallet 100% ocupado por um único SKU."
            })
            
        fil_completas, resto = divmod(sobra_caixas, cpf)
        for _ in range(fil_completas):
            pool_fileiras.append({
                "sku": it["SKU"],
                "tipo_cx": it["Nº Caixa"],
                "familia": it["Familia"],
                "h_max": h_max,
                "cpf": cpf,
                "itens": {it["SKU"]: cpf}
            })
        if resto > 0:
            caixas_soltas.append({
                "sku": it["SKU"],
                "tipo_cx": it["Nº Caixa"],
                "familia": it["Familia"],
                "h_max": h_max,
                "cpf": cpf,
                "qtd": resto
            })
            
    # 2. Consolidação de Caixas Soltas em Fileiras Mistas
    soltas_agrupadas = {}
    for cs in caixas_soltas:
        t = cs["tipo_cx"]
        soltas_agrupadas.setdefault(t, []).append(cs)
        
    for t, lista_cs in soltas_agrupadas.items():
        if not lista_cs:
            continue
        cpf = lista_cs[0]["cpf"]
        lista_cs.sort(key=lambda x: (-x["h_max"], x["familia"]))
        
        camada_temp = {}
        soma = 0
        min_h = 6
        for c in lista_cs:
            while c["qtd"] > 0:
                espaco = cpf - soma
                pegar = min(espaco, c["qtd"])
                camada_temp[c["sku"]] = camada_temp.get(c["sku"], 0) + pegar
                c["qtd"] -= pegar
                soma += pegar
                min_h = min(min_h, c["h_max"])
                if soma == cpf:
                    pool_fileiras.append({
                        "sku": None,
                        "tipo_cx": t,
                        "familia": "Mista",
                        "h_max": min_h,
                        "cpf": cpf,
                        "itens": camada_temp
                    })
                    camada_temp = {}
                    soma = 0
                    min_h = 6
        if camada_temp:
            for s, q in camada_temp.items():
                ref = next((x for x in lista_cs if x["sku"] == s), None)
                if ref:
                    ref["qtd"] = q
                
    # 3. Pallets de Sobras com Fileiras Completas (Mesmo Tipo de Caixa)
    tipos_presentes = sorted(set(f["tipo_cx"] for f in pool_fileiras), reverse=True)
    
    for t in tipos_presentes:
        fils_t = [f for f in pool_fileiras if f["tipo_cx"] == t]
        if not fils_t:
            continue
            
        alturas = sorted(set(f["h_max"] for f in fils_t), reverse=True)
        for h in alturas:
            iguais = [f for f in fils_t if f["h_max"] == h]
            while len(iguais) >= h:
                lote = iguais[:h]
                for x in lote:
                    fils_t.remove(x)
                    pool_fileiras.remove(x)
                pallets.append({
                    "tipo": "Pallet Fechado (Mesma Caixa e Mesma Altura)",
                    "limite_fileiras": h,
                    "camadas": [{"tipo_cx": t, "itens": f["itens"], "completa": True} for f in lote],
                    "obs": "Composto por fileiras completas da mesma caixa e mesma altura."
                })
                iguais = [f for f in fils_t if f["h_max"] == h]
                
        while fils_t:
            alturas_disponiveis = [f["h_max"] for f in fils_t]
            lim_h = min(alturas_disponiveis)
            if len(fils_t) >= lim_h:
                lote = fils_t[:lim_h]
                for x in lote:
                    fils_t.remove(x)
                    pool_fileiras.remove(x)
                pallets.append({
                    "tipo": "Pallet Fechado (Mesma Caixa, Alturas Mistas)",
                    "limite_fileiras": lim_h,
                    "camadas": [{"tipo_cx": t, "itens": f["itens"], "completa": True} for f in lote],
                    "obs": f"Limite respeitado de {lim_h} fileiras máximas."
                })
            else:
                break

    # 4. Combinação de Diferentes Tipos de Caixa
    while len(pool_fileiras) >= 4:
        alturas_candidatas = [f["h_max"] for f in pool_fileiras[:4]]
        h_lim = min(alturas_candidatas)
        if len(pool_fileiras) >= h_lim:
            lote = pool_fileiras[:h_lim]
            lote.sort(key=lambda x: -x["tipo_cx"])
            for x in lote:
                pool_fileiras.remove(x)
            pallets.append({
                "tipo": "Pallet Fechado (Caixas Mistas por Fileira Inteira)",
                "limite_fileiras": h_lim,
                "camadas": [{"tipo_cx": f["tipo_cx"], "itens": f["itens"], "completa": True} for f in lote],
                "obs": "Fileiras completas de diferentes caixas combinadas."
            })
        else:
            break

    # 5. Fechamento do Pallet Final
    soltas_finais = [cs for cs in caixas_soltas if cs.get("qtd", 0) > 0]
    
    if pool_fileiras or soltas_finais:
        camadas_final = []
        for f in pool_fileiras:
            camadas_final.append({"tipo_cx": f["tipo_cx"], "itens": f["itens"], "completa": True})
            
        if soltas_finais:
            itens_inc = {cs["sku"]: cs["qtd"] for cs in soltas_finais}
            camadas_final.append({"tipo_cx": soltas_finais[0]["tipo_cx"], "itens": itens_inc, "completa": False})
            
        if len(camadas_final) < 2 and pallets:
            doador = pallets[-1]
            if len(doador.get("camadas", [])) > 2:
                camada_movida = doador["camadas"].pop()
                camadas_final.insert(0, camada_movida)
                doador["obs"] += " (1 fileira transferida para o último pallet para cumprir o mínimo de 2 fileiras)."
                
        pallets.append({
            "tipo": "Último Pallet (Sobras / Fileira Incompleta)",
            "limite_fileiras": len(camadas_final),
            "camadas": camadas_final,
            "obs": "Contém sobras finais de exportação e fileiras residuais."
        })
        
    return pallets

# --- CONVERSÃO PARA RELATÓRIO OPERACIONAL ---
def gerar_dataframe_operador(pallets, itens_pedido):
    mapa_itens = {i["SKU"]: i for i in itens_pedido}
    linhas = []
    
    for idx, p in enumerate(pallets, 1):
        qtd_fileiras_pallet = len(p["camadas"])
        for pos, c in enumerate(p["camadas"], 1):
            for sku, qtd in c["itens"].items():
                info = mapa_itens.get(sku, {})
                pecas_cx = info.get("Pecas_Por_Caixa", 1)
                total_pecas_linha = qtd * pecas_cx
                
                linhas.append({
                    "Pallet_Num": idx,
                    "Pallet": f"Pallet {idx}",
                    "Tipo Pallet": p["tipo"],
                    "Altura_Pallet": qtd_fileiras_pallet,
                    "Fileira": f"{pos}ª fileira",
                    "SKU": sku,
                    "Produto": info.get("Produto", "Desconhecido"),
                    "Caixa Nº": info.get("Nº Caixa", "-"),
                    "Qtd Caixas": qtd,
                    "Total Peças": total_pecas_linha,
                    "Cx / Fileira": info.get("Caixas_Por_Fileira", "-"),
                    "Status Fileira": "Completa" if c["completa"] else "Incompleta (Topo)",
                    "Observação": p["obs"]
                })
    return pd.DataFrame(linhas)

# --- GERADOR DO EXCEL NO FORMATO DO MODELO ---
def gerar_excel_modelo(df_operador):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Paletização"
    
    PALETA_CORES = [
        "E2EFDA", "D9E1F2", "FCE4D6", "FFF2CC", "EDEDED", "DDEBF7", "EAE8FE"
    ]
    
    fill_cabecalho = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    font_cabecalho = Font(name="Calibri", size=11, bold=True, color="000000")
    
    thin_side = Side(border_style="thin", color="000000")
    double_side = Side(border_style="double", color="000000")
    borda_padrao = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    borda_cabecalho = Border(left=thin_side, right=thin_side, top=thin_side, bottom=double_side)
    
    headers = ["Pallet", "SKU", "Produto", "Caixa Nº", "Qtd Caixas", "Fileira", "Status"]
    ws.row_dimensions[1].height = 28
    
    for col_idx, header in enumerate(headers, 1):
        c = ws.cell(row=1, column=col_idx, value=header)
        c.fill = fill_cabecalho
        c.font = font_cabecalho
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = borda_cabecalho

    df_agrupado = (
        df_operador.groupby(["Pallet_Num", "SKU", "Produto", "Caixa Nº", "Status Fileira"], as_index=False)
        .agg(
            Qtd_Caixas=("Qtd Caixas", "sum"),
            Fileiras=("Fileira", lambda f: ", ".join(f))
        )
        .sort_values(by=["Pallet_Num", "Caixa Nº", "SKU"])
    )

    linha_atual = 2
    for idx_pal, (pal_num, grupo) in enumerate(df_agrupado.groupby("Pallet_Num", sort=False)):
        cor_hex = PALETA_CORES[idx_pal % len(PALETA_CORES)]
        fill_pallet = PatternFill(start_color=cor_hex, end_color=cor_hex, fill_type="solid")
        
        inicio_linha = linha_atual
        qtd_skus = len(grupo)
        fim_linha = linha_atual + qtd_skus - 1
        
        for _, row in grupo.iterrows():
            ws.row_dimensions[linha_atual].height = 20
            
            ws.cell(row=linha_atual, column=1, value=int(pal_num))
            ws.cell(row=linha_atual, column=2, value=str(row["SKU"]))
            ws.cell(row=linha_atual, column=3, value=str(row["Produto"]))
            ws.cell(row=linha_atual, column=4, value=int(row["Caixa Nº"]))
            ws.cell(row=linha_atual, column=5, value=int(row["Qtd_Caixas"]))
            ws.cell(row=linha_atual, column=6, value=str(row["Fileiras"]))
            ws.cell(row=linha_atual, column=7, value=str(row["Status Fileira"]))
            
            for col_i in range(1, 8):
                cell_item = ws.cell(row=linha_atual, column=col_i)
                cell_item.fill = fill_pallet
                cell_item.border = borda_padrao
                cell_item.font = Font(name="Calibri", size=10)
                
                if col_i in [1, 2, 4, 5, 7]:
                    cell_item.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell_item.alignment = Alignment(horizontal="left", vertical="center")
                    
            linha_atual += 1
            
        if qtd_skus > 1:
            ws.merge_cells(start_row=inicio_linha, start_column=1, end_row=fim_linha, end_column=1)
            cell_mesclada = ws.cell(row=inicio_linha, column=1)
            cell_mesclada.alignment = Alignment(horizontal="center", vertical="center")
            cell_mesclada.font = Font(name="Calibri", size=11, bold=True)
        else:
            ws.cell(row=inicio_linha, column=1).font = Font(name="Calibri", size=10, bold=True)

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
        
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 18

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

# --- GERADOR DE PDF OPERACIONAL ---
def _latin(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

def gerar_pdf_operacional(df_operador, nome_cliente_str):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "MUSTAD - Relatorio de Paletizacao", align="C")
    pdf.ln(7)
    
    cli = nome_cliente_str.strip() if nome_cliente_str else "Nao Informado"
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, f"Cliente: {_latin(cli)}", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Emissao: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C")
    pdf.ln(6)
    
    total_pallets = df_operador["Pallet_Num"].nunique()
    total_cx = df_operador["Qtd Caixas"].sum()
    total_pc = df_operador["Total Peças"].sum()
    
    pdf.set_fill_color(0, 85, 184)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 9, f"CARGA TOTAL: {total_pallets} PALLETS | {total_cx} CAIXAS | {total_pc} PECAS", align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(12)
    
    for num_p in sorted(df_operador["Pallet_Num"].unique()):
        df_p = df_operador[df_operador["Pallet_Num"] == num_p]
        cx_pallet = int(df_p["Qtd Caixas"].sum())
        alt_pallet = int(df_p["Altura_Pallet"].iloc[0])
        
        if pdf.get_y() + (len(df_p) * 6) + 30 > 280:
            pdf.add_page()
            
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, f"Pallet {num_p} - Altura: {alt_pallet} fileiras - {_latin(df_p['Tipo Pallet'].iloc[0])}", border="B")
        pdf.ln(7)
        
        larguras = [24, 28, 70, 15, 20, 32]
        titulos = ["Fileira", "SKU", "Produto", "N. Cx", "Qtd Cx", "Status"]
        
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        for w, t in zip(larguras, titulos):
            pdf.cell(w, 6, t, border=1, fill=True, align="C")
        pdf.ln()
        
        pdf.set_font("Helvetica", "", 8)
        for _, r in df_p.iterrows():
            pdf.cell(larguras[0], 6, _latin(r["Fileira"]), border=1, align="C")
            pdf.cell(larguras[1], 6, str(r["SKU"]), border=1, align="C")
            pdf.cell(larguras[2], 6, _latin(r["Produto"])[:45], border=1)
            pdf.cell(larguras[3], 6, str(r["Caixa Nº"]), border=1, align="C")
            pdf.cell(larguras[4], 6, str(r["Qtd Caixas"]), border=1, align="C")
            pdf.cell(larguras[5], 6, _latin(r["Status Fileira"]), border=1, align="C")
            pdf.ln()
            
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"Total de Caixas no Pallet {num_p}: {cx_pallet} cx  |  Altura: {alt_pallet} fileiras", align="R")
        pdf.ln(8)
        
    return bytes(pdf.output())

# --- EXECUÇÃO E EXIBIÇÃO ---
if st.button("🚀 Otimizar e Gerar Instruções de Paletização"):
    if not st.session_state.carrinho:
        st.warning("Adicione produtos ou importe uma folha de cálculo para processar.")
    else:
        resultado_pallets = otimizar_paletizacao(st.session_state.carrinho)
        df_operador = gerar_dataframe_operador(resultado_pallets, st.session_state.carrinho)
        
        st.subheader("📋 Resumo da Carga Paletizada")
        total_cx_global = df_operador["Qtd Caixas"].sum()
        total_pc_global = df_operador["Total Peças"].sum()
        
        # Três métricas principais: Pallets, Total Geral de Caixas e Total Geral de Peças
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Total de Pallets", f"{len(resultado_pallets)}")
        c2.metric("📦 Total Geral de Caixas", f"{total_cx_global:,} cx".replace(",", "."))
        c3.metric("🧩 Total Geral de Peças", f"{total_pc_global:,} pçs".replace(",", "."))
        st.markdown("---")
        
        # Botões de Download
        col_btn1, col_btn2 = st.columns(2)
        cliente_limpo = re.sub(r'[\\/*?:"<>|]', "", nome_cliente.strip()) or "PEDIDO"
        data_str = datetime.now().strftime("%d-%m-%Y")
        
        with col_btn1:
            bytes_excel = gerar_excel_modelo(df_operador)
            st.download_button(
                label="📊 Baixar Paletização em Excel (.xlsx)",
                data=bytes_excel,
                file_name=f"PALETIZACAO_{cliente_limpo}_{data_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        with col_btn2:
            if FPDF_DISPONIVEL:
                bytes_pdf = gerar_pdf_operacional(df_operador, nome_cliente)
                st.download_button(
                    label="📄 Baixar Relatório em PDF (.pdf)",
                    data=bytes_pdf,
                    file_name=f"PALETIZACAO_{cliente_limpo}_{data_str}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # Exibição individual dos Pallets com a Altura em destaque
        for num_p in sorted(df_operador["Pallet_Num"].unique()):
            df_p = df_operador[df_operador["Pallet_Num"] == num_p]
            total_cx_pallet = int(df_p["Qtd Caixas"].sum())
            altura_pallet = int(df_p["Altura_Pallet"].iloc[0])
            
            with st.expander(f"📦 {num_p} - {df_p['Tipo Pallet'].iloc[0]}  |  📐 Altura: {altura_pallet} fileiras", expanded=True):
                st.caption(f"Orientação: {df_p['Observação'].iloc[0]}")
                st.dataframe(
                    df_p[["Fileira", "SKU", "Produto", "Caixa Nº", "Qtd Caixas", "Cx / Fileira", "Status Fileira"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Cards de rodapé com Altura e Quantidade de Caixas
                st.markdown(
                    f"""
                    <div class="total-box-container">
                        <div class="total-card">
                            📐 Altura: <b>{altura_pallet} fileiras</b>
                        </div>
                        <div class="total-card">
                            📦 Total de Caixas no {num_p}: <b>{total_cx_pallet} cx</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
