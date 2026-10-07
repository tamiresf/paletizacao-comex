from datetime import datetime
from fractions import Fraction
import itertools
import os
import textwrap
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
COLUNAS_ESSENCIAIS = [
    "NUMERO DA CAIXA",
    "QUANTIDADE DE PEÇAS",
    "QUANTIDADE DE CAIXAS NO PALLET",
    "QUANTIDADE DE CAIXAS POR FILEIRA",
    "ALTURA",
]


def _fileiras_efetivas(cx_fileira, altura, capacidade):
    """Fileiras que o SKU realmente comporta: a menor entre a ALTURA cadastrada e o
    que a capacidade (caixas/pallet) permite. Sempre fileiras completas."""
    cx_fileira = max(int(cx_fileira), 1)
    return max(min(int(altura), max(int(capacidade) // cx_fileira, 1)), 1)


def _cpf_padrao_por_tipo(df, coluna_tipo="Ordem_Caixa"):
    """Caixas por fileira PADRÃO de cada tipo de caixa (o valor mais comum na
    planilha: tipo 0 = 25, 1 = 20, 2 = 16, 3 = 12). A fileira segue sempre o tipo."""
    return {
        int(t): int(g["QUANTIDADE DE CAIXAS POR FILEIRA"].mode().iloc[0])
        for t, g in df.groupby(coluna_tipo)
    }


@st.cache_data
def carregar_base(caminho_excel, versao=None):
    df = pd.read_excel(caminho_excel, sheet_name=0)  # sempre a PRIMEIRA aba
    df.columns = df.columns.str.strip()

    # linhas sem dados de paletização são ignoradas em silêncio (sem aviso):
    # antes viravam "1 caixa por pallet" e distorciam o cálculo
    df = df.dropna(subset=COLUNAS_ESSENCIAIS).copy()

    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["NOME DO PRODUTO"] = df["NOME DO PRODUTO"].astype(str).str.strip()

    # número da caixa vem como 1.0 no Excel -> "1"
    num_caixa = pd.to_numeric(df["NUMERO DA CAIXA"], errors="coerce")
    df["NUMERO DA CAIXA"] = [
        str(int(n)) if pd.notna(n) else str(orig).strip()
        for n, orig in zip(num_caixa, df["NUMERO DA CAIXA"])
    ]

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

    return df.reset_index(drop=True)


@st.cache_data
def diagnosticar_base(caminho_excel, versao=None):
    """SKUs cuja capacidade não bate com caixas/fileira x altura, só do que está na
    planilha AGORA. Linhas sem dados são ignoradas sem aviso. 'versao' (data de
    gravação do arquivo) entra na chave do cache: ao salvar a planilha de novo, o
    diagnóstico é refeito sozinho."""
    planilha = pd.ExcelFile(caminho_excel)
    aba = planilha.sheet_names[0]
    bruto = pd.read_excel(planilha, sheet_name=aba)
    bruto.columns = bruto.columns.str.strip()
    bruto = bruto[bruto["SKU"].notna()].dropna(subset=COLUNAS_ESSENCIAIS).copy()
    bruto["_tipo"] = pd.to_numeric(bruto["NUMERO DA CAIXA"], errors="coerce")
    padrao = _cpf_padrao_por_tipo(bruto.dropna(subset=["_tipo"]), "_tipo")

    inconsistentes = []
    for _, r in bruto.iterrows():
        cpf, alt = int(r["QUANTIDADE DE CAIXAS POR FILEIRA"]), int(r["ALTURA"])
        cap = int(r["QUANTIDADE DE CAIXAS NO PALLET"])
        tipo = None if pd.isna(r["_tipo"]) else int(r["_tipo"])
        cpf_pad = padrao.get(tipo, cpf)
        if cpf != cpf_pad or cap != cpf * alt:
            usa = _fileiras_efetivas(cpf_pad, alt, cap)
            inconsistentes.append({
                "sku": str(r["SKU"]).strip(),
                "produto": str(r["NOME DO PRODUTO"]).strip(),
                "tipo": tipo, "cap": cap, "cpf": cpf, "cpf_pad": cpf_pad, "alt": alt,
                "usa_fil": usa, "usa_cx": usa * max(cpf_pad, 1),
                "motivo": "cpf" if cpf != cpf_pad else "cap",
            })
    return aba, inconsistentes


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

VERSAO_PLANILHA = os.path.getmtime(CAMINHO_EXCEL)

try:
    df_produtos = carregar_base(CAMINHO_EXCEL, VERSAO_PLANILHA)
except Exception as e:
    st.error(f"Erro ao carregar a base de dados ({CAMINHO_EXCEL}): {e}")
    st.stop()

_aba, _inconsistentes = diagnosticar_base(CAMINHO_EXCEL, VERSAO_PLANILHA)
st.caption(
    f"📄 Planilha lida: {CAMINHO_EXCEL} (aba '{_aba}') - salva em "
    f"{datetime.fromtimestamp(VERSAO_PLANILHA).strftime('%d/%m/%Y %H:%M')}"
)
if _inconsistentes:
    with st.expander(
        f"⚠️ Erro na planilha {CAMINHO_EXCEL}: {len(_inconsistentes)} SKU(s) com cadastro incorreto",
        expanded=True,
    ):
        for p in _inconsistentes:
            if p["motivo"] == "cpf":
                detalhe = (
                    f"caixa tipo {p['tipo']} usa {p['cpf_pad']} cx/fileira, mas a planilha "
                    f"traz {p['cpf']} cx/fileira (capacidade {p['cap']} cx, altura {p['alt']})"
                )
            else:
                detalhe = (
                    f"capacidade cadastrada {p['cap']} cx, mas {p['cpf']} cx/fileira × "
                    f"altura {p['alt']} = {p['cpf'] * p['alt']} cx"
                )
            st.markdown(
                f"- **Erro na planilha - SKU {p['sku']}** ({p['produto']}): {detalhe}. "
                f"O sistema está usando {p['usa_fil']} fileiras ({p['usa_cx']} cx) por pallet."
            )
        st.caption(
            "Corrija a linha na planilha e salve: o aviso atualiza sozinho na próxima "
            "interação (se o app rodar na nuvem, é preciso publicar a planilha nova)."
        )

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

_cpf_sel = _cpf_padrao_por_tipo(df_produtos).get(
    int(prod_info["Ordem_Caixa"]), int(prod_info["QUANTIDADE DE CAIXAS POR FILEIRA"])
)
if (
    int(prod_info["QUANTIDADE DE CAIXAS POR FILEIRA"]) != _cpf_sel
    or int(prod_info["QUANTIDADE DE CAIXAS NO PALLET"]) != _cpf_sel * int(prod_info["ALTURA"])
):
    _usa = _fileiras_efetivas(
        _cpf_sel, prod_info["ALTURA"], prod_info["QUANTIDADE DE CAIXAS NO PALLET"]
    )
    st.sidebar.warning(
        "Erro na planilha neste SKU: caixas/fileira ou capacidade não batem com o tipo "
        f"de caixa e a altura. O sistema usa {_usa} fileiras ({_usa * _cpf_sel} cx) por pallet."
    )

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


# --- 6. ALGORITMO COMEX - PALLETS SEQUENCIAIS, TIPO DE CAIXA E ALTURA ---
# Limite geral das fileiras; quem manda é a ALTURA de cada SKU na planilha (normal = 5;
# a linha LANCERO é cadastrada com 6). O pallet respeita sempre o SKU mais baixo.
ALTURA_MAXIMA_FILEIRAS = 6

TIPO_SEQUENCIAL = "Pallet Fechado - SKU unico, sequencial 🟢"
TIPO_MESMA_ALTURA = "Pallet Fechado - mesma caixa e mesma altura 🟢"
TIPO_ALTURAS_DIFERENTES = "Pallet Fechado - mesma caixa, alturas diferentes 🟡"
TIPO_FINAL = "Pallet Final (caixas soltas e sobras) 🟠"


def _achar_combinacao_exata(unidades, alvo):
    """Procura combinação de blocos inteiros (SKU, fileiras) cuja soma de
    fileiras seja exatamente 'alvo'. Prefere blocos maiores (menos SKUs no pallet)."""
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


def _particoes(itens):
    """Todas as formas de dividir uma lista pequena em grupos."""
    if not itens:
        yield []
        return
    primeiro, resto = itens[0], itens[1:]
    for p in _particoes(resto):
        yield [[primeiro]] + p
        for i in range(len(p)):
            yield p[:i] + [[primeiro] + p[i]] + p[i + 1:]


def _gerar_pallets(carrinho, df_produtos, ordem_residuos="desc"):
    # --- Preparação dos SKUs do pedido ---
    skus = {}
    padrao_tipo = _cpf_padrao_por_tipo(df_produtos)
    for item in carrinho:
        sku = str(item["SKU"]).strip()
        prod = df_produtos[df_produtos["SKU"] == sku].iloc[0]
        cx_fileira = max(
            padrao_tipo.get(
                int(prod.get("Ordem_Caixa", 0)), int(prod["QUANTIDADE DE CAIXAS POR FILEIRA"])
            ),
            1,
        )
        altura = min(
            _fileiras_efetivas(
                cx_fileira, prod["ALTURA"], prod["QUANTIDADE DE CAIXAS NO PALLET"]
            ),
            ALTURA_MAXIMA_FILEIRAS,
        )
        skus[sku] = {
            "SKU": sku,
            "Produto": prod["NOME DO PRODUTO"],
            "Nº Caixa": str(prod["NUMERO DA CAIXA"]).strip(),
            "Ordem_Caixa": int(prod.get("Ordem_Caixa", 0)),
            "Pecas_Por_Caixa": int(prod["QUANTIDADE DE PEÇAS"]),
            "Caixas_Por_Fileira": cx_fileira,
            "Altura": altura,
            "Capacidade_Max": cx_fileira * altura,  # sempre fileiras completas
            "Restante": int(item["Qtd_Caixas"]),
        }

    # Cada pallet: {"tipo": str, "itens": {sku: caixas}}
    pallets = []

    def novo_pallet(tipo, itens):
        pallets.append({"tipo": tipo, "itens": dict(itens)})

    def cx_fileira_do_tipo(ordem):
        return max(s["Caixas_Por_Fileira"] for s in skus.values() if s["Ordem_Caixa"] == ordem)

    def fileiras_do_lote(itens):
        """Fileiras ocupadas: caixas do mesmo tipo dividem fileiras entre si."""
        por_tipo = {}
        for sku, qtd in itens.items():
            por_tipo[skus[sku]["Ordem_Caixa"]] = por_tipo.get(skus[sku]["Ordem_Caixa"], 0) + qtd
        return sum(-(-qtd // cx_fileira_do_tipo(t)) for t, qtd in por_tipo.items())

    def so_fileiras_completas(itens):
        por_tipo = {}
        for sku, qtd in itens.items():
            por_tipo[skus[sku]["Ordem_Caixa"]] = por_tipo.get(skus[sku]["Ordem_Caixa"], 0) + qtd
        return all(qtd % cx_fileira_do_tipo(t) == 0 for t, qtd in por_tipo.items())

    def limite_fileiras(itens):
        return min([ALTURA_MAXIMA_FILEIRAS] + [skus[sku]["Altura"] for sku in itens])

    ordem_skus = sorted(skus.values(), key=lambda s: (-s["Ordem_Caixa"], s["SKU"]))

    # ETAPA 1: pallets completos de um único SKU, SEQUENCIAIS (Pallet 01, 02, ...)
    for s in ordem_skus:
        while s["Restante"] >= s["Capacidade_Max"]:
            novo_pallet(TIPO_SEQUENCIAL, {s["SKU"]: s["Capacidade_Max"]})
            s["Restante"] -= s["Capacidade_Max"]

    # ETAPA 2: pallets mistos, SEMPRE separados por tipo de caixa.
    # Só entram fileiras completas; blocos de um SKU não são divididos.
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

        # 2.1: MESMA ALTURA dentro do mesmo tipo de caixa
        for altura in sorted({s["Altura"] for s in skus_tipo}, reverse=True):
            while True:
                escolha = _achar_combinacao_exata(
                    unidades(lambda s, a=altura: s["Altura"] == a), altura
                )
                if not escolha:
                    break
                fechar(escolha, TIPO_MESMA_ALTURA)

        # 2.2: esgotada a mesma altura, mistura ALTURAS DIFERENTES (mesmo tipo de caixa)
        achou = True
        while achou:
            achou = False
            for alvo in sorted({s["Altura"] for s in skus_tipo}, reverse=True):
                elegiveis = unidades(lambda s, a=alvo: s["Altura"] >= a)
                # precisa de ao menos um SKU com a altura-limite do pallet
                for sku_base, fil_base in [u for u in elegiveis if skus[u[0]]["Altura"] == alvo]:
                    outros = [u for u in elegiveis if u[0] != sku_base]
                    resto = _achar_combinacao_exata(outros, alvo - fil_base) if fil_base < alvo else []
                    if resto is not None:
                        fechar([(sku_base, fil_base)] + resto, TIPO_ALTURAS_DIFERENTES)
                        achou = True
                        break
                if achou:
                    break

    # ETAPA 3: sobras. Regra: fechar a fileira do tipo de caixa antes de entrar
    # outro tipo. Só as caixas que NÃO completam fileira vão para o último pallet.
    def montar_fileiras(tipo):
        """Transforma as sobras de um tipo de caixa em fileiras completas + caixas soltas.
        1) fileiras PURAS (um SKU só) - mantêm a altura do próprio SKU e são as mais
           rápidas de montar;
        2) só os restos (< 1 fileira) de cada SKU são combinados entre si, primeiro
           dentro da mesma altura e depois misturando alturas (mesmo tipo de caixa)."""
        cpf = cx_fileira_do_tipo(tipo)
        sobras = [s for s in ordem_skus if s["Ordem_Caixa"] == tipo and s["Restante"] > 0]
        fileiras, restos = [], []

        for s in sobras:
            for _ in range(s["Restante"] // cpf):
                fileiras.append({"tipo": tipo, "altura": s["Altura"], "itens": {s["SKU"]: cpf}})
            if s["Restante"] % cpf:
                restos.append((s["SKU"], s["Restante"] % cpf))
            s["Restante"] = 0

        def consumir(fila):
            atual, cheia = {}, 0
            for sku, qtd in fila:
                while qtd > 0:
                    pega = min(cpf - cheia, qtd)
                    atual[sku] = atual.get(sku, 0) + pega
                    cheia += pega
                    qtd -= pega
                    if cheia == cpf:
                        alt = min(skus[k]["Altura"] for k in atual)
                        fileiras.append({"tipo": tipo, "altura": alt, "itens": atual})
                        atual, cheia = {}, 0
            return atual

        sobra_de_altura = []
        for altura in sorted({skus[k]["Altura"] for k, _ in restos}, reverse=True):
            grupo = sorted(
                [r for r in restos if skus[r[0]]["Altura"] == altura],
                key=lambda r: (-r[1], r[0]),
            )
            sobra_de_altura.extend(consumir(grupo).items())
        # mistura alturas só com o que sobrou. 'desc': as caixas soltas ficam com as
        # alturas MENORES; 'asc': ficam com as MAIORES (limitam menos o pallet final)
        if ordem_residuos == "asc":
            sobra_de_altura.sort(key=lambda kv: (skus[kv[0]]["Altura"], -kv[1], kv[0]))
        else:
            sobra_de_altura.sort(key=lambda kv: (-skus[kv[0]]["Altura"], -kv[1], kv[0]))
        soltas = consumir(sobra_de_altura)
        return fileiras, soltas

    fileiras_todas, soltas_por_tipo = [], []
    for tipo in tipos:
        f, soltas = montar_fileiras(tipo)
        fileiras_todas.append((tipo, f))
        if soltas:
            soltas_por_tipo.append({
                "tipo": tipo,
                "altura": min(skus[k]["Altura"] for k in soltas),
                "itens": soltas,
                "solta": True,
            })

    # tipos com mais fileiras primeiro (empate: menor número de caixa)
    fileiras_todas.sort(key=lambda tf: (-len(tf[1]), tf[0]))

    def juntar(lista_fileiras):
        itens = {}
        for f in lista_fileiras:
            for sku, qtd in f["itens"].items():
                itens[sku] = itens.get(sku, 0) + qtd
        return itens

    def ocupacao(itens):
        """Fração da capacidade do pallet ocupada (1 = lotado). Cada SKU consome
        qtd / Capacidade_Max; para um SKU único é exatamente o limite de caixas."""
        return sum(
            Fraction(qtd, skus[sku]["Capacidade_Max"]) for sku, qtd in itens.items()
        )

    def cabe(lista_fileiras, nova):
        """A fileira 'nova' cabe no pallet? Respeita (1) altura máxima de 5 e a
        altura do SKU mais baixo e (2) a quantidade máxima de caixas do pallet."""
        if not lista_fileiras:
            return True
        alt = min([ALTURA_MAXIMA_FILEIRAS] + [f["altura"] for f in lista_fileiras + [nova]])
        if len(lista_fileiras) + 1 > alt:
            return False
        return ocupacao(juntar(lista_fileiras + [nova])) <= 1

    def limite_fileiras_lista(lista_fileiras):
        return min([ALTURA_MAXIMA_FILEIRAS] + [f["altura"] for f in lista_fileiras])

    TIPO_FILEIRAS_SOBRAS = "Pallet Fechado - fileiras completas de sobras 🟢"

    # ETAPA 4: empacotamento das fileiras de sobras em pallets.
    # Cada fileira tem uma altura (a do SKU mais baixo nela) e cada pallet comporta,
    # no máximo, tantas fileiras quanto a menor altura que ele contém. Processando
    # da MENOR altura para a MAIOR, os pallets baixos são completados com fileiras
    # mais altas (que cabem em qualquer pallet baixo) e nunca sobra pallet pela
    # metade sem necessidade - ou seja, o menor número possível de pallets.
    #  - as caixas soltas (fileiras quebradas) ficam TODAS juntas no último pallet,
    #    só se dividindo em mais de um quando altura/capacidade não permitirem;
    #  - dentro da mesma altura, prefere-se o mesmo tipo de caixa no mesmo pallet.
    rows_completas = [f for _, fl in fileiras_todas for f in fl]

    def particoes_viaveis(soltas):
        """Formas de dividir as caixas soltas em pallets (cada grupo precisa caber)."""
        viaveis = [
            part for part in _particoes(soltas)
            if all(
                len(g) <= limite_fileiras_lista(g) and ocupacao(juntar(g)) <= 1 for g in part
            )
        ]
        return viaveis or [[[x] for x in soltas]]

    def n_completas(lista_fileiras):
        return sum(1 for f in lista_fileiras if not f.get("solta"))

    def empacotar(rows, grupos_soltos, lims, desig):
        pals = [
            {"lim": lim, "rows": list(g), "solta": True}
            for g, lim in zip(grupos_soltos, lims)
        ]
        por_altura = {}
        for f in rows:
            por_altura.setdefault(min(f["altura"], ALTURA_MAXIMA_FILEIRAS), []).append(f)
        for h in sorted(por_altura):
            for f in por_altura[h]:
                cands = [
                    p for p in pals
                    if p["lim"] <= h and len(p["rows"]) < p["lim"]
                    # (a capacidade em caixas fica garantida pelo limite de fileiras:
                    #  cada SKU comporta exatamente 'caixas/fileira x altura')
                ]
                if cands:
                    p = min(cands, key=lambda p: (
                        # o pallet que será o ÚLTIMO recebe primeiro até ter 2 fileiras completas
                        0 if (desig is not None and p is pals[desig]
                              and n_completas(p["rows"]) < 2) else 1,
                        0 if f["tipo"] in {x["tipo"] for x in p["rows"]} else 1,
                        -len(p["rows"]),
                    ))
                else:
                    p = {"lim": h, "rows": [], "solta": False}
                    pals.append(p)
                p["rows"].append(f)
        return pals

    melhor_emp = None
    for grupos_soltos in particoes_viaveis(soltas_por_tipo):
        faixas = [range(len(g), limite_fileiras_lista(g) + 1) for g in grupos_soltos]
        desigs = list(range(len(grupos_soltos))) or [None]
        for lims in itertools.product(*faixas):
            for desig in desigs:
                pals = empacotar(rows_completas, grupos_soltos, lims, desig)
                viol = 0
                if desig is not None and n_completas(pals[desig]["rows"]) < 2:
                    viol = 1
                chave = (viol, len(pals), len(grupos_soltos), -sum(lims))
                if melhor_emp is None or chave < melhor_emp[0]:
                    melhor_emp = (chave, pals)
    pals_sobras = melhor_emp[1] if melhor_emp else []

    fechados_sobras = [
        p["rows"] for p in pals_sobras
        if not p["solta"] and len(p["rows"]) >= limite_fileiras_lista(p["rows"])
    ]
    restantes = [
        p for p in pals_sobras
        if p["solta"] or len(p["rows"]) < limite_fileiras_lista(p["rows"])
    ]
    # o pallet com caixas soltas é sempre o ÚLTIMO (o que tiver mais fileiras completas);
    # os demais, do mais cheio ao mais vazio
    restantes.sort(key=lambda p: (
        p["solta"],
        n_completas(p["rows"]) if p["solta"] else -len(p["rows"]),
    ))
    blocos = [p["rows"] for p in restantes]

    # Reajuste do ÚLTIMO pallet: ele deve ter, no mínimo, 2 fileiras COMPLETAS.
    # Se faltar, extrai fileiras completas dos pallets mais recentes (de trás
    # para frente): pallets finais -> pallets de sobras -> pallets mistos ->
    # pallets sequenciais. Regras:
    #   - só sai fileira COMPLETA (o doador nunca fica com fileira quebrada);
    #   - o doador nunca fica com menos de 2 fileiras completas;
    #   - o pallet que recebe respeita SEMPRE a altura máxima (5 fileiras / altura
    #     do SKU mais baixo) e a quantidade máxima de caixas (função cabe()).
    TIPO_REAJUSTADO = "Pallet Fechado - fileiras completas (reajustado) 🟢"
    TIPO_SEQ_OU_MISTO = {TIPO_SEQUENCIAL: 2, TIPO_MESMA_ALTURA: 1, TIPO_ALTURAS_DIFERENTES: 1}

    def completas(lista_fileiras):
        return sum(1 for f in lista_fileiras if not f.get("solta"))

    n_pal, n_fech = len(pallets), len(fechados_sobras)

    for bloco in reversed(blocos):
        while completas(bloco) < 2:
            tipos_bloco = {f["tipo"] for f in bloco}
            alt_bloco = min([ALTURA_MAXIMA_FILEIRAS] + [f["altura"] for f in bloco])
            candidatos = []

            # a) doadores em lista de fileiras: pallets de sobras e demais pallets
            #    finais (posição na numeração final = n_pal + índice)
            listas = [(n_pal + i, d) for i, d in enumerate(fechados_sobras)]
            listas += [(n_pal + n_fech + i, d) for i, d in enumerate(blocos) if d is not bloco]
            for pos, doador in listas:
                if completas(doador) <= 2:
                    continue
                for f in doador:
                    if f.get("solta") or not cabe(bloco, f):
                        continue
                    prioridade = (
                        -pos,                                    # mais recente primeiro
                        0 if f["tipo"] in tipos_bloco else 1,    # mesmo tipo de caixa
                        0 if f["altura"] == alt_bloco else 1,    # mesma altura
                    )
                    candidatos.append((prioridade, "lista", doador, f))

            # b) doadores já formados nas etapas 1 e 2 (pallets mistos/sequenciais)
            for idx_p, pal in enumerate(pallets):
                if pal["tipo"] not in TIPO_SEQ_OU_MISTO and pal["tipo"] != TIPO_REAJUSTADO:
                    continue
                if fileiras_do_lote(pal["itens"]) <= 2:
                    continue
                for sku, qtd in pal["itens"].items():
                    s = skus[sku]
                    if qtd < s["Caixas_Por_Fileira"]:
                        continue
                    f = {"tipo": s["Ordem_Caixa"], "altura": s["Altura"],
                         "itens": {sku: s["Caixas_Por_Fileira"]}}
                    if not cabe(bloco, f):
                        continue
                    prioridade = (
                        -idx_p,
                        0 if s["Ordem_Caixa"] in tipos_bloco else 1,
                        0 if s["Altura"] == alt_bloco else 1,
                    )
                    candidatos.append((prioridade, "pallet", (pal, sku), f))

            if not candidatos:
                break  # nenhum pallet consegue doar uma fileira completa que caiba
            _, origem, doador, f = min(candidatos, key=lambda c: c[0])
            if origem == "lista":
                doador.remove(f)
            else:
                pal, sku = doador
                pal["itens"][sku] -= f["itens"][sku]
                if pal["itens"][sku] == 0:
                    del pal["itens"][sku]
                pal["tipo"] = TIPO_REAJUSTADO
            bloco.append(f)

    for fileiras_pallet_sobras in fechados_sobras:
        novo_pallet(TIPO_FILEIRAS_SOBRAS, juntar(fileiras_pallet_sobras))
    for bloco in blocos:
        novo_pallet(TIPO_FINAL, juntar(bloco))

    # --- Estrutura final para exibição e relatórios ---
    linhas = []
    for idx, p in enumerate(pallets, 1):
        itens_ord = sorted(
            p["itens"].items(), key=lambda kv: (-skus[kv[0]]["Ordem_Caixa"], kv[0])
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
                "Cx_Fileira_Tipo": cx_fileira_do_tipo(s["Ordem_Caixa"]),
                "Cap_Pallet_Caixas": s["Capacidade_Max"],
            })
    return pd.DataFrame(linhas)


def _pontuar(df):
    """Menor é melhor: (último pallet sem 2 fileiras completas, nº de pallets,
    pallets com caixa solta, linhas de separação)."""
    cpf_tipo = df.groupby("Ordem_Caixa")["Caixas_Por_Fileira"].max().to_dict()
    ultimo = df["Pallet_Num"].max()
    com_solta = 0
    completas_ultimo = 0
    for pn, g in df.groupby("Pallet_Num"):
        por_tipo = g.groupby("Ordem_Caixa")["Qtd Caixas"].sum()
        if any(q % cpf_tipo[t] for t, q in por_tipo.items()):
            com_solta += 1
        if pn == ultimo:
            completas_ultimo = sum(int(q // cpf_tipo[t]) for t, q in por_tipo.items())
    return (
        1 if completas_ultimo < 2 else 0,
        int(ultimo),
        com_solta,
        len(df),
    )


def processar_pallets_operador(carrinho, df_produtos):
    """Roda as variantes do algoritmo e devolve a melhor montagem."""
    melhor = None
    for variante in ("desc", "asc"):
        df = _gerar_pallets(carrinho, df_produtos, variante)
        pont = _pontuar(df)
        if melhor is None or pont < melhor[0]:
            melhor = (pont, df)
    return melhor[1]


# --- 6.1 FUNÇÕES DE APOIO: CONFERÊNCIA, MONTAGEM FILEIRA A FILEIRA E SEPARAÇÃO ---
def _tipo_limpo(tipo):
    for emoji in ("🟢", "🟡", "🟠"):
        tipo = tipo.replace(emoji, "")
    return tipo.strip()


def _faixas(numeros):
    """[1, 2, 3, 5] -> '1 a 3, 5'."""
    numeros = sorted(numeros)
    partes, ini, ant = [], None, None
    for n in numeros:
        if ini is None:
            ini = ant = n
        elif n == ant + 1:
            ant = n
        else:
            partes.append((ini, ant))
            ini = ant = n
    if ini is not None:
        partes.append((ini, ant))
    return ", ".join(str(a) if a == b else f"{a} a {b}" for a, b in partes)


def montar_camadas(df_p):
    """Quebra um pallet em fileiras, da BASE para o TOPO.
    Fileiras completas primeiro (tipo de caixa de maior número na base; dentro do
    tipo, fileiras puras de um SKU antes das mistas); fileiras incompletas por
    último, no topo, onde não deixam 'buraco' por baixo."""
    completas_, parciais = [], []
    for tipo in sorted(df_p["Ordem_Caixa"].unique(), reverse=True):
        d = df_p[df_p["Ordem_Caixa"] == tipo]
        cpf = int(d["Cx_Fileira_Tipo"].iloc[0])
        restos = []
        for _, r in d.iterrows():
            sku, prod, qtd = r["SKU"], r["Produto"], int(r["Qtd Caixas"])
            for _ in range(qtd // cpf):
                completas_.append(
                    {"tipo": tipo, "cpf": cpf, "itens": [(sku, prod, cpf)], "completa": True}
                )
            if qtd % cpf:
                restos.append((sku, prod, qtd % cpf))
        restos.sort(key=lambda x: (-x[2], x[0]))
        atual, cheia = [], 0
        for sku, prod, q in restos:
            while q > 0:
                pega = min(cpf - cheia, q)
                atual.append((sku, prod, pega))
                cheia += pega
                q -= pega
                if cheia == cpf:
                    completas_.append(
                        {"tipo": tipo, "cpf": cpf, "itens": atual, "completa": True}
                    )
                    atual, cheia = [], 0
        if atual:
            parciais.append({"tipo": tipo, "cpf": cpf, "itens": atual, "completa": False})
    camadas = completas_ + parciais
    for i, c in enumerate(camadas, 1):
        c["n"] = i
    return camadas


def posicao_por_sku(camadas):
    """Onde cada SKU fica no pallet: '1 a 3' (fileiras inteiras) e, se for o caso,
    '4 (12 cx, mista)' ou '5 (3 cx, incompleta)'."""
    pos = {}
    for c in camadas:
        for sku, _, q in c["itens"]:
            d = pos.setdefault(sku, {"inteiras": [], "outras": []})
            if c["completa"] and len(c["itens"]) == 1:
                d["inteiras"].append(c["n"])
            else:
                motivo = "mista" if c["completa"] else "incompleta"
                d["outras"].append(f"{c['n']} ({q} cx, {motivo})")
    textos = {}
    for sku, d in pos.items():
        partes = []
        if d["inteiras"]:
            partes.append(_faixas(d["inteiras"]))
        partes.extend(d["outras"])
        textos[sku] = "; ".join(partes)
    return textos


def tabela_camadas(camadas):
    """Tabela de montagem: fileiras idênticas e seguidas viram uma linha só."""
    linhas, i = [], 0
    while i < len(camadas):
        c = camadas[i]
        j = i
        while (
            j + 1 < len(camadas)
            and camadas[j + 1]["itens"] == c["itens"]
            and camadas[j + 1]["completa"] == c["completa"]
        ):
            j += 1
        n_rep = j - i + 1
        rotulo = str(c["n"]) if n_rep == 1 else f"{c['n']} a {camadas[j]['n']}"
        if not c["completa"]:
            rotulo += " (incompleta - topo)"
        elif len(c["itens"]) > 1:
            rotulo += " (mista)"
        for sku, prod, q in c["itens"]:
            total = q * n_rep
            linhas.append({
                "Fileira (base→topo)": rotulo,
                "Nº Caixa": str(c["tipo"]),
                "SKU": sku,
                "Produto": prod,
                "Caixas": f"{q} por fileira × {n_rep} = {total} cx" if n_rep > 1 else f"{q} cx",
            })
        i = j + 1
    return pd.DataFrame(linhas)


def lista_separacao(df):
    """Lista consolidada para quem separa: cada SKU uma vez, com o total a
    separar e para quais pallets as caixas vão."""
    linhas = []
    for sku, g in df.groupby("SKU", sort=False):
        g = g.sort_values("Pallet_Num")
        partes, i, nums, qtds = [], 0, list(g["Pallet_Num"]), [int(q) for q in g["Qtd Caixas"]]
        while i < len(nums):
            j = i
            while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1 and qtds[j + 1] == qtds[i]:
                j += 1
            if j == i:
                partes.append(f"Pallet {nums[i]:02d} ({qtds[i]} cx)")
            else:
                partes.append(f"Pallets {nums[i]:02d} a {nums[j]:02d} ({qtds[i]} cx cada)")
            i = j + 1
        linhas.append({
            "SKU": sku,
            "Produto": g["Produto"].iloc[0],
            "Nº Caixa": g["Nº Caixa"].iloc[0],
            "Total Caixas": int(g["Qtd Caixas"].sum()),
            "Total Peças": int(g["Total Peças"].sum()),
            "Vai para": " | ".join(partes),
            "_ordem": int(g["Ordem_Caixa"].iloc[0]),
        })
    out = pd.DataFrame(linhas)
    out = out.sort_values(["_ordem", "SKU"], ascending=[False, True]).drop(columns="_ordem")
    return out.reset_index(drop=True)


def agrupar_pallets_identicos(df, agrupar=True):
    """Pallets seguidos e idênticos (mesmos SKUs e quantidades) viram um grupo só:
    'Pallets 01 a 03'. O operador monta o primeiro e repete."""
    grupos = []
    for pn in sorted(df["Pallet_Num"].unique()):
        g = df[df["Pallet_Num"] == pn]
        assinatura = (
            g["Tipo"].iloc[0],
            tuple(sorted(zip(g["SKU"], [int(q) for q in g["Qtd Caixas"]]))),
        )
        if agrupar and grupos and grupos[-1]["assinatura"] == assinatura:
            grupos[-1]["nums"].append(int(pn))
        else:
            grupos.append({"assinatura": assinatura, "nums": [int(pn)], "df": g})
    for gr in grupos:
        a, b = gr["nums"][0], gr["nums"][-1]
        gr["n"] = len(gr["nums"])
        gr["rotulo"] = f"Pallet {a:02d}" if gr["n"] == 1 else f"Pallets {a:02d} a {b:02d}"
    return grupos


def validar_pallets(df, carrinho):
    """Conferência automática do resultado. 'erros' = regra física/quantidade
    violada; 'avisos' = regra de preferência que não foi possível cumprir."""
    erros, avisos = [], []
    pedido = {str(c["SKU"]).strip(): int(c["Qtd_Caixas"]) for c in carrinho}
    gerado = df.groupby("SKU")["Qtd Caixas"].sum().astype(int).to_dict()
    for sku in sorted(set(pedido) | set(gerado)):
        if pedido.get(sku, 0) != gerado.get(sku, 0):
            erros.append(
                f"SKU {sku}: pedido {pedido.get(sku, 0)} cx, distribuído {gerado.get(sku, 0)} cx."
            )
    ultimo = int(df["Pallet_Num"].max())
    for pn, g in df.groupby("Pallet_Num"):
        limite = min([ALTURA_MAXIMA_FILEIRAS] + [int(x) for x in g["Quantidade_Fileiras"]])
        if int(g["Fileiras no Pallet"].iloc[0]) > limite:
            erros.append(f"Pallet {pn:02d}: {int(g['Fileiras no Pallet'].iloc[0])} fileiras, limite {limite}.")
        ocup = sum(
            Fraction(int(q), int(c)) for q, c in zip(g["Qtd Caixas"], g["Cap_Pallet_Caixas"])
        )
        if ocup > 1:
            erros.append(f"Pallet {pn:02d}: acima da capacidade de caixas.")
        por_tipo = g.groupby("Ordem_Caixa").agg(q=("Qtd Caixas", "sum"), c=("Cx_Fileira_Tipo", "first"))
        soltas = any(int(r["q"]) % int(r["c"]) for _, r in por_tipo.iterrows())
        if soltas and pn != ultimo:
            avisos.append(
                f"Pallet {pn:02d} tem fileira incompleta (caixas soltas): não foi possível "
                "juntar todas as soltas no último pallet respeitando altura e capacidade."
            )
        if pn == ultimo:
            n_completas = sum(int(r["q"]) // int(r["c"]) for _, r in por_tipo.iterrows())
            if n_completas < 2:
                avisos.append(
                    f"O último pallet (Pallet {pn:02d}) ficou com {n_completas} fileira(s) "
                    "completa(s): não foi possível chegar a 2 respeitando altura e capacidade."
                )
    return erros, avisos


# --- 7. GERADOR DE PDF (COMPACTO: lista de separação + pallets idênticos agrupados) ---
def _latin(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")


def gerar_pdf(df_pallets, cliente, data_str, agrupar=True):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "MUSTAD - Relatório de Paletização", align="C")
    pdf.ln(7)

    nome_cliente_formatado = cliente.strip() if cliente else "Não Informado"
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Cliente: {_latin(nome_cliente_formatado)}", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Data de Emissão: {data_str}", align="C")
    pdf.ln(5)
    n_pallets = int(df_pallets["Pallet_Num"].nunique())
    total_cx = int(df_pallets["Qtd Caixas"].sum())
    total_pc = int(df_pallets["Total Peças"].sum())
    pdf.cell(0, 5, f"{n_pallets} pallets | {total_pc} peças", align="C")
    pdf.ln(8)

    # Caixa de destaque: TOTAL DE CAIXAS
    pdf.set_fill_color(30, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 14, f"TOTAL DE CAIXAS: {total_cx}", align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(18)

    # ---- Pallets (idênticos agrupados) ----
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Montagem dos Pallets", border="B")
    pdf.ln(10)

    for gr in agrupar_pallets_identicos(df_pallets, agrupar):
        df_p = gr["df"]
        tipo_limpo = _latin(_tipo_limpo(str(df_p["Tipo"].iloc[0])))
        cx_pallet = int(df_p["Qtd Caixas"].sum())
        pc_pallet = int(df_p["Total Peças"].sum())
        altura_bloco = 20 + (len(df_p) + 1) * 6
        if pdf.get_y() + altura_bloco > 275:
            pdf.add_page()

        titulo = f"{gr['rotulo']} | Tipo: {tipo_limpo}"
        if gr["n"] > 1:
            titulo += f" | {gr['n']} pallets idênticos"
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, titulo, border="B")
        pdf.ln(8)
        pdf.set_font("Helvetica", "B", 12)
        destaque = f"TOTAL: {cx_pallet} caixas"
        if gr["n"] > 1:
            destaque = f"CADA PALLET: {cx_pallet} caixas   |   GRUPO: {cx_pallet * gr['n']} caixas"
        pdf.cell(0, 7, destaque)
        pdf.ln(8)

        larg = [24, 62, 18, 22, 24, 20, 20]
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(235, 235, 235)
        for w, t in zip(larg, ["SKU", "Produto", "N. Caixa", "Qtd Cx", "Qtd Peças", "Cx/Fil.", "Fil."]):
            pdf.cell(w, 6, t, border=1, fill=True)
        pdf.ln()

        for _, row in df_p.iterrows():
            pdf.set_font("Helvetica", size=8)
            pdf.cell(larg[0], 6, str(row["SKU"]), border=1)
            pdf.cell(larg[1], 6, _latin(row["Produto"])[:34], border=1)
            pdf.cell(larg[2], 6, str(row["Nº Caixa"]), border=1)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(larg[3], 6, str(row["Qtd Caixas"]), border=1, align="C")
            pdf.set_font("Helvetica", size=8)
            pdf.cell(larg[4], 6, str(row["Total Peças"]), border=1)
            pdf.cell(larg[5], 6, str(row["Caixas_Por_Fileira"]), border=1)
            pdf.cell(larg[6], 6, str(row["Quantidade_Fileiras"]), border=1)
            pdf.ln()

        pdf.ln(5)

    return bytes(pdf.output())


# --- 8. EXECUÇÃO E RESULTADOS ---
@st.cache_data(show_spinner="Calculando a melhor montagem dos pallets...")
def calcular_pallets(itens, caminho_excel, versao, _df_produtos):
    """Cálculo em cache: mexer em checkbox/abas não recalcula tudo de novo."""
    carrinho = [{"SKU": sku, "Qtd_Caixas": qtd} for sku, qtd in itens]
    return processar_pallets_operador(carrinho, _df_produtos)


if st.button("⚙️ CALCULAR E GERAR PALLETS"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

if st.session_state.processado and st.session_state.carrinho:
    df_pallets = calcular_pallets(
        tuple((i["SKU"], int(i["Qtd_Caixas"])) for i in st.session_state.carrinho),
        CAMINHO_EXCEL,
        VERSAO_PLANILHA,
        df_produtos,
    )

    agrupar = st.checkbox(
        "Agrupar pallets idênticos (ex.: Pallets 01 a 03)",
        value=True,
        key="agrupar_identicos",
    )
    grupos = agrupar_pallets_identicos(df_pallets, agrupar)

    st.subheader("📦 Detalhamento Individual por Pallet")
    n_pallets = int(df_pallets["Pallet_Num"].nunique())
    st.success(f"**Total de Pallets Gerados:** {n_pallets}")

    # Conferência automática antes de liberar para o operador
    erros, avisos = validar_pallets(df_pallets, st.session_state.carrinho)
    if erros:
        st.error("⛔ Conferência automática encontrou divergências - não use este resultado:")
        for e in erros:
            st.write(f"- {e}")
    else:
        st.info(
            "✅ Conferência automática: todas as caixas do pedido foram distribuídas, "
            "sem excesso de altura ou de capacidade em nenhum pallet."
        )
    for a in avisos:
        st.warning(a)

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
                df_pallets, cliente_informado, data_formatada_pdf, agrupar
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

    # --- Lista de separação: para quem separa o pedido ---
    with st.expander("🧾 Lista de separação (cada SKU uma vez, com destino)", expanded=True):
        st.caption(
            "Separe o total de cada SKU de uma vez e distribua conforme a coluna "
            "'Vai para'."
        )
        st.dataframe(lista_separacao(df_pallets), use_container_width=True)

    # --- Pallets: para quem monta ---
    for gr in grupos:
        df_p = gr["df"]
        tipo_pallet = df_p["Tipo"].iloc[0]
        total_cx = int(df_p["Qtd Caixas"].sum())
        total_pc = int(df_p["Total Peças"].sum())
        n_fil = int(df_p["Fileiras no Pallet"].iloc[0])
        camadas = montar_camadas(df_p)
        posicoes = posicao_por_sku(camadas)

        titulo = f"📌 {gr['rotulo']} - Total de Caixas: {total_cx} cx | Total de Peças: {total_pc} peças | {n_fil} fileiras ({tipo_pallet})"
        if gr["n"] > 1:
            titulo = (
                f"📌 {gr['rotulo']} ({gr['n']} pallets idênticos) - cada um: {total_cx} cx | "
                f"{total_pc} peças | {n_fil} fileiras ({tipo_pallet})"
            )

        with st.expander(titulo, expanded=True):
            aba_comp, aba_mont = st.tabs(["Composição", "🧱 Montagem fileira a fileira"])

            with aba_comp:
                df_exibe = df_p.copy()
                df_exibe["Posição (base→topo)"] = df_exibe["SKU"].map(posicoes)
                st.dataframe(
                    df_exibe[[
                        "SKU",
                        "Produto",
                        "Nº Caixa",
                        "Qtd Caixas",
                        "Total Peças",
                        "Posição (base→topo)",
                        "Caixas_Por_Fileira",
                        "Quantidade_Fileiras",
                    ]],
                    use_container_width=True,
                )

            with aba_mont:
                st.caption(
                    "Fileiras numeradas da base (1) para o topo. A fileira incompleta, "
                    "quando existir, fica por último, no topo."
                )
                st.dataframe(tabela_camadas(camadas), use_container_width=True)

            texto_destaque = f"📦 Total de Caixas do Pallet: {total_cx} cx"
            if gr["n"] > 1:
                texto_destaque += f" (x{gr['n']} = {total_cx * gr['n']} cx)"
            str_destaque = f"""
                <div style="text-align: right;">
                    <span class="total-caixas-destaque">{texto_destaque}</span>
                </div>
                """
            st.markdown(str_destaque, unsafe_allow_html=True)
