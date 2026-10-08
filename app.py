import os
import re
import math
from datetime import datetime
import pandas as pd
import streamlit as st

try:
    from fpdf import FPDF
    FPDF_DISPONIVEL = True
except ImportError:
    FPDF_DISPONIVEL = False

st.set_page_config(page_title="Sistema de Paletização - COMEX", page_icon="📦", layout="wide")

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
    
    # Agrupamento interno por Família (usado apenas no algoritmo de rota/separação)
    df["FAMILIA"] = df["SKU"].apply(lambda x: ".".join(x.split(".")[:2]) if "." in x else x[:4])
    return df

if not CAMINHO_EXCEL:
    st.error("⚠️ Arquivo 'COMEX.xlsx' não encontrado no diretório do aplicativo.")
    st.stop()

df_mestre = carregar_base_mestre(CAMINHO_EXCEL)

# --- INTERFACE DE ENTRADA DO PEDIDO ---
st.title("📦 Otimizador de Paletização para Exportação")
st.markdown("Preencha os itens manualmente ou faça o upload da planilha de pedido enviada pelo COMEX.")

tab_upload, tab_manual = st.tabs(["📁 Importar Planilha de Pedido", "✍️ Inserção Manual"])

if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

with tab_upload:
    arquivo_pedido = st.file_uploader("Selecione a planilha do pedido (.xlsx ou .csv):", type=["xlsx", "xls", "csv"])
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
                if st.button("📥 Carregar Itens da Planilha para o Pedido"):
                    st.session_state.carrinho = itens_importados
                    st.success(f"{len(itens_importados)} SKUs carregados com sucesso!")
            else:
                st.warning("A planilha deve conter ao menos as colunas 'SKU' e 'QUANTIDADE'.")
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")

with tab_manual:
    col_sel, col_qtd = st.columns([3, 1])
    opcoes = df_mestre["SKU"] + " - " + df_mestre["NOME DO PRODUTO"]
    prod_sel = col_sel.selectbox("Pesquisar SKU / Produto:", options=opcoes)
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
        st.success("Item adicionado!")

# --- RESUMO DO PEDIDO ---
st.markdown("---")
nome_cliente = st.text_input("Identificação do Pedido / Cliente:", placeholder="Ex: Exportação Pedido #45882")

if st.session_state.carrinho:
    df_carrinho = pd.DataFrame(st.session_state.carrinho)
    # Visualização limpa: SEM a coluna de família
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
    
    # Ordenação por Família de Produto internamente para reduzir deslocamento no estoque
    itens = sorted(itens_pedido, key=lambda x: (x["Familia"], x["Nº Caixa"], x["SKU"]))
    
    pool_fileiras = []
    caixas_soltas = []
    
    # 1. Pallets Fechados Monoproduto (100% Cheios)
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
            
    # 2. Consolidação de Caixas Soltas em Fileiras Mistas do Mesmo Tipo de Caixa
    soltas_agrupadas = {}
    for cs in caixas_soltas:
        t = cs["tipo_cx"]
        soltas_agrupadas.setdefault(t, []).append(cs)
        
    for t, lista_cs in soltas_agrupadas.items():
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
                ref = next(x for x in lista_cs if x["sku"] == s)
                ref["qtd"] = q
                
    # 3. Montar Pallets de Sobras com Fileiras Completas (Mesmo Tipo de Caixa)
    tipos_presentes = sorted(set(f["tipo_cx"] for f in pool_fileiras), reverse=True)
    
    for t in tipos_presentes:
        fils_t = [f for f in pool_fileiras if f["tipo_cx"] == t]
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
                
        while len(fils_t) >= min(f["h_max"] for f in fils_t):
            lim_h = min(f["h_max"] for f in fils_t[:min(f["h_max"] for f in fils_t)])
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

    # 4. Combinação de Diferentes Tipos de Caixa (Pallets Mistos com Fileiras Completas)
    while len(pool_fileiras) >= 4:
        h_lim = min(f["h_max"] for f in pool_fileiras[:4])
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

    # 5. Fechamento do Pallet Final (Regras 4, 5 e 6)
    soltas_finais = [cs for cs in caixas_soltas if cs["qtd"] > 0]
    
    if pool_fileiras or soltas_finais:
        camadas_final = []
        for f in pool_fileiras:
            camadas_final.append({"tipo_cx": f["tipo_cx"], "itens": f["itens"], "completa": True})
            
        if soltas_finais:
            itens_inc = {cs["sku"]: cs["qtd"] for cs in soltas_finais}
            camadas_final.append({"tipo_cx": soltas_finais[0]["tipo_cx"], "itens": itens_inc, "completa": False})
            
        # Regra 4: Último pallet deve ter no mínimo 2 fileiras
        if len(camadas_final) < 2 and pallets:
            doador = pallets[-1]
            if len(doador["camadas"]) > 2:
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
        for pos, c in enumerate(p["camadas"], 1):
            for sku, qtd in c["itens"].items():
                info = mapa_itens[sku]
                linhas.append({
                    "Pallet": f"Pallet {idx}",
                    "Tipo Pallet": p["tipo"],
                    "Fileira": f"{pos}ª fileira",
                    "SKU": sku,
                    "Produto": info["Produto"],
                    "Caixa Nº": info["Nº Caixa"],
                    "Qtd Caixas": qtd,
                    "Cx / Fileira": info["Caixas_Por_Fileira"],
                    "Status Fileira": "Completa" if c["completa"] else "Incompleta (Topo)",
                    "Observação": p["obs"]
                })
    return pd.DataFrame(linhas)

if st.button("🚀 Otimizar e Gerar Instruções de Paletização"):
    if not st.session_state.carrinho:
        st.warning("Adicione produtos ou importe uma planilha para processar.")
    else:
        resultado_pallets = otimizar_paletizacao(st.session_state.carrinho)
        df_operador = gerar_dataframe_operador(resultado_pallets, st.session_state.carrinho)
        
        st.subheader("📋 Resumo da Carga Paletizada")
        st.success(f"Carga otimizada em **{len(resultado_pallets)} pallets**.")
        
        # Exibição individual para os operadores (sem a coluna de família)
        for num_p in df_operador["Pallet"].unique():
            df_p = df_operador[df_operador["Pallet"] == num_p]
            with st.expander(f"📦 {num_p} - {df_p['Tipo Pallet'].iloc[0]} ({df_p['Qtd Caixas'].sum()} Caixas)", expanded=True):
                st.caption(f"Orientação: {df_p['Observação'].iloc[0]}")
                st.dataframe(
                    df_p[["Fileira", "SKU", "Produto", "Caixa Nº", "Qtd Caixas", "Cx / Fileira", "Status Fileira"]],
                    use_container_width=True,
                    hide_index=True
                )
