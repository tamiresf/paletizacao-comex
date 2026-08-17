# --- GERADOR GRÁFICO 3D CORRIGIDO (ESTABILIDADE FÍSICA REAL) ---
def gerar_grafico_3d_otimizado(df_pallet_especifico, titulo):
    fig = go.Figure()

    paleta_cores = ['#3B82F6', '#10B981', '#EF4444', '#8B5CF6', '#F59E0B', '#D9A036']
    skus_unicos = df_pallet_especifico['SKU'].unique()
    cor_map = {sku: paleta_cores[i % len(paleta_cores)] for i, sku in enumerate(skus_unicos)}

    # 1. ORDENAÇÃO FÍSICA RIGOROSA: Caixa maior (Ordem_Caixa 3) vai para a BASE, menor para o TOPO
    df_ordenado = df_pallet_especifico.sort_values(by=['Ordem_Caixa', 'SKU'], ascending=[False, True])

    # Desmembra os itens em uma lista de caixas individuais ordenadas da maior para a menor
    lista_caixas_individuais = []
    for _, row in df_ordenado.iterrows():
        sku = row['SKU']
        qtd = int(row['Qtd Caixas'])
        cor = cor_map[sku]
        cx_nome = row['Nº Caixa']
        dims = obter_dimensoes_caixa(cx_nome)
        ordem = row['Ordem_Caixa']
        
        for _ in range(qtd):
            lista_caixas_individuais.append({
                'sku': sku,
                'cor': cor,
                'cx_nome': cx_nome,
                'ordem': ordem,
                'dims': dims
            })

    if not lista_caixas_individuais:
        return fig

    x_cube = [0, 1, 1, 0, 0, 1, 1, 0]
    y_cube = [0, 0, 1, 1, 0, 0, 1, 1]
    z_cube = [0, 0, 0, 0, 1, 1, 1, 1]
    i_mesh = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j_mesh = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k_mesh = [0, 7, 2, 3, 6, 7, 1, 1, 1, 5, 2, 7]

    # 2. ALGORITMO DE EMPILHAMENTO EM GRID FLUIDO
    z_atual = 0.0
    idx = 0
    total_caixas = len(lista_caixas_individuais)

    while idx < total_caixas:
        # Pega as dimensões do tipo de caixa atual para definir a malha do piso
        cx_referencia = lista_caixas_individuais[idx]
        dims = cx_referencia['dims']
        
        dx, dy, cols_x, cols_y = obter_melhor_orientacao(dims['comp'], dims['larg'], PALLET_COMP, PALLET_LARG)
        dz = dims['alt']
        caixas_por_camada = max(1, cols_x * cols_y)

        offset_x = (PALLET_COMP - (cols_x * dx)) / 2.0
        offset_y = (PALLET_LARG - (cols_y * dy)) / 2.0

        # Preenche a camada completa (Lastro) antes de subir o nível Z
        qtd_camada = min(total_caixas - idx, caixas_por_camada)
        
        for i in range(qtd_camada):
            item = lista_caixas_individuais[idx + i]
            
            cx_i = i % cols_x
            cy_i = i // cols_x
            
            x0 = offset_x + cx_i * dx
            y0 = offset_y + cy_i * dy
            
            x_box = [x0 + vx * (dx * 0.98) for vx in x_cube]
            y_box = [y0 + vy * (dy * 0.98) for vy in y_cube]
            z_box = [z_atual + vz * dz for vz in z_cube]

            fig.add_trace(go.Mesh3d(
                x=x_box, y=y_box, z=z_box,
                i=i_mesh, j=j_mesh, k=k_mesh,
                color=item['cor'],
                flatshading=True,
                lighting=dict(ambient=0.85, diffuse=0.9),
                hoverinfo="text",
                text=f"<b>SKU:</b> {item['sku']}<br><b>Tipo:</b> {item['cx_nome']}<br><b>Dimensões:</b> {int(dx*1000)}x{int(dy*1000)}x{int(dz*1000)} mm",
                showscale=False
            ))

        idx += qtd_camada
        z_atual += dz  # Sobe o nível Z apenas quando o lastro do nível atual estiver preenchido

    # Desenho do Estrado Fumigado (Base de Madeira)
    fig.add_trace(go.Mesh3d(
        x=[0, PALLET_COMP, PALLET_COMP, 0, 0, PALLET_COMP, PALLET_COMP, 0],
        y=[0, 0, PALLET_LARG, PALLET_LARG, 0, 0, PALLET_LARG, PALLET_LARG],
        z=[-0.05, -0.05, -0.05, -0.05, 0, 0, 0, 0],
        i=i_mesh, j=j_mesh, k=k_mesh,
        color='#7C4700',
        opacity=0.8,
        hoverinfo="none",
        showscale=False
    ))

    posicoes_travessas = np.linspace(0.05, PALLET_COMP - 0.10, 6)
    for pos_x in posicoes_travessas:
        fig.add_trace(go.Mesh3d(
            x=[pos_x, pos_x+0.08, pos_x+0.08, pos_x, pos_x, pos_x+0.08, pos_x+0.08, pos_x],
            y=[0, 0, PALLET_LARG, PALLET_LARG, 0, 0, PALLET_LARG, PALLET_LARG],
            z=[-0.12, -0.12, -0.12, -0.12, -0.05, -0.05, -0.05, -0.05],
            i=i_mesh, j=j_mesh, k=k_mesh,
            color='#4A2A00',
            opacity=0.9,
            hoverinfo="none",
            showscale=False
        ))

    fig.update_layout(
        title=f"{titulo} ({total_caixas} caixas)",
        scene=dict(
            xaxis=dict(title="Comp (1.20m)", showgrid=True),
            yaxis=dict(title="Larg (0.75m)", showgrid=True),
            zaxis=dict(title="Alt (m)", showgrid=True),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=35),
        showlegend=False
    )
    return fig
