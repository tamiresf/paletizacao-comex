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
    .tabela-cabecalho {
        font-weight: bold;
        background-color: #F0F2F6;
        padding: 8px 10px;
        border-radius: 4px;
        margin-bottom: 8px;
    }
    .linha-pedido {
        padding: 6px 10px;
        border-bottom: 1px solid #E6E9EF;
        align-items: center;
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
    
    df["SKU_NORMALIZADO"] = df["SKU"].apply(lambda s: re.sub(r"\D", "", str(s)))
    df["NOME_NORMALIZADO"] = df["NOME DO PRODUTO"].str.upper().str.strip()
    df["FAMILIA"] = df["SKU"].apply(lambda x: ".".join(x.split(".")[:2]) if "." in x else str(x)[:4])
    return df

if not CAMINHO_EXCEL:
    st.error("⚠️ Ficheiro 'COMEX.xlsx' não encontrado no diretório da aplicação.")
    st.stop()

df_mestre = carregar_base_mestre(CAMINHO_EXCEL)

def buscar_produto_na_base(termo_sku, termo_nome, df_ref):
    termo_sku = str(termo_sku or "").strip()
    termo_nome = str(termo_nome or "").strip()
    
    if termo_sku and termo_sku.lower() != "nan":
        m = df_ref[df_ref["SKU"] == termo_sku]
        if not m.empty:
            return m.iloc[0]
        sku_num = re.sub(r"\D", "", termo_sku)
        if sku_num:
            m = df_ref[df_ref["SKU_NORMALIZADO"] == sku_num]
            if not m.empty:
                return m.iloc[0]
                
    if termo_nome and termo_nome.lower() != "nan":
        nome_up = termo_nome.upper()
        m = df_ref[df_ref["NOME_NORMALIZADO"] == nome_up]
        if not m.empty:
            return m.iloc[0]
        m = df_ref[df_ref["NOME_NORMALIZADO"].str.contains(re.escape(nome_up), na=False)]
        if not m.empty:
            return m.iloc[0]
            
    return None

# --- ESTADO DA SESSÃO ---
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

if "sku_para_excluir" not in st.session_state:
    st.session_state.sku_para_excluir = None

# --- INTERFACE DE ENTRADA DO PEDIDO ---
st.title("📦 Otimizador de Paletização para Exportação")
st.markdown("Preencha os itens manualmente ou faça o carregamento da folha de cálculo enviada pelo COMEX.")

tab_upload, tab_manual = st.tabs(["📁 Importar Folha de Cálculo", "✍️ Inserção Manual"])

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
            col_nome = next((c for c in df_ped.columns if any(k in c for k in ["NOME", "PRODUTO", "DESCRICAO", "DESCRIÇÃO"])), None)
            col_qtd = next((c for c in df_ped.columns if any(k in c for k in ["QTD", "QUANTIDADE", "CAIXAS"])), None)
            
            if col_qtd and (col_sku or col_nome):
                itens_importados = []
                nao_encontrados = []
                
                for _, r in df_ped.iterrows():
                    val_sku = str(r[col_sku]).strip() if col_sku else ""
                    val_nome = str(r[col_nome]).strip() if col_nome else ""
                    qtd = int(pd.to_numeric(r[col_qtd], errors="coerce") or 0)
                    
                    if qtd > 0:
                        info = buscar_produto_na_base(val_sku, val_nome, df_mestre)
                        if info is not None:
                            itens_importados.append({
                                "SKU": str(info["SKU"]),
                                "Produto": info["NOME DO PRODUTO"],
                                "Familia": info["FAMILIA"],
                                "Nº Caixa": int(info["NUMERO DA CAIXA"]),
                                "Qtd_Caixas": qtd,
                                "Pecas_Por_Caixa": int(info["QUANTIDADE DE PEÇAS"]),
                                "Caixas_Por_Fileira": int(info["QUANTIDADE DE CAIXAS POR FILEIRA"]),
                                "Altura": int(info["ALTURA"]),
                                "Capacidade_Pallet": int(info["QUANTIDADE DE CAIXAS NO PALLET"]),
                            })
                        else:
                            identificador = val_sku if val_sku else val_nome
                            nao_encontrados.append(f"{identificador} (Qtd: {qtd})")
                            
                if st.button("📥 Carregar Itens para o Pedido"):
                    st.session_state.carrinho = itens_importados
                    st.session_state.sku_para_excluir = None
                    st.success(f"{len(itens_importados)} SKUs carregados com sucesso!")
                    if nao_encontrados:
                        st.warning(f"⚠️ {len(nao_encontrados)} item(ns) não foram localizados na planilha COMEX (nem por SKU nem por Nome do Produto):\n• " + "\n• ".join(nao_encontrados))
            else:
                st.warning("A folha de cálculo deve conter uma coluna de QUANTIDADE e ao menos uma coluna de identificação ('SKU' ou 'PRODUTO').")
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
        st.session_state.sku_para_excluir = None
        st.success("Artigo adicionado!")

# --- RESUMO DO PEDIDO COM EXCLUSÃO INDIVIDUAL ---
st.markdown("---")
nome_cliente = st.text_input("Identificação do Pedido / Cliente:", placeholder="Ex: Exportação Pedido #45882")

if st.session_state.carrinho:
    st.subheader("🛒 Itens Carregados no Pedido")

    if st.session_state.sku_para_excluir is not None:
        idx_del = st.session_state.sku_para_excluir
        if 0 <= idx_del < len(st.session_state.carrinho):
            item_alvo = st.session_state.carrinho[idx_del]
            st.warning(f"⚠️ **Deseja realmente apagar este item?**\n\n• **SKU:** `{item_alvo['SKU']}` | **Produto:** {item_alvo['Produto']} | **Qtd:** {item_alvo['Qtd_Caixas']} caixas")
            c_conf1, c_conf2, _ = st.columns([1.2, 1.2, 5])
            with c_conf1:
                if st.button("✅ Sim, excluir", key="btn_confirma_exclusao", use_container_width=True):
                    st.session_state.carrinho.pop(idx_del)
                    st.session_state.sku_para_excluir = None
                    st.rerun()
            with c_conf2:
                if st.button("❌ Cancelar", key="btn_cancela_exclusao", use_container_width=True):
                    st.session_state.sku_para_excluir = None
                    st.rerun()
        else:
            st.session_state.sku_para_excluir = None

    c_h1, c_h2, c_h3, c_h4, c_h5, c_h6, c_h7 = st.columns([1.8, 4.2, 1.2, 1.3, 1.5, 1.0, 0.8])
    c_h1.markdown("**SKU**")
    c_h2.markdown("**Produto**")
    c_h3.markdown("**Nº Caixa**")
    c_h4.markdown("**Qtd Caixas**")
    c_h5.markdown("**Cx / Fileira**")
    c_h6.markdown("**Altura**")
    c_h7.markdown("**Ação**")

    for i, it in enumerate(st.session_state.carrinho):
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.8, 4.2, 1.2, 1.3, 1.5, 1.0, 0.8])
        c1.write(it["SKU"])
        c2.write(it["Produto"])
        c3.write(str(it["Nº Caixa"]))
        c4.write(f"{it['Qtd_Caixas']} cx")
        c5.write(str(it["Caixas_Por_Fileira"]))
        c6.write(str(it["Altura"]))
        if c7.button("🗑️", key=f"del_sku_{i}_{it['SKU']}", help="Excluir este SKU"):
            st.session_state.sku_para_excluir = i
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔴 Limpar Todo o Pedido"):
        st.session_state.carrinho = []
        st.session_state.sku_para_excluir = None
        st.rerun()

# --- MOTOR DE REGRAS DE PALETIZAÇÃO (OTIMIZADO POR CAPACIDADE E 2 SKUS) ---
def _montar_camadas_por_skus(lista_sku_qtd, tipo_cx, cpf):
    """Distribui uma lista de (sku, qtd_caixas) em fileiras sequenciais de tamanho cpf."""
    camadas = []
    camada_atual = {}
    ocupado = 0

    for sku, qtd in lista_sku_qtd:
        restante = qtd
        while restante > 0:
            espaco = cpf - ocupado
            colocar = min(espaco, restante)
            camada_atual[sku] = camada_atual.get(sku, 0) + colocar
            ocupado += colocar
            restante -= colocar

            if ocupado == cpf:
                camadas.append({
                    "tipo_cx": tipo_cx,
                    "itens": camada_atual,
                    "completa": True
                })
                camada_atual = {}
                ocupado = 0

    if camada_atual:
        camadas.append({
            "tipo_cx": tipo_cx,
            "itens": camada_atual,
            "completa": False
        })
    return camadas


def otimizar_paletizacao(itens_pedido):
    pallets = []
    itens = sorted(itens_pedido, key=lambda x: (x["Nº Caixa"], x["Familia"], x["SKU"]))

    sobras_por_sku = []

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

        if sobra_caixas > 0:
            sobras_por_sku.append({
                "sku": it["SKU"],
                "tipo_cx": it["Nº Caixa"],
                "familia": it["Familia"],
                "h_max": h_max,
                "cpf": cpf,
                "cap": cap,
                "qtd": sobra_caixas
            })

    # 2. Pallets Fechados de 2 SKUs (Soma Exata de Caixas - Mesma Caixa, ex: 50 + 30 = 80)
    tipos_caixa = sorted(set(s["tipo_cx"] for s in sobras_por_sku), reverse=True)
    for t in tipos_caixa:
        while True:
            candidatos = [s for s in sobras_por_sku if s["tipo_cx"] == t and s["qtd"] > 0]
            candidatos.sort(key=lambda x: (-x["qtd"], x["sku"]))
            achou_par = False

            for i in range(len(candidatos)):
                s1 = candidatos[i]
                for j in range(i + 1, len(candidatos)):
                    s2 = candidatos[j]
                    cap_alvo = min(s1["cap"], s2["cap"])
                    if s1["qtd"] + s2["qtd"] == cap_alvo:
                        camadas = _montar_camadas_por_skus(
                            [(s1["sku"], s1["qtd"]), (s2["sku"], s2["qtd"])],
                            t,
                            s1["cpf"]
                        )
                        pallets.append({
                            "tipo": "Pallet Fechado (2 SKUs - Soma Exata)",
                            "limite_fileiras": len(camadas),
                            "camadas": camadas,
                            "obs": f"Otimizado com 2 SKUs ({s1['sku']} e {s2['sku']}) fechando {cap_alvo} caixas exatas."
                        })
                        s1["qtd"] = 0
                        s2["qtd"] = 0
                        achou_par = True
                        break
                if achou_par:
                    break

            if not achou_par:
                break

    # 3. Pallets Fechados de 2 SKUs (Mesma Caixa - Combinação que atinge capacidade do pallet)
    for t in tipos_caixa:
        while True:
            candidatos = [s for s in sobras_por_sku if s["tipo_cx"] == t and s["qtd"] > 0]
            if len(candidatos) < 2:
                break
            candidatos.sort(key=lambda x: (-x["qtd"], x["sku"]))
            s1 = candidatos[0]

            melhor_s2 = None
            for s2 in candidatos[1:]:
                cap_alvo = min(s1["cap"], s2["cap"])
                if s1["qtd"] + s2["qtd"] >= cap_alvo:
                    sobra_apos = (s1["qtd"] + s2["qtd"]) - cap_alvo
                    if melhor_s2 is None or sobra_apos < melhor_s2[0]:
                        melhor_s2 = (sobra_apos, s2, cap_alvo)

            if melhor_s2 is None:
                break

            _, s2, cap_alvo = melhor_s2
            usar_s1 = s1["qtd"]
            usar_s2 = cap_alvo - usar_s1

            camadas = _montar_camadas_por_skus(
                [(s1["sku"], usar_s1), (s2["sku"], usar_s2)],
                t,
                s1["cpf"]
            )
            pallets.append({
                "tipo": "Pallet Fechado (2 SKUs - Mesma Caixa)",
                "limite_fileiras": len(camadas),
                "camadas": camadas,
                "obs": f"Otimizado com apenas 2 SKUs ({s1['sku']} e {s2['sku']}) na mesma caixa."
            })
            s1["qtd"] -= usar_s1
            s2["qtd"] -= usar_s2

    # 4. Consolidação Final por Mesmo Número de Caixa (evita desperdiçar capacidade de pallets intermediários)
    restantes = [s for s in sobras_por_sku if s["qtd"] > 0]
    restantes.sort(key=lambda x: (-x["tipo_cx"], -x["qtd"], x["sku"]))

    for t in sorted(set(r["tipo_cx"] for r in restantes), reverse=True):
        grupo_t = [r for r in restantes if r["tipo_cx"] == t and r["qtd"] > 0]
        if not grupo_t:
            continue

        cpf = grupo_t[0]["cpf"]
        cap_grupo = max(r["cap"] for r in grupo_t)
        total_cx_grupo = sum(r["qtd"] for r in grupo_t)

        while total_cx_grupo >= cap_grupo:
            alocados = []
            falta = cap_grupo
            grupo_t.sort(key=lambda x: (-x["qtd"], x["sku"]))

            for r in grupo_t:
                if r["qtd"] <= 0 or falta == 0:
                    continue
                pegar = min(r["qtd"], falta)
                alocados.append((r["sku"], pegar))
                r["qtd"] -= pegar
                falta -= pegar

            camadas = _montar_camadas_por_skus(alocados, t, cpf)
            pallets.append({
                "tipo": "Pallet Consolidado (Mesma Caixa - Múltiplos SKUs)",
                "limite_fileiras": len(camadas),
                "camadas": camadas,
                "obs": f"Consolidação de sobras da Caixa Nº {t} fechando {cap_grupo} caixas."
            })
            total_cx_grupo = sum(r["qtd"] for r in grupo_t)

    # 5. Últimos Pallets (Sobras Finais que não fecharam 1 pallet inteiro do mesmo tipo de caixa)
    sobras_finais = [r for r in restantes if r["qtd"] > 0]
    sobras_finais.sort(key=lambda x: (-x["tipo_cx"], -x["qtd"], x["sku"]))

    if sobras_finais:
        camadas_residuais = []
        for t in sorted(set(r["tipo_cx"] for r in sobras_finais), reverse=True):
            itens_t = [(r["sku"], r["qtd"]) for r in sobras_finais if r["tipo_cx"] == t]
            cpf_t = next(r["cpf"] for r in sobras_finais if r["tipo_cx"] == t)
            camadas_residuais.extend(_montar_camadas_por_skus(itens_t, t, cpf_t))

        limite_final = 5
        while len(camadas_residuais) > limite_final:
            lote = camadas_residuais[:limite_final]
            camadas_residuais = camadas_residuais[limite_final:]
            pallets.append({
                "tipo": "Pallet Consolidado Final (Múltiplos SKUs)",
                "limite_fileiras": len(lote),
                "camadas": lote,
                "obs": "Consolidação das sobras finais antes do último pallet."
            })

        if camadas_residuais:
            if len(camadas_residuais) < 2 and pallets:
                doador = pallets[-1]
                if len(doador.get("camadas", [])) > 2:
                    camada_movida = doador["camadas"].pop()
                    camadas_residuais.insert(0, camada_movida)
                    doador["obs"] += " (1 fileira transferida para o último pallet para cumprir o mínimo de 2 fileiras)."

            pallets.append({
                "tipo": "Último Pallet (Consolidação de Sobras)",
                "limite_fileiras": len(camadas_residuais),
                "camadas": camadas_residuais,
                "obs": "Concentra as sobras finais de exportação."
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
                    "Altura": info.get("Altura", "-"),
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
    
    headers = ["Pallet", "SKU", "Produto", "Caixa Nº", "Qtd Caixas", "Altura", "Fileira", "Status"]
    ws.row_dimensions[1].height = 28
    
    for col_idx, header in enumerate(headers, 1):
        c = ws.cell(row=1, column=col_idx, value=header)
        c.fill = fill_cabecalho
        c.font = font_cabecalho
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = borda_cabecalho

    df_agrupado = (
        df_operador.groupby(["Pallet_Num", "SKU", "Produto", "Caixa Nº", "Altura", "Status Fileira"], as_index=False)
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
            ws.cell(row=linha_atual, column=6, value=int(row["Altura"]) if str(row["Altura"]).isdigit() else str(row["Altura"]))
            ws.cell(row=linha_atual, column=7, value=str(row["Fileiras"]))
            ws.cell(row=linha_atual, column=8, value=str(row["Status Fileira"]))
            
            for col_i in range(1, 9):
                cell_item = ws.cell(row=linha_atual, column=col_i)
                cell_item.fill = fill_pallet
                cell_item.border = borda_padrao
                cell_item.font = Font(name="Calibri", size=10)
                
                if col_i in [1, 2, 4, 5, 6, 8]:
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
        pdf.cell(0, 6, f"Pallet {num_p} - Altura do Pallet: {alt_pallet} fileiras - {_latin(df_p['Tipo Pallet'].iloc[0])}", border="B")
        pdf.ln(7)
        
        larguras = [22, 26, 60, 14, 18, 16, 30]
        titulos = ["Fileira", "SKU", "Produto", "N. Cx", "Qtd Cx", "Altura", "Status"]
        
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        for w, t in zip(larguras, titulos):
            pdf.cell(w, 6, t, border=1, fill=True, align="C")
        pdf.ln()
        
        pdf.set_font("Helvetica", "", 8)
        for _, r in df_p.iterrows():
            pdf.cell(larguras[0], 6, _latin(r["Fileira"]), border=1, align="C")
            pdf.cell(larguras[1], 6, str(r["SKU"]), border=1, align="C")
            pdf.cell(larguras[2], 6, _latin(r["Produto"])[:40], border=1)
            pdf.cell(larguras[3], 6, str(r["Caixa Nº"]), border=1, align="C")
            pdf.cell(larguras[4], 6, str(r["Qtd Caixas"]), border=1, align="C")
            pdf.cell(larguras[5], 6, str(r["Altura"]), border=1, align="C")
            pdf.cell(larguras[6], 6, _latin(r["Status Fileira"]), border=1, align="C")
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
        
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Total de Pallets", f"{len(resultado_pallets)}")
        c2.metric("📦 Total Geral de Caixas", f"{total_cx_global:,} cx".replace(",", "."))
        c3.metric("🧩 Total Geral de Peças", f"{total_pc_global:,} pçs".replace(",", "."))
        st.markdown("---")
        
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
        
        for num_p in sorted(df_operador["Pallet_Num"].unique()):
            df_p = df_operador[df_operador["Pallet_Num"] == num_p]
            total_cx_pallet = int(df_p["Qtd Caixas"].sum())
            altura_pallet = int(df_p["Altura_Pallet"].iloc[0])
            
            with st.expander(f"📦 {num_p} - {df_p['Tipo Pallet'].iloc[0]}  |  📐 Altura: {altura_pallet} fileiras", expanded=True):
                st.caption(f"Orientação: {df_p['Observação'].iloc[0]}")
                st.dataframe(
                    df_p[["Fileira", "SKU", "Produto", "Caixa Nº", "Qtd Caixas", "Altura", "Cx / Fileira", "Status Fileira"]],
                    use_container_width=True,
                    hide_index=True
                )
                
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
