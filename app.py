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

TIPO_SEQUENCIAL = "Pallet Fechado - SKU único, sequencial 🟢"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura 🟢"
TIPO_ALTURAS_DIFERENTES = "Pallet Fechado - mesma caixa, alturas diferentes 🟡"
TIPO_INTERMEDIARIO_FECHADO = (
    "Pallet Fechado - fileiras completas inteligentes 🟢"
)
TIPO_FINAL = "Pallet Misto Final / Sobras (Múltiplos tipos permitidos) 🟠"


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
    """
    Algoritmo de paletização orientado à operação.

    Princípios:
    1. Pallet completo de um único SKU é sempre priorizado.
    2. O mesmo SKU que ocupa vários pallets permanece sequencial.
    3. Depois dos pallets completos, trabalha-se com FILEIRAS como unidade
       física, evitando chamar de "fileira completa" uma quantidade parcial.
    4. Prioriza o mesmo número de caixa, depois a mesma altura e, por fim,
       combinações de alturas diferentes.
    5. Nenhum pallet pode ultrapassar 5 fileiras nem a capacidade máxima
       cadastrada de qualquer SKU.
    6. Sobras que não conseguem formar fileiras fechadas vão para pallets finais,
       sempre respeitando as capacidades.
    """
    skus = {}

    # -----------------------------
    # 1. Preparação dos SKUs
    # -----------------------------
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]

        cx_fileira = max(int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"]), 1)
        altura = max(min(int(prod["ALTURA"]), ALTURA_MAXIMA_FILEIRAS), 1)
        capacidade = max(int(prod["QUANTIDADE DE CAIXAS NO PALLET"]), 1)
        quantidade = max(int(item["Qtd_Caixas"]), 0)

        skus[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": int(prod.get("Ordem_Caixa", 0)),
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": cx_fileira,
            "Altura": altura,
            "Capacidade_Max": capacidade,
            "Restante": quantidade,
        }

    pallets = []

    def novo_pallet(tipo, itens, fileiras=None):
        pallets.append({
            "tipo": tipo,
            "itens": dict(itens),
            "fileiras": list(fileiras or []),
        })

    def adicionar_fileira(lista, sku, quantidade, completa=True):
        """Registra uma fileira física. Quantidade pode ser parcial apenas
        quando completa=False."""
        lista.append({
            "sku": sku,
            "qtd": int(quantidade),
            "completa": bool(completa),
        })

    def total_caixas(itens):
        return sum(itens.values())

    def capacidade_disponivel(itens, sku):
        return max(0, skus[sku]["Capacidade_Max"] - itens.get(sku, 0))

    def ordenar_skus(lista):
        return sorted(
            lista,
            key=lambda s: (-s["Ordem_Caixa"], -s["Altura"], s["SKU"])
        )

    ordem_skus = ordenar_skus(list(skus.values()))

    # -------------------------------------------------------
    # 2. Pallets completos: um SKU por pallet, sequenciais
    # -------------------------------------------------------
    for s in ordem_skus:
        cap = s["Capacidade_Max"]
        while s["Restante"] >= cap:
            itens = {s["SKU"]: cap}
            fileiras = []
            # Se a capacidade cadastrada for múltipla da fileira,
            # conseguimos representar todas as fileiras.
            qtd_fileiras = cap // s["Caixas_Por_Fileira"]
            if (
                qtd_fileiras > 0
                and qtd_fileiras * s["Caixas_Por_Fileira"] == cap
                and qtd_fileiras <= ALTURA_MAXIMA_FILEIRAS
            ):
                for _ in range(qtd_fileiras):
                    adicionar_fileira(
                        fileiras, s["SKU"], s["Caixas_Por_Fileira"], True
                    )
            novo_pallet(TIPO_SEQUENCIAL, itens, fileiras)
            s["Restante"] -= cap

    # -------------------------------------------------------
    # 3. Utilitários para montar pallets por fileiras
    # -------------------------------------------------------
    def candidatos_fileiras(tipo, altura_exata=None, minimo_altura=None):
        resultado = []
        for s in ordem_skus:
            if s["Ordem_Caixa"] != tipo or s["Restante"] <= 0:
                continue
            if altura_exata is not None and s["Altura"] != altura_exata:
                continue
            if minimo_altura is not None and s["Altura"] < minimo_altura:
                continue

            qtd_fileiras = s["Restante"] // s["Caixas_Por_Fileira"]
            qtd_fileiras = min(
                qtd_fileiras,
                s["Capacidade_Max"] // s["Caixas_Por_Fileira"],
                ALTURA_MAXIMA_FILEIRAS,
            )
            if qtd_fileiras > 0:
                resultado.append({
                    "sku": s["SKU"],
                    "fileiras": qtd_fileiras,
                    "cap_fileira": s["Caixas_Por_Fileira"],
                    "altura": s["Altura"],
                })
        return resultado

    def aplicar_fileiras(escolha, tipo_pallet):
        """Consome fileiras completas e cria um pallet."""
        itens = {}
        fileiras = []

        for sku, n_fileiras in escolha:
            s = skus[sku]
            qtd = n_fileiras * s["Caixas_Por_Fileira"]
            if qtd <= 0:
                continue

            itens[sku] = itens.get(sku, 0) + qtd
            s["Restante"] -= qtd

            for _ in range(n_fileiras):
                adicionar_fileira(
                    fileiras, sku, s["Caixas_Por_Fileira"], True
                )

        if itens:
            novo_pallet(tipo_pallet, itens, fileiras)

    def melhor_combinacao_fileiras(candidatos, limite=ALTURA_MAXIMA_FILEIRAS):
        """
        Seleciona até 'limite' fileiras.
        Critérios:
        - maximizar número de fileiras ocupadas;
        - preferir menos SKUs;
        - preferir maior altura base;
        - manter a ordem de caixa.
        """
        # Como um pallet tem no máximo 5 fileiras, usamos uma programação
        # dinâmica pequena e previsível em vez de uma busca combinatória que
        # poderia crescer muito com a quantidade de SKUs.
        estados = {0: []}

        for c in candidatos:
            sku = c["sku"]
            max_n = min(c["fileiras"], limite)
            novos = dict(estados)

            for usadas, escolha_atual in estados.items():
                for n in range(1, min(max_n, limite - usadas) + 1):
                    novo_total = usadas + n
                    # Um SKU aparece no máximo uma vez na escolha.
                    nova_escolha = escolha_atual + [(sku, n)]

                    anterior = novos.get(novo_total)
                    if anterior is None:
                        novos[novo_total] = nova_escolha
                    else:
                        # Empate na quantidade de fileiras:
                        # prefere menos SKUs e, depois, maior altura.
                        def score(escolha):
                            return (
                                -len(escolha),
                                min(
                                    skus[x]["Altura"] for x, _ in escolha
                                ),
                                max(
                                    skus[x]["Ordem_Caixa"] for x, _ in escolha
                                ),
                            )

                        if score(nova_escolha) > score(anterior):
                            novos[novo_total] = nova_escolha

            estados = novos

        if not estados:
            return []

        # Maximiza ocupação. Em empate, reduz a quantidade de SKUs.
        melhor_total = max(estados)
        candidatos_melhores = [
            escolha
            for total, escolha in estados.items()
            if total == melhor_total
        ]

        return max(
            candidatos_melhores,
            key=lambda escolha: (
                -len(escolha),
                min(skus[x]["Altura"] for x, _ in escolha),
                max(skus[x]["Ordem_Caixa"] for x, _ in escolha),
            ),
        )

    # -------------------------------------------------------
    # 4. Primeiro: pallets fechados da mesma caixa e mesma altura
    # -------------------------------------------------------
    tipos = sorted(
        {s["Ordem_Caixa"] for s in skus.values()},
        reverse=True,
    )

    for tipo in tipos:
        alturas = sorted(
            {
                s["Altura"]
                for s in ordem_skus
                if s["Ordem_Caixa"] == tipo and s["Restante"] > 0
            },
            reverse=True,
        )

        for altura in alturas:
            while True:
                candidatos = candidatos_fileiras(tipo, altura_exata=altura)
                if not candidatos:
                    break

                escolha = melhor_combinacao_fileiras(candidatos)
                if not escolha:
                    break

                aplicar_fileiras(escolha, TIPO_MESMA_ALTURA)

    # -------------------------------------------------------
    # 5. Depois: mesma caixa, permitindo alturas diferentes
    # -------------------------------------------------------
    for tipo in tipos:
        while True:
            candidatos = candidatos_fileiras(tipo)
            if not candidatos:
                break

            escolha = melhor_combinacao_fileiras(candidatos)
            if not escolha:
                break

            aplicar_fileiras(escolha, TIPO_ALTURAS_DIFERENTES)

    # -------------------------------------------------------
    # 6. Reunir sobras que não fecharam uma fileira
    # -------------------------------------------------------
    # Sobras parciais ficam separadas por SKU. Isso é importante para não
    # transformar uma quantidade parcial em uma falsa "fileira completa".
    sobras = {
        s["SKU"]: s["Restante"]
        for s in ordem_skus
        if s["Restante"] > 0
    }

    # -------------------------------------------------------
    # 7. Pallets finais: sobras, sem ultrapassar 5 fileiras
    # -------------------------------------------------------
    sobras_restantes = dict(sobras)

    while any(qtd > 0 for qtd in sobras_restantes.values()):
        candidatos = [
            s for s in ordem_skus
            if sobras_restantes.get(s["SKU"], 0) > 0
        ]
        if not candidatos:
            break

        # Prioriza a maior numeração de caixa e, em seguida, a maior altura.
        candidatos.sort(
            key=lambda s: (-s["Ordem_Caixa"], -s["Altura"], s["SKU"])
        )

        itens = {}
        fileiras = []
        slots = ALTURA_MAXIMA_FILEIRAS

        for s in candidatos:
            sku = s["SKU"]
            restante = sobras_restantes.get(sku, 0)
            if restante <= 0 or slots <= 0:
                continue

            disponivel = s["Capacidade_Max"] - itens.get(sku, 0)
            pegar = min(restante, disponivel)
            if pegar <= 0:
                continue

            # Cada SKU pode ocupar:
            # - várias fileiras fechadas; e
            # - no máximo uma fileira parcial.
            completas, parcial = divmod(pegar, s["Caixas_Por_Fileira"])
            fileiras_a_usar = completas + (1 if parcial else 0)

            # Respeita os slots físicos restantes.
            if fileiras_a_usar > slots:
                completas = min(completas, slots)
                parcial = 0
                fileiras_a_usar = completas

            if fileiras_a_usar <= 0:
                continue

            qtd_final = completas * s["Caixas_Por_Fileira"] + parcial

            itens[sku] = itens.get(sku, 0) + qtd_final
            sobras_restantes[sku] -= qtd_final
            skus[sku]["Restante"] -= qtd_final
            slots -= fileiras_a_usar

            for _ in range(completas):
                adicionar_fileira(
                    fileiras, sku, s["Caixas_Por_Fileira"], True
                )

            if parcial:
                adicionar_fileira(fileiras, sku, parcial, False)

        if itens:
            novo_pallet(TIPO_FINAL, itens, fileiras)
        else:
            raise ValueError(
                "Não foi possível acomodar as sobras sem ultrapassar "
                "a capacidade de 5 fileiras por pallet."
            )

    # -------------------------------------------------------
    # 8. Validação final
    # -------------------------------------------------------
    # Todo o pedido deve ter sido consumido.
    nao_consumidos = {
        sku: s["Restante"]
        for sku, s in skus.items()
        if s["Restante"] > 0
    }
    if nao_consumidos:
        raise ValueError(
            f"Não foi possível distribuir todas as caixas: {nao_consumidos}"
        )

    # Validações físicas antes de entregar o resultado.
    for p in pallets:
        if len(p["fileiras"]) > ALTURA_MAXIMA_FILEIRAS:
            raise ValueError(
                f"O pallet gerado possui mais de {ALTURA_MAXIMA_FILEIRAS} fileiras."
            )

        for sku, qtd in p["itens"].items():
            if qtd > skus[sku]["Capacidade_Max"]:
                raise ValueError(
                    f"O SKU {sku} ultrapassou sua capacidade máxima no pallet."
                )

    # -------------------------------------------------------
    # 9. DataFrame final
    # -------------------------------------------------------
    linhas = []

    for idx, p in enumerate(pallets, 1):
        # Calcula a quantidade real de fileiras físicas do pallet.
        fileiras_pallet = len(p["fileiras"])

        # Ordem da base para o topo pela numeração da caixa.
        itens_ord = sorted(
            p["itens"].items(),
            key=lambda kv: (
                -skus[kv[0]]["Ordem_Caixa"],
                kv[0],
            ),
        )

        for sku, qtd in itens_ord:
            s = skus[sku]

            # Quantidade de fileiras completas daquele SKU neste pallet.
            fileiras_sku = sum(
                1
                for f in p["fileiras"]
                if f["sku"] == sku and f["completa"]
            )
            parciais_sku = sum(
                1
                for f in p["fileiras"]
                if f["sku"] == sku and not f["completa"]
            )
            caixas_na_fileira_parcial = sum(
                f["qtd"]
                for f in p["fileiras"]
                if f["sku"] == sku and not f["completa"]
            )

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
                "Fileiras Completas SKU": fileiras_sku,
                "Fileiras Parciais SKU": parciais_sku,
                "Caixas na Fileira Parcial": caixas_na_fileira_parcial,
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
        pdf.cell(22, 6, "SKU", border=1)
        pdf.cell(52, 6, "Produto", border=1)
        pdf.cell(16, 6, "N. Caixa", border=1)
        pdf.cell(18, 6, "Qtd Caixas", border=1)
        pdf.cell(20, 6, "Qtd Peças", border=1)
        pdf.cell(18, 6, "Cx/Fileira", border=1)
        pdf.cell(14, 6, "F. Compl.", border=1)
        pdf.cell(14, 6, "F. Parc.", border=1)
        pdf.cell(16, 6, "Cx F. Parc.", border=1)
        pdf.ln()

        pdf.set_font("Helvetica", size=8)
        for _, row in df_p.iterrows():
            prod_nome = (
                str(row["Produto"])
                .encode("latin-1", "replace")
                .decode("latin-1")[:25]
            )
            pdf.cell(22, 6, str(row["SKU"]), border=1)
            pdf.cell(52, 6, prod_nome, border=1)
            pdf.cell(16, 6, str(row["Nº Caixa"]), border=1)
            pdf.cell(18, 6, str(row["Qtd Caixas"]), border=1)
            pdf.cell(20, 6, str(row["Total Peças"]), border=1)
            pdf.cell(18, 6, str(row["Caixas_Por_Fileira"]), border=1)
            pdf.cell(14, 6, str(row["Fileiras Completas SKU"]), border=1)
            pdf.cell(14, 6, str(row["Fileiras Parciais SKU"]), border=1)
            pdf.cell(16, 6, str(row["Caixas na Fileira Parcial"]), border=1)
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
                "**Composição detalhada (base para o topo, priorizando fileiras completas e a ordem da numeração de caixa). Fileiras parciais aparecem identificadas separadamente:**"
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
                    "Fileiras Completas SKU",
                    "Fileiras Parciais SKU",
                    "Caixas na Fileira Parcial",
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
