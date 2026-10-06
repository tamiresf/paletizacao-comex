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


# --- 6. ALGORITMO COMEX - V2: OTIMIZAÇÃO DE OCUPAÇÃO DOS PALLETS ---
ALTURA_MAXIMA_FILEIRAS = 5

TIPO_SEQUENCIAL = "Pallet Fechado - SKU único, sequencial 🟢"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura 🟢"
TIPO_ALTURAS_DIFERENTES = "Pallet Fechado - mesma caixa, alturas diferentes 🟡"
TIPO_INTERMEDIARIO_FECHADO = "Pallet Fechado - tipos diferentes, fileiras completas 🟢"
TIPO_FINAL = "Pallet Misto Final / Sobras (Múltiplos tipos permitidos) 🟠"


def processar_pallets_operador(carrinho, df_produtos):
    """
    V2 - Algoritmo de paletização orientado à operação.

    Objetivo principal:
        reduzir a quantidade total de pallets, sem perder as regras físicas.

    Ordem de decisão:
        1. Pallets completos de um único SKU permanecem sequenciais.
        2. Para os demais, procura-se o MELHOR pallet possível antes de
           consumir qualquer caixa: maior ocupação, respeitando no máximo
           5 fileiras e a capacidade máxima de cada SKU.
        3. Dentro de ocupações equivalentes, prioriza-se:
             a) mesmo tipo de caixa + mesma altura;
             b) mesmo tipo de caixa + alturas diferentes;
             c) tipos diferentes de caixa + mesma altura;
             d) mistura final apenas para sobras parciais.
        4. Fileiras completas nunca são quebradas nas etapas 2 e 3.
        5. Sobras parciais só são tratadas depois que todas as combinações
           de fileiras completas foram esgotadas.

    Observação importante:
        "Pallet fechado" pode conter mais de um SKU. O que importa é que
        todas as fileiras sejam completas e que as capacidades cadastradas
        sejam respeitadas.
    """
    skus = {}

    # -------------------------------------------------------
    # 1. PREPARAÇÃO DOS SKUS
    # -------------------------------------------------------
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]

        cpf = max(int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"]), 1)
        altura = max(min(int(prod["ALTURA"]), ALTURA_MAXIMA_FILEIRAS), 1)
        capacidade = max(int(prod["QUANTIDADE DE CAIXAS NO PALLET"]), 1)
        quantidade = max(int(item["Qtd_Caixas"]), 0)

        skus[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": int(prod.get("Ordem_Caixa", 0)),
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": cpf,
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

    def adicionar_fileira(fileiras, sku, qtd, completa=True):
        fileiras.append({
            "sku": sku,
            "qtd": int(qtd),
            "completa": bool(completa),
        })

    ordem_skus = sorted(
        skus.values(),
        key=lambda s: (-s["Ordem_Caixa"], -s["Altura"], s["SKU"]),
    )

    # -------------------------------------------------------
    # 2. PALLETS COMPLETOS DE UM SKU - SEMPRE SEQUENCIAIS
    # -------------------------------------------------------
    for s in ordem_skus:
        cap = s["Capacidade_Max"]
        while s["Restante"] >= cap:
            fileiras = []
            # A capacidade cadastrada é a regra de quantidade de caixas.
            # Se ela não for divisível pela quantidade por fileira, ainda
            # assim o pallet é válido pela capacidade; a composição física
            # será indicada como fileiras + eventual quantidade residual.
            completas, parcial = divmod(cap, s["Caixas_Por_Fileira"])
            completas = min(completas, ALTURA_MAXIMA_FILEIRAS)
            consumivel = completas * s["Caixas_Por_Fileira"]

            # Só fazemos o pallet fechado de SKU único diretamente quando
            # conseguimos representar a capacidade inteira em até 5 fileiras.
            if consumivel != cap:
                break

            for _ in range(completas):
                adicionar_fileira(fileiras, s["SKU"], s["Caixas_Por_Fileira"], True)

            novo_pallet(TIPO_SEQUENCIAL, {s["SKU"]: cap}, fileiras)
            s["Restante"] -= cap

    # -------------------------------------------------------
    # 3. FUNÇÕES DE BUSCA DE CANDIDATOS
    # -------------------------------------------------------
    def candidatos_disponiveis():
        return [
            s for s in ordem_skus
            if s["Restante"] >= s["Caixas_Por_Fileira"]
        ]

    def pode_usar(s, qtd_fileiras):
        if qtd_fileiras <= 0:
            return False
        qtd = qtd_fileiras * s["Caixas_Por_Fileira"]
        return (
            qtd <= s["Restante"]
            and qtd <= s["Capacidade_Max"]
            and qtd_fileiras <= ALTURA_MAXIMA_FILEIRAS
        )

    def capacidade_pallet_da_escolha(escolha):
        """
        Capacidade TOTAL permitida para um pallet.

        Para um pallet com mais de um SKU, usamos o menor limite de
        capacidade entre os SKUs participantes. Assim, nunca permitimos que
        uma combinação mista ultrapasse a capacidade do SKU mais restritivo.
        """
        if not escolha:
            return 0
        return min(skus[sku]["Capacidade_Max"] for sku, _ in escolha)

    def gerar_escolhas(candidatos, limite=ALTURA_MAXIMA_FILEIRAS):
        """Gera combinações de até 5 fileiras respeitando capacidade TOTAL."""
        estados = {0: []}

        for s in candidatos:
            cpf = s["Caixas_Por_Fileira"]
            max_n = min(
                s["Restante"] // cpf,
                s["Capacidade_Max"] // cpf,
                limite,
            )
            if max_n <= 0:
                continue

            novos = dict(estados)
            for usadas, escolha in estados.items():
                for n in range(1, min(max_n, limite - usadas) + 1):
                    total = usadas + n
                    nova = escolha + [(s["SKU"], n)]

                    # A capacidade máxima é do PALLET, não apenas do SKU.
                    # Para mistura, vale o menor limite entre os SKUs presentes.
                    caixas_nova = sum(
                        qtd_fileiras * skus[sku]["Caixas_Por_Fileira"]
                        for sku, qtd_fileiras in nova
                    )
                    capacidade_nova = capacidade_pallet_da_escolha(nova)
                    if caixas_nova > capacidade_nova:
                        continue

                    anterior = novos.get(total)
                    if anterior is None:
                        novos[total] = nova
                    else:
                        # Mantém a melhor composição para a mesma quantidade
                        # de fileiras: menos SKUs e maior ordem de caixa.
                        def desempate(e):
                            return (
                                -len(e),
                                max(skus[x]["Ordem_Caixa"] for x, _ in e),
                            )

                        if desempate(nova) > desempate(anterior):
                            novos[total] = nova

            estados = novos

        return [e for total, e in estados.items() if total > 0]

    def caracteristicas(escolha):
        tipos = {skus[sku]["Ordem_Caixa"] for sku, _ in escolha}
        alturas = {skus[sku]["Altura"] for sku, _ in escolha}
        caixas = sum(
            n * skus[sku]["Caixas_Por_Fileira"]
            for sku, n in escolha
        )
        fileiras = sum(n for _, n in escolha)
        return caixas, fileiras, tipos, alturas

    def classificar_escolha(escolha):
        """
        Classifica a qualidade operacional da combinação.

        3 = mesmo tipo + mesma altura
        2 = mesmo tipo + alturas diferentes
        1 = tipos diferentes + mesma altura
        0 = combinação de tipos/alturas diferentes (não usada nas etapas
            normais, mas mantida para segurança).
        """
        _, _, tipos, alturas = caracteristicas(escolha)
        if len(tipos) == 1 and len(alturas) == 1:
            return 3
        if len(tipos) == 1:
            return 2
        if len(alturas) == 1:
            return 1
        return 0

    def pontuacao(escolha):
        caixas, fileiras, tipos, alturas = caracteristicas(escolha)
        classe = classificar_escolha(escolha)

        # A quantidade de caixas é o critério dominante, pois o objetivo é
        # reduzir pallets. Depois entram as regras de simplicidade operacional.
        return (
            caixas,
            fileiras,
            classe,
            -len(escolha),
            -len(tipos),
            -len(alturas),
            max(skus[sku]["Ordem_Caixa"] for sku, _ in escolha),
        )

    def escolher_melhor(candidatos):
        escolhas = gerar_escolhas(candidatos)
        if not escolhas:
            return []
        return max(escolhas, key=pontuacao)

    def consumir(escolha, tipo_pallet):
        itens = {}
        fileiras = []

        # Validação global antes de consumir qualquer estoque.
        capacidade_pallet = capacidade_pallet_da_escolha(escolha)
        total_caixas = sum(
            n * skus[sku]["Caixas_Por_Fileira"] for sku, n in escolha
        )
        if total_caixas > capacidade_pallet:
            raise ValueError(
                f"Pallet inválido: {total_caixas} caixas > "
                f"capacidade máxima permitida de {capacidade_pallet} caixas."
            )

        for sku, n in escolha:
            s = skus[sku]
            qtd = n * s["Caixas_Por_Fileira"]

            if not pode_usar(s, n):
                raise ValueError(
                    f"Combinação inválida para o SKU {sku}: {qtd} caixas."
                )

            itens[sku] = itens.get(sku, 0) + qtd
            s["Restante"] -= qtd

            for _ in range(n):
                adicionar_fileira(fileiras, sku, s["Caixas_Por_Fileira"], True)

        novo_pallet(tipo_pallet, itens, fileiras)

    # -------------------------------------------------------
    # 4. MONTAGEM OTIMIZADA DOS PALLETS FECHADOS
    # -------------------------------------------------------
    # Importante: não processamos um tipo de caixa inteiro de uma vez.
    # A cada pallet, o sistema olha novamente TODOS os SKUs disponíveis.
    # Isso evita o erro da versão anterior em que, por exemplo, 3 fileiras
    # de um tipo eram consumidas antes de perceber que poderiam completar
    # 5 fileiras junto com outro tipo de caixa.
    while True:
        candidatos = candidatos_disponiveis()
        if not candidatos:
            break

        # 4.1 Primeiro tenta encontrar o melhor pallet exclusivamente dentro
        # de um tipo + mesma altura.
        melhores_mesmo_tipo_altura = []
        for tipo in sorted({s["Ordem_Caixa"] for s in candidatos}, reverse=True):
            for altura in sorted(
                {s["Altura"] for s in candidatos if s["Ordem_Caixa"] == tipo},
                reverse=True,
            ):
                grupo = [
                    s for s in candidatos
                    if s["Ordem_Caixa"] == tipo and s["Altura"] == altura
                ]
                escolha = escolher_melhor(grupo)
                if escolha:
                    melhores_mesmo_tipo_altura.append(escolha)

        melhor_1 = max(melhores_mesmo_tipo_altura, key=pontuacao) if melhores_mesmo_tipo_altura else []

        # 4.2 Também calcula as alternativas mais amplas ANTES de consumir.
        # Assim, uma combinação de 5 fileiras com tipos diferentes pode vencer
        # duas combinações separadas de 3 + 2 fileiras.
        alternativas = []

        # Mesmo tipo, alturas diferentes.
        for tipo in sorted({s["Ordem_Caixa"] for s in candidatos}, reverse=True):
            grupo = [s for s in candidatos if s["Ordem_Caixa"] == tipo]
            escolha = escolher_melhor(grupo)
            if escolha:
                alternativas.append(escolha)

        # Tipos diferentes, mesma altura.
        for altura in sorted({s["Altura"] for s in candidatos}, reverse=True):
            grupo = [s for s in candidatos if s["Altura"] == altura]
            tipos_grupo = {s["Ordem_Caixa"] for s in grupo}
            if len(tipos_grupo) >= 2:
                escolha = escolher_melhor(grupo)
                if escolha and len({skus[x]["Ordem_Caixa"] for x, _ in escolha}) >= 2:
                    alternativas.append(escolha)

        # Escolhe globalmente a combinação que mais reduz a quantidade de
        # pallets. Em empate, segue a prioridade operacional.
        todas = []
        if melhor_1:
            todas.append(melhor_1)
        todas.extend(alternativas)

        if not todas:
            break

        melhor = max(todas, key=pontuacao)
        classe = classificar_escolha(melhor)

        if classe == 3:
            tipo_saida = TIPO_MESMA_ALTURA
        elif classe == 2:
            tipo_saida = TIPO_ALTURAS_DIFERENTES
        elif classe == 1:
            tipo_saida = TIPO_INTERMEDIARIO_FECHADO
        else:
            # Esta situação não deveria ocorrer nas alternativas normais.
            break

        consumir(melhor, tipo_saida)

    # -------------------------------------------------------
    # 5. SOBRAS PARCIAIS - ÚLTIMA ETAPA
    # -------------------------------------------------------
    # Antes de abrir um pallet novo, tenta encaixar cada sobra parcial em um
    # pallet já existente que ainda tenha espaço físico e capacidade. Isso é
    # essencial para a redução real de pallets: por exemplo, 12 + 5 caixas
    # do mesmo SKU devem preferencialmente permanecer no MESMO pallet.
    def adicionar_sobra_a_pallet_existente(s):
        sku = s["SKU"]
        qtd = s["Restante"]
        if qtd <= 0:
            return False

        candidatos = []
        for idx, p in enumerate(pallets):
            if len(p["fileiras"]) >= ALTURA_MAXIMA_FILEIRAS:
                continue

            # A capacidade restante é GLOBAL do pallet. Para pallets mistos,
            # o limite é o menor Capacidade_Max entre todos os SKUs presentes.
            capacidades_pallet = [skus[x]["Capacidade_Max"] for x in p["itens"]]
            capacidade_global = min(capacidades_pallet) if capacidades_pallet else s["Capacidade_Max"]
            capacidade_global = min(capacidade_global, s["Capacidade_Max"])
            total_atual = sum(p["itens"].values())
            capacidade = capacidade_global - total_atual
            if capacidade <= 0:
                continue

            # Para inserir uma sobra parcial, priorizamos pallets que já
            # possuam o mesmo tipo e a mesma altura. Em seguida, mesmo tipo.
            tipos_p = {skus[x]["Ordem_Caixa"] for x in p["itens"]}
            alturas_p = {skus[x]["Altura"] for x in p["itens"]}

            if tipos_p == {s["Ordem_Caixa"]} and alturas_p == {s["Altura"]}:
                prioridade = 3
            elif tipos_p == {s["Ordem_Caixa"]}:
                prioridade = 2
            elif alturas_p == {s["Altura"]}:
                prioridade = 1
            else:
                prioridade = 0

            candidatos.append((prioridade, len(p["fileiras"]), idx, capacidade))

        if not candidatos:
            return False

        # Primeiro maior compatibilidade; depois pallets mais cheios, para
        # evitar deixar vários pallets parcialmente ocupados.
        _, _, idx, capacidade = max(candidatos, key=lambda x: (x[0], x[1], -x[2]))
        p = pallets[idx]
        pegar = min(qtd, capacidade)
        if pegar <= 0:
            return False

        p["itens"][sku] = p["itens"].get(sku, 0) + pegar
        adicionar_fileira(p["fileiras"], sku, pegar, False)
        s["Restante"] -= pegar

        # Se o pallet ganhou uma sobra, deixa o tipo explicitamente como
        # pallet final/misto, pois agora ele contém uma fileira parcial.
        p["tipo"] = TIPO_FINAL
        return True

    # Primeiro tenta aproveitar pallets já criados.
    for s in ordem_skus:
        if s["Restante"] > 0:
            adicionar_sobra_a_pallet_existente(s)

    # Se ainda houver sobras, cria novos pallets finais.
    while any(s["Restante"] > 0 for s in ordem_skus):
        disponiveis = [s for s in ordem_skus if s["Restante"] > 0]
        disponiveis.sort(
            key=lambda s: (-s["Ordem_Caixa"], -s["Altura"], s["SKU"])
        )

        itens = {}
        fileiras = []
        slots = ALTURA_MAXIMA_FILEIRAS
        capacidade_pallet = min(s["Capacidade_Max"] for s in disponiveis)

        # Primeiro consome fileiras completas.
        for s in disponiveis:
            if slots <= 0:
                break

            sku = s["SKU"]
            cpf = s["Caixas_Por_Fileira"]
            capacidade_restante_global = capacidade_pallet - sum(itens.values())
            capacidade_restante_sku = s["Capacidade_Max"] - itens.get(sku, 0)
            completas = min(
                s["Restante"] // cpf,
                capacidade_restante_global // cpf,
                capacidade_restante_sku // cpf,
                slots,
            )

            if completas:
                qtd = completas * cpf
                itens[sku] = itens.get(sku, 0) + qtd
                s["Restante"] -= qtd
                slots -= completas
                for _ in range(completas):
                    adicionar_fileira(fileiras, sku, cpf, True)

        # Depois usa as posições restantes para parciais.
        for s in disponiveis:
            if slots <= 0 or s["Restante"] <= 0:
                continue

            sku = s["SKU"]
            capacidade_restante_global = capacidade_pallet - sum(itens.values())
            capacidade_restante_sku = s["Capacidade_Max"] - itens.get(sku, 0)
            pegar = min(s["Restante"], capacidade_restante_global, capacidade_restante_sku)
            if pegar <= 0:
                continue

            itens[sku] = itens.get(sku, 0) + pegar
            s["Restante"] -= pegar
            adicionar_fileira(fileiras, sku, pegar, False)
            slots -= 1

        if not itens:
            raise ValueError("Não foi possível acomodar as sobras restantes.")

        novo_pallet(TIPO_FINAL, itens, fileiras)

    # -------------------------------------------------------
    # 6. VALIDAÇÃO FINAL
    # -------------------------------------------------------
    nao_consumidos = {
        sku: s["Restante"]
        for sku, s in skus.items()
        if s["Restante"] > 0
    }
    if nao_consumidos:
        raise ValueError(
            f"Não foi possível distribuir todas as caixas: {nao_consumidos}"
        )

    for p in pallets:
        if len(p["fileiras"]) > ALTURA_MAXIMA_FILEIRAS:
            raise ValueError(
                f"O pallet gerado possui mais de {ALTURA_MAXIMA_FILEIRAS} fileiras."
            )

        capacidade_global = min(
            skus[sku]["Capacidade_Max"] for sku in p["itens"]
        ) if p["itens"] else 0
        total_pallet = sum(p["itens"].values())
        if total_pallet > capacidade_global:
            raise ValueError(
                f"Pallet inválido: {total_pallet} caixas > "
                f"capacidade máxima de {capacidade_global} caixas."
            )

        for sku, qtd in p["itens"].items():
            if qtd > skus[sku]["Capacidade_Max"]:
                raise ValueError(
                    f"O SKU {sku} ultrapassou sua capacidade máxima no pallet."
                )

    # -------------------------------------------------------
    # 7. DATAFRAME FINAL
    # -------------------------------------------------------
    linhas = []

    for idx, p in enumerate(pallets, 1):
        fileiras_pallet = len(p["fileiras"])

        itens_ord = sorted(
            p["itens"].items(),
            key=lambda kv: (-skus[kv[0]]["Ordem_Caixa"], kv[0]),
        )

        for sku, qtd in itens_ord:
            s = skus[sku]
            fileiras_sku = sum(
                1 for f in p["fileiras"]
                if f["sku"] == sku and f["completa"]
            )
            parciais_sku = sum(
                1 for f in p["fileiras"]
                if f["sku"] == sku and not f["completa"]
            )
            caixas_parcial = sum(
                f["qtd"] for f in p["fileiras"]
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
                "Caixas na Fileira Parcial": caixas_parcial,
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
