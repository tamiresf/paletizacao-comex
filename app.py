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
                    sobra_após = (s1["qtd"] + s2["qtd"]) - cap_alvo
                    if melhor_s2 is None or sobra_após < melhor_s2[0]:
                        melhor_s2 = (sobra_após, s2, cap_alvo)

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

    # Primeiro fecha pallets completos dentro do mesmo tipo de caixa
    for t in sorted(set(r["tipo_cx"] for r in restantes), reverse=True):
        grupo_t = [r for r in restantes if r["tipo_cx"] == t and r["qtd"] > 0]
        if not grupo_t:
            continue

        cpf = grupo_t[0]["cpf"]
        # Usa a capacidade predominante dos itens restantes desse tipo de caixa
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
        # Agrupa por tipo de caixa para montar as fileiras corretamente
        for t in sorted(set(r["tipo_cx"] for r in sobras_finais), reverse=True):
            itens_t = [(r["sku"], r["qtd"]) for r in sobras_finais if r["tipo_cx"] == t]
            cpf_t = next(r["cpf"] for r in sobras_finais if r["tipo_cx"] == t)
            camadas_residuais.extend(_montar_camadas_por_skus(itens_t, t, cpf_t))

        # Divide em blocos de no máximo 5 fileiras (altura padrão) caso ainda restem muitas fileiras
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
