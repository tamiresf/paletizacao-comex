def processar_pallets_operador(carrinho, df_produtos):
    pallets_lista = []
    pallet_id = 1
    sobras_por_sku = []

    # 1. Separar Pallets Fechados (Monoproduto) e Mapear Sobras
    for item in carrinho:
        sku = str(item['SKU']).strip()
        qtd = int(item['Qtd_Caixas'])

        prod = df_produtos[df_produtos['SKU'] == sku].iloc[0]
        cap_pallet = int(prod['QUANTIDADE DE CAIXAS NO PALLET'])
        ordem_cx = int(prod.get('Ordem_Caixa', 0))
        num_caixa = str(prod['NUMERO DA CAIXA']).strip()

        qtd_pallets_fechados = qtd // cap_pallet
        resto = qtd % cap_pallet

        # Pallets Fechados completos
        for _ in range(qtd_pallets_fechados):
            pallets_lista.append({
                'ID': f"Pallet {pallet_id}",
                'Tipo': "Fechado 🟢",
                'SKU': sku,
                'Produto': prod['NOME DO PRODUTO'],
                'Qtd Caixas': cap_pallet,
                'Nº Caixa': num_caixa,
                'Ordem_Caixa': ordem_cx,
                'Capacidade_Max': cap_pallet
            })
            pallet_id += 1

        # Sobra para compor pallets mistos
        if resto > 0:
            sobras_por_sku.append({
                'SKU': sku,
                'Produto': prod['NOME DO PRODUTO'],
                'Qtd Caixas': resto,
                'Nº Caixa': num_caixa,
                'Ordem_Caixa': ordem_cx,
                'Capacidade_Max': cap_pallet
            })

    # 2. Consolidação Contínua nos Pallets Mistos (Preenchendo até 100% de ocupação)
    if sobras_por_sku:
        misto_atual_id = f"Pallet {pallet_id} (Misto)"
        capacidade_usada_fracao = 0.0

        for item_sobra in sobras_por_sku:
            sku = item_sobra['SKU']
            prod_nome = item_sobra['Produto']
            num_caixa = item_sobra['Nº Caixa']
            qtd_restante = item_sobra['Qtd Caixas']
            cap_max = item_sobra['Capacidade_Max']
            ordem_cx = item_sobra['Ordem_Caixa']

            fracao_unidade = 1.0 / cap_max

            while qtd_restante > 0:
                espaco_disponivel = 1.0 - capacidade_usada_fracao
                caixas_que_cabem = int(np.floor((espaco_disponivel + 1e-9) / fracao_unidade))

                # Se o pallet misto atual atingiu o limite (1.0), abre o próximo ID de pallet misto
                if caixas_que_cabem == 0:
                    pallet_id += 1
                    misto_atual_id = f"Pallet {pallet_id} (Misto)"
                    capacidade_usada_fracao = 0.0
                    caixas_que_cabem = int(np.floor((1.0 + 1e-9) / fracao_unidade))

                qtd_alocar = min(qtd_restante, caixas_que_cabem)
                fracao_alocada = qtd_alocar * fracao_unidade

                pallets_lista.append({
                    'ID': misto_atual_id,
                    'Tipo': "Misto 🟡",
                    'SKU': sku,
                    'Produto': prod_nome,
                    'Qtd Caixas': qtd_alocar,
                    'Nº Caixa': num_caixa,
                    'Ordem_Caixa': ordem_cx,
                    'Capacidade_Max': cap_max
                })

                capacidade_usada_fracao += fracao_alocada
                qtd_restante -= qtd_alocar

    return pd.DataFrame(pallets_lista)
