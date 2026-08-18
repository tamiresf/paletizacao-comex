import json
import os
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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

            if abs(capacidade_usada - 1.0) < 1e-6:
                for it in itens_no_pallet_atual:
                    pallets_lista.append(it)
                pallet_id += 1
            else:
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


# --- 8. GERADOR DE MODELO 3D (THREE.JS COM AUTO-START) ---
def gerar_visualizacao_3d_threejs(df_pallet_especifico):
    df_ordenado = df_pallet_especifico.sort_values(
        by=["Ordem_Caixa", "SKU"], ascending=[False, True]
    )

    paleta_cores = [
        "#2563EB",
        "#059669",
        "#DC2626",
        "#7C3AED",
        "#D97706",
        "#4B5563",
    ]
    skus_unicos = list(df_pallet_especifico["SKU"].unique())
    cor_map = {
        sku: paleta_cores[i % len(paleta_cores)]
        for i, sku in enumerate(skus_unicos)
    }

    caixas_json = []
    z_atual = 0.0

    lista_caixas = []
    for _, row in df_ordenado.iterrows():
        sku = row["SKU"]
        qtd = int(row["Qtd Caixas"])
        cor = cor_map[sku]
        cx_nome = row["Nº Caixa"]
        dims = obter_dimensoes_caixa(cx_nome)

        for _ in range(qtd):
            lista_caixas.append(
                {"sku": sku, "cor": cor, "cx_nome": cx_nome, "dims": dims}
            )

    idx = 0
    total_caixas = len(lista_caixas)

    while idx < total_caixas:
        cx_ref = lista_caixas[idx]
        dims = cx_ref["dims"]
        dx, dy, cols_x, cols_y = obter_melhor_orientacao(
            dims["comp"], dims["larg"], PALLET_COMP, PALLET_LARG
        )
        dz = dims["alt"]
        caixas_por_camada = max(1, cols_x * cols_y)

        offset_x = (PALLET_COMP - (cols_x * dx)) / 2.0
        offset_y = (PALLET_LARG - (cols_y * dy)) / 2.0

        qtd_camada = min(total_caixas - idx, caixas_por_camada)

        for i in range(qtd_camada):
            item = lista_caixas[idx + i]
            cx_i = i % cols_x
            cy_i = i // cols_x

            x0 = offset_x + cx_i * dx + dx / 2.0
            y0 = offset_y + cy_i * dy + dy / 2.0
            z0 = z_atual + dz / 2.0

            caixas_json.append(
                {
                    "x": round(x0, 4),
                    "y": round(z0, 4),
                    "z": round(y0, 4),
                    "dx": round(dx * 0.98, 4),
                    "dy": round(dz * 0.98, 4),
                    "dz": round(dy * 0.98, 4),
                    "cor": item["cor"],
                    "sku": item["sku"],
                    "cx_nome": item["cx_nome"],
                }
            )

        idx += qtd_camada
        z_atual += dz

    data_json_str = json.dumps(caixas_json)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; overflow: hidden; background-color: #0e1117; font-family: sans-serif; }}
            #canvas-container {{ width: 100%; height: 480px; position: relative; }}
            #controls {{ position: absolute; top: 10px; left: 10px; z-index: 10; }}
            button {{
                background: #262730; color: #FAFAFA; border: 1px solid #4B4B4B;
                padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: 600;
                transition: all 0.2s ease; font-size: 13px;
            }}
            button:hover {{ background: #FF4B4B; border-color: #FF4B4B; }}
            #info {{ position: absolute; bottom: 8px; left: 10px; color: #A0A0A0; font-size: 11px; }}
        </style>
        <script src="https://unpkg.com/three@0.128.0/build/three.min.js"></script>
        <script src="https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
        <div id="canvas-container">
            <div id="controls">
                <button onclick="resetarCamera()">🎥 Resetar Câmera</button>
            </div>
            <div id="info">💡 Arraste com o mouse para girar | Scroll para zoom</div>
        </div>

        <script>
            let camera, scene, renderer, controls;
            let boxMeshes = [];
            let currentStep = 0;
            let animando = true;
            const caixasData = {data_json_str};

            function init() {{
                const container = document.getElementById('canvas-container');
                scene = new THREE.Scene();
                scene.background = new THREE.Color(0x0e1117);

                camera = new THREE.PerspectiveCamera(45, container.clientWidth / 480, 0.1, 100);
                camera.position.set(2.5, 2.0, 2.5);

                renderer = new THREE.WebGLRenderer({{ antialias: true }});
                renderer.setSize(container.clientWidth, 480);
                renderer.setPixelRatio(window.devicePixelRatio);
                renderer.shadowMap.enabled = true;
                renderer.shadowMap.type = THREE.PCFSoftShadowMap;
                container.appendChild(renderer.domElement);

                controls = new THREE.OrbitControls(camera, renderer.domElement);
                controls.enableDamping = true;
                controls.dampingFactor = 0.05;
                controls.target.set(0.6, 0.4, 0.375);

                const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
                scene.add(ambientLight);

                const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
                dirLight.position.set(3, 5, 2);
                dirLight.castShadow = true;
                scene.add(dirLight);

                const gridHelper = new THREE.GridHelper(5, 20, 0x444444, 0x222222);
                gridHelper.position.set(0.6, -0.06, 0.375);
                scene.add(gridHelper);

                // Pallet Base
                const palletGeo = new THREE.BoxGeometry(1.20, 0.05, 0.75);
                const palletMat = new THREE.MeshStandardMaterial({{ color: 0x8B5A2B, roughness: 0.8 }});
                const palletMesh = new THREE.Mesh(palletGeo, palletMat);
                palletMesh.position.set(0.6, -0.025, 0.375);
                palletMesh.receiveShadow = true;
                scene.add(palletMesh);

                // Criar caixas
                caixasData.forEach((item, index) => {{
                    const geo = new THREE.BoxGeometry(item.dx, item.dy, item.dz);
                    const mat = new THREE.MeshStandardMaterial({{
                        color: new THREE.Color(item.cor),
                        roughness: 0.4,
                        metalness: 0.1
                    }});
                    
                    const mesh = new THREE.Mesh(geo, mat);
                    mesh.castShadow = true;
                    mesh.receiveShadow = true;

                    const edges = new THREE.EdgesGeometry(geo);
                    const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({{ color: 0x000000, linewidth: 1 }}));
                    mesh.add(line);

                    mesh.userData = {{
                        targetY: item.y,
                        startY: item.y + 1.8,
                        index: index
                    }};

                    mesh.position.set(item.x, mesh.userData.startY, item.z);
                    mesh.visible = false;
                    
                    scene.add(mesh);
                    boxMeshes.push(mesh);
                }});

                animate();
            }}

            function resetarCamera() {{
                if (camera && controls) {{
                    camera.position.set(2.5, 2.0, 2.5);
                    controls.target.set(0.6, 0.4, 0.375);
                }}
            }}

            function animate() {{
                requestAnimationFrame(animate);
                if (controls) controls.update();

                if (animando && currentStep < boxMeshes.length) {{
                    const m = boxMeshes[currentStep];
                    m.visible = true;
                    m.position.y -= (m.position.y - m.userData.targetY) * 0.18;

                    if (Math.abs(m.position.y - m.userData.targetY) < 0.008) {{
                        m.position.y = m.userData.targetY;
                        currentStep++;
                    }}
                }}

                if (renderer && scene && camera) {{
                    renderer.render(scene, camera);
                }}
            }}

            window.addEventListener('load', init);
            if (document.readyState === 'complete') {{
                init();
            }}
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=500)


# --- 9. GERADOR DE PDF ---
def gerar_pdf(df_pallets):
    pdf = FPDF()
    pdf.add_page()

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

        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 6, "SKU", border=1)
        pdf.cell(100, 6, "Produto", border=1)
        pdf.cell(25, 6, "N. Caixa", border=1)
        pdf.cell(25, 6, "Qtd Caixas", border=1)
        pdf.ln()

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


# --- 10. EXECUÇÃO E RESULTADOS IMEDIATOS ---
if st.button("⚙️ CALCULAR E GERAR PALLETS 3D", type="primary"):
    if not st.session_state.carrinho:
        st.warning("Adicione pelo menos um item ao pedido antes de calcular.")
    else:
        df_pallets = processar_pallets_operador(
            st.session_state.carrinho, df_produtos
        )
        pallets_unicos = df_pallets["ID"].unique()

        st.subheader("📦 Resultado da Paletização")

        col_metrica, col_pdf = st.columns([2, 1])
        col_metrica.success(
            f"**Total de Pallets Gerados:** {len(pallets_unicos)}"
        )

        if FPDF_DISPONIVEL:
            try:
                pdf_bytes = gerar_pdf(df_pallets)
                col_pdf.download_button(
                    label="📄 Baixar Relatório (PDF)",
                    data=pdf_bytes,
                    file_name="plano_de_paletizacao.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as err:
                st.error(f"Erro ao gerar PDF: {err}")

        st.markdown("---")

        for p_id in pallets_unicos:
            df_p = df_pallets[df_pallets["ID"] == p_id]
            tipo_pallet = df_p["Tipo"].iloc[0]
            total_cx = int(df_p["Qtd Caixas"].sum())

            st.markdown(
                f"### 📌 {p_id} — Total: {total_cx} caixas ({tipo_pallet})"
            )

            col_tabela, col_3d = st.columns([1, 1.2])

            with col_tabela:
                st.markdown("**Composição do Pallet:**")
                st.dataframe(
                    df_p[["SKU", "Produto", "Nº Caixa", "Qtd Caixas"]],
                    use_container_width=True,
                    hide_index=True,
                )

            with col_3d:
                st.markdown("**Modelo 3D Interativo:**")
                gerar_visualizacao_3d_threejs(df_p)

            st.markdown("---")
