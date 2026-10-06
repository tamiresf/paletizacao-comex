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


# --- 6. ALGORITMO COMEX - REGRAS REVISADAS DE PALETIZAÇÃO ---
ALTURA_MAXIMA_FILEIRAS = 5
MINIMO_FILEIRAS_ULTIMO_PALLET = 2

TIPO_SEQUENCIAL = "Pallet Fechado - SKU unico, sequencial 🟢"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura 🟢"
TIPO_ALTURAS_DIFERENTES = "Pallet Fechado - mesma caixa, alturas diferentes 🟡"
TIPO_INTERMEDIARIO_FECHADO = "Pallet Fechado - fileiras completas 🟢"
TIPO_FINAL = "Pallet Misto Inteligente / Final (Permite Sobras) 🟠"


def _achar_combinacao_exata(unidades, alvo):
    unidades = sorted(unidades, key=lambda u: (-u[1], str(u[0])))
    memo = {}

    def rec(i, restante):
        if restante == 0:
            return ()
        if i >= len(unidades) or restante < 0:
            return None
        chave = (i, restante)
        if chave in memo:
            return memo[chave]
        resultado = None
        if unidades[i][1] <= restante:
            sub = rec(i + 1, restante - unidades[i][1])
            if sub is not None:
                resultado = (i,) + sub
        if resultado is None:
            resultado = rec(i + 1, restante)
        memo[chave] = resultado
        return resultado

    achado = rec(0, alvo)
    if achado is None:
        return None
    return [unidades[i] for i in achado]


def processar_pallets_operador(carrinho, df_produtos):
    skus = {}
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]
        cx_fileira = max(int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"]), 1)
        altura = max(min(int(prod["ALTURA"]), ALTURA_MAXIMA_FILEIRAS), 1)
        skus[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": int(prod.get("Ordem_Caixa", 0)),
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": cx_fileira,
            "Altura": altura,
            "Capacidade_Max": max(int(prod["QUANTIDADE DE CAIXAS NO PALLET"]), 1),
            "Restante": int(item["Qtd_Caixas"]),
        }

    pallets = []

    def novo_pallet(tipo, itens):
        pallets.append({"tipo": tipo, "itens": dict(itens)})

    def cx_fileira_do_tipo(ordem):
        return max(
            s["Caixas_Por_Fileira"]
            for s in skus.values()
            if s["Ordem_Caixa"] == ordem
        )

    def fileiras_do_lote(itens):
        por_tipo = {}
        for sku, qtd in itens.items():
            por_tipo[skus[sku]["Ordem_Caixa"]] = (
                por_tipo.get(skus[sku]["Ordem_Caixa"], 0) + qtd
            )
        return sum(
            -(-qtd // cx_fileira_do_tipo(t)) for t, qtd in por_tipo.items()
        )

    ordem_skus = sorted(
        skus.values(), key=lambda s: (-s["Ordem_Caixa"], s["SKU"])
    )

    # ETAPA 1: Pallets completos de um único SKU (Sequenciais)
    for s in ordem_skus:
        while s["Restante"] >= s["Capacidade_Max"]:
            novo_pallet(TIPO_SEQUENCIAL, {s["SKU"]: s["Capacidade_Max"]})
            s["Restante"] -= s["Capacidade_Max"]

    # ETAPA 2: Pallets fechados do mesmo tipo de caixa e mesma altura ou alturas diferentes
    tipos = sorted({s["Ordem_Caixa"] for s in skus.values()}, reverse=True)
    for tipo in tipos:
        skus_tipo = [s for s in ordem_skus if s["Ordem_Caixa"] == tipo]

        def unidades(filtro):
            return [
                (s["SKU"], s["Restante"] // s["Caixas_Por_Fileira"])
                for s in skus_tipo
                if filtro(s) and s["Restante"] // s["Caixas_Por_Fileira"] > 0
            ]

        def fechar(escolha, tipo_pallet):
            itens = {}
            for sku, fileiras in escolha:
                qtd = fileiras * skus[sku]["Caixas_Por_Fileira"]
                itens[sku] = qtd
                skus[sku]["Restante"] -= qtd
            novo_pallet(tipo_pallet, itens)

        for altura in sorted({s["Altura"] for s in skus_tipo}, reverse=True):
            while True:
                escolha = _achar_combinacao_exata(
                    unidades(lambda s, a=altura: s["Altura"] == a), altura
                )
                if not escolha:
                    break
                fechar(escolha, TIPO_MESMA_ALTURA)

        achou = True
        while achou:
            achou = False
            for alvo in sorted(
                {s["Altura"] for s in skus_tipo}, reverse=True
            ):
                elegiveis = unidades(lambda s, a=alvo: s["Altura"] >= a)
                for sku_base, fil_base in [
                    u for u in elegiveis if skus[u[0]]["Altura"] == alvo
                ]:
                    outros = [u for u in elegiveis if u[0] != sku_base]
                    resto = (
                        _achar_combinacao_exata(outros, alvo - fil_base)
                        if fil_base < alvo
                        else []
                    )
                    if resto is not None:
                        fechar(
                            [(sku_base, fil_base)] + resto,
                            TIPO_ALTURAS_DIFERENTES,
                        )
                        achou = True
                        break
                if achou:
                    break

    # ETAPA 3: Separação estrita entre fileiras completas (para pallets intermediários) e sobras (para o pallet final)
    fileiras_completas_todas = []
    fileiras_incompletas_todas = []

    for tipo in tipos:
        cpf = cx_fileira_do_tipo(tipo)
        skus_tipo = [s for s in ordem_skus if s["Ordem_Caixa"] == tipo and s["Restante"] > 0]
        
        # Primeiro isola as fileiras completas puras por SKU
        for s in skus_tipo:
            qtd = s["Restante"]
            restantes_sku = s["Restante"] % cpf
            completas = qtd - restantes_sku
            if completas > 0:
                num_fil = completas // cpf
                fileiras_completas_todas.append({
                    "tipo": tipo,
                    "altura": s["Altura"],
                    "itens": {s["SKU"]: completas},
                    "incompleta": False
                })
                s["Restante"] = restantes_sku

        # Tenta combinar sobras do mesmo tipo e altura para formar fileiras completas adicionais
        sobras_ativas = [(s["SKU"], s["Restante"], s["Altura"]) for s in skus_tipo if s["Restante"] > 0]
        sobras_ativas.sort(key=lambda x: (-x[2], x[0]))

        i = 0
        while i < len(sobras_ativas):
            sku1, qtd1, alt1 = sobras_ativas[i]
            if qtd1 == 0:
                i += 1
                continue
            
            fileira_atual = {sku1: min(cpf, qtd1)}
            cheia = fileira_atual[sku1]
            qtd1 -= fileira_atual[sku1]
            
            if cheia < cpf:
                for j in range(i + 1, len(sobras_ativas)):
                    sku2, qtd2, alt2 = sobras_ativas[j]
                    if qtd2 > 0 and alt2 == alt1:
                        pega = min(cpf - cheia, qtd2)
                        fileira_atual[sku2] = fileira_atual.get(sku2, 0) + pega
                        cheia += pega
                        qtd2 -= pega
                        sobras_ativas[j] = (sku2, qtd2, alt2)
                        if cheia == cpf:
                            break

            if cheia == cpf:
                fileiras_completas_todas.append({
                    "tipo": tipo,
                    "altura": min(skus[k]["Altura"] for k in fileira_atual),
                    "itens": fileira_atual,
                    "incompleta": False
                })
                sobras_ativas[i] = (sku1, qtd1, alt1)
                if qtd1 == 0:
                    i += 1
            else:
                # Se após as tentativas ainda não formou fileira completa, vai para as sobras reais (último pallet)
                for sku_inc, qtd_inc in fileira_atual.items():
                    fileiras_incompletas_todas.append({
                        "tipo": tipo,
                        "altura": skus[sku_inc]["Altura"],
                        "itens": {sku_inc: qtd_inc},
                        "incompleta": True
                    })
                sobras_ativas[i] = (sku1, 0, alt1)
                i += 1

        for s in skus_tipo:
            s["Restante"] = 0

    def juntar(lista_fileiras):
        itens = {}
        for f in lista_fileiras:
            if f and "itens" in f:
                for sku, qtd in f["itens"].items():
                    itens[sku] = itens.get(sku, 0) + qtd
        return itens

    def capacidade_max_atingida(lista_fileiras, nova_fileira):
        temp_itens = juntar(
            lista_fileiras + ([nova_fileira] if nova_fileira else [])
        )
        for sku, qtd in temp_itens.items():
            if qtd > skus[sku]["Capacidade_Max"]:
                return True
        return False

    # Montagem dos pallets intermediários estritamente com fileiras completas (sem sobras)
    blocos_intermediarios = []
    bloco_atual = []

    for f in fileiras_completas_todas:
        tipos_no_bloco = {skus[sku]["Ordem_Caixa"] for item in bloco_atual for sku in item["itens"]}
        tipos_no_bloco.add(f["tipo"])
        
        if (
            len(bloco_atual) >= ALTURA_MAXIMA_FILEIRAS
            or len(tipos_no_bloco) > 2
            or capacidade_max_atingida(bloco_atual, f)
        ):
            if bloco_atual:
                blocos_intermediarios.append(bloco_atual)
            bloco_atual = [f]
        else:
            bloco_atual.append(f)

    if bloco_atual:
        blocos_intermediarios.append(bloco_atual)

    # Criação dos pallets intermediários fechados
    for bloco in blocos_intermediarios:
        novo_pallet(TIPO_INTERMEDIARIO_FECHADO, juntar(bloco))

    # Montagem do último pallet (onde entram as sobras e fileiras incompletas)
    if fileiras_incompletas_todas:
        bloco_final = []
        for f in fileiras_incompletas_todas:
            tipos_no_bloco = {skus[sku]["Ordem_Caixa"] for item in bloco_final for sku in item["itens"]}
            tipos_no_bloco.add(f["tipo"])
            if len(bloco_final) >= ALTURA_MAXIMA_FILEIRAS or len(tipos_no_bloco) > 2 or capacidade_max_atingida(bloco_final, f):
                if bloco_final:
                    novo_pallet(TIPO_FINAL, juntar(bloco_final))
                bloco_final = [f]
            else:
                bloco_final.append(f)
        if bloco_final:
            novo_pallet(TIPO_FINAL, juntar(bloco_final))

    linhas = []
    for idx, p in enumerate(pallets, 1):
        itens_ord = sorted(
            p["itens"].items(),
            key=lambda kv: (-skus[kv[0]]["Ordem_Caixa"], kv[0]),
        )
        fileiras_pallet = fileiras_do_lote(p["itens"])
        for sku, qtd in itens_ord:
            s = skus[sku]
            linhas.append({
                "Pallet_Num": idx,
                "ID": f"Pallet {idx:02d}",
                "Tipo": p["tipo"],
                "SKU": sku,
                "Produto": s["Produto"],
                "Nº Caixa": s["Nº Caixa"],
                "Caixas_Por_Fileira": s["Caixas_Por_Fileira"],
                "Quantidade_Fileiras": s["Altura"],
                "Qtd Caixas": qtd,
                "Fileiras no Pallet": fileiras_pallet,
                "Total Peças": qtd * s["Pecas_Por_Caixa"],
                "Ordem_Caixa": s["Ordem_Caixa"],
            })
    return pd.DataFrame(linhas)


# --- 7. GERADOR DE PDF COM CONTROLE DE QUEBRA DE PÁGINA ---
def gerar_pdf(df_pallets, cliente, data_str):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "MUSTAD - Relatório de Paletização", align="C")
    pdf.ln(7)

    nome_cliente_formatado = cliente.strip() if cliente else "Não Informado"
    cliente_pdf = (
        nome_cliente_formatado.encode("latin-1", "replace").decode("latin-1")
    )

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
            tipo_raw.replace("🟢", "")
            .replace("🟡", "")
            .replace("🟠", "")
            .strip()
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
    pallets_unicos = df_pallets.sort_values("Pallet_Num")["ID"].unique()
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
            f"📌 {p_id} - Total de Caixas: {total_cx} cx | Total de Peças: {total_pc} peças | {int(df_p['Fileiras no Pallet'].iloc[0])} fileiras ({tipo_pallet})",
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
                    "Fileiras no Pallet",
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
