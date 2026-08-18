# --- 10. EXECUÇÃO E RESULTADOS ---
if st.button("⚙️ CALCULAR E GERAR PALLETS 3D"):
    if not st.session_state.carrinho:
        st.warning("Adicione itens ao pedido antes de calcular.")
    else:
        st.session_state.processado = True

if st.session_state.processado and st.session_state.carrinho:
    df_pallets = processar_pallets_operador(
        st.session_state.carrinho, df_produtos
    )

    st.subheader("📦 Detalhamento Individual por Pallet")
    pallets_unicos = df_pallets["ID"].unique()
    st.success(f"**Total de Pallets Gerados:** {len(pallets_unicos)}")

    if FPDF_DISPONIVEL:
        try:
            # Data
            data_atual = datetime.now()
            data_formatada_pdf = data_atual.strftime("%d/%m/%Y")
            data_formatada_arquivo = data_atual.strftime("%d-%m-%Y")

            # Tratamento do Nome do Cliente mantendo a grafia original
            cliente_informado = nome_cliente_input.strip()

            if cliente_informado:
                # Remove apenas caracteres proibidos em nomes de arquivos no S.O.
                cliente_limpo = re.sub(r'[\\/*?:"<>|]', "", cliente_informado)
            else:
                cliente_limpo = "CLIENTE"

            # Nome do Arquivo PDF: PALETIZACAO_{NOME DO CLIENTE}_{DATA}.pdf
            nome_arquivo_pdf = f"PALETIZACAO_{cliente_limpo}_{data_formatada_arquivo}.pdf"

            # Geração do PDF
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

        with st.expander(
            f"📌 {p_id} - Total: {total_cx} caixas ({tipo_pallet})",
            expanded=True,
        ):
            col_tabela, col_3d = st.columns([1, 1])

            with col_tabela:
                st.markdown("**Composição das Caixas:**")
                st.dataframe(
                    df_p[["SKU", "Produto", "Nº Caixa", "Qtd Caixas"]],
                    use_container_width=True,
                )

            with col_3d:
                fig_3d = gerar_grafico_3d_otimizado(
                    df_p, f"Estrutura 3D - {p_id}"
                )
                st.plotly_chart(fig_3d, use_container_width=True)
