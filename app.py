"""
ART Check – Análise de Risco de Tarefa
Aplicativo para análise, identificação de inconsistências e edição de ARTs.
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode
from analysis import (
    load_excel_safe, clean_dataframe, generate_summary, run_all_analyses,
    check_risk_classification, find_duplicate_arts, find_duplicate_arts_trio,
    find_similar_art_differences, check_task_step_consistency,
    check_risk_cause_controls, check_full_risk_controls,
    find_constant_risks, find_constant_risk_cause_controls,
    check_title_consistency, check_missing_fields,
    find_near_duplicate_arts, compare_art_risk_lines,
    KEY_COLS,
)

# ── Configuração da página ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="ART Check",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS customizado ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 2.5rem; padding-bottom: 1rem; }
    /* Esconder apenas o menu e botão de deploy, sem afetar a sidebar */
    .stDeployButton { display: none !important; }
    #MainMenu { display: none !important; }
    footer { display: none !important; }
    [data-testid="manage-app-button"] { display: none !important; }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem; border-radius: 0.5rem; color: white; text-align: center;
    }
    .metric-card h3 { margin: 0; font-size: 2rem; }
    .metric-card p { margin: 0; font-size: 0.9rem; opacity: 0.85; }
    .issue-badge {
        display: inline-block; padding: 0.2rem 0.6rem;
        border-radius: 1rem; font-weight: bold; font-size: 0.8rem;
    }
    .badge-red { background: #FFCDD2; color: #B71C1C; }
    .badge-yellow { background: #FFF9C4; color: #F57F17; }
    .badge-green { background: #C8E6C9; color: #1B5E20; }
    div[data-testid="stSidebar"] { background-color: #263238; }
    div[data-testid="stSidebar"] .stMarkdown p { color: #ECEFF1; }
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 { color: #FFFFFF; }
</style>
""", unsafe_allow_html=True)


# ── Funções auxiliares ──────────────────────────────────────────────────────────

def load_excel(file) -> pd.DataFrame:
    """Carrega arquivo Excel e retorna DataFrame limpo."""
    df = load_excel_safe(file)
    df = clean_dataframe(df)
    return df


# Caminho do arquivo de exemplo (pode não existir em deploy público)
SAMPLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "data.xlsx")
SAMPLE_EXISTS = os.path.exists(SAMPLE_PATH)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Converte DataFrame para bytes de Excel para download."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Export", index=False)
    return output.getvalue()


def render_aggrid(df: pd.DataFrame, key: str, editable: bool = False,
                  height: int = 500, selection: bool = False,
                  fit_columns: bool = False) -> pd.DataFrame:
    """Renderiza um AG-Grid com configurações padrão."""
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        resizable=True,
        filterable=True,
        sortable=True,
        editable=editable,
        wrapText=True,
        autoHeight=True,
    )

    if selection:
        gb.configure_selection(
            selection_mode="multiple",
            use_checkbox=True,
            header_checkbox=True,
        )

    # Esconder coluna de índice interno se presente
    if "_idx" in df.columns:
        gb.configure_column("_idx", hide=True)

    # Nº Linha nunca deve ser editável
    if "Nº Linha" in df.columns and editable:
        gb.configure_column("Nº Linha", editable=False)

    # Colunas com texto longo usam editor de área de texto (popup)
    long_text_cols = (
        "MEDIDA DE CONTROLE", "CAUSA", "CONSEQUÊNCIA", "SITUAÇÃO DE RISCO",
        "NOME DO PASSO", "TAREFA", "TITULO DA ART",
    )
    if editable:
        for col in df.columns:
            if col in long_text_cols:
                gb.configure_column(
                    col,
                    cellEditor="agLargeTextCellEditor",
                    cellEditorPopup=True,
                    cellEditorParams={"maxLength": 10000, "rows": 10, "cols": 80},
                )

    if fit_columns and len(df.columns) <= 8:
        gb.configure_grid_options(domLayout="autoHeight")
    else:
        for col in df.columns:
            if col in ("MEDIDA DE CONTROLE", "CAUSA", "CONSEQUÊNCIA",
                       "Medidas Encontradas", "Colunas Divergentes",
                       "NOME DO PASSO", "SITUAÇÃO DE RISCO", "Títulos",
                       "Títulos das ARTs", "IDs ART envolvidos"):
                gb.configure_column(col, width=300)
            elif col in ("ID ART", "ITEM", "Nº Linha", "Linha", "Qtd Linhas"):
                gb.configure_column(col, width=90)

    grid_options = gb.build()
    grid_options["enableCellTextSelection"] = True

    # Determinar eventos que disparam atualização
    _update_events = []
    if editable:
        _update_events.append("cellValueChanged")
    if selection:
        _update_events.append("selectionChanged")

    # Adicionar versão ao key para forçar re-render quando dados mudam
    grid_version = st.session_state.get("_grid_version", 0)
    effective_key = f"{key}_v{grid_version}"

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        height=height,
        update_on=_update_events if _update_events else [],
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=fit_columns,
        theme="streamlit",
        key=effective_key,
        allow_unsafe_jscode=False,
    )

    result_data = pd.DataFrame(grid_response["data"])
    selected = grid_response.get("selected_rows", None)
    if selected is not None:
        if isinstance(selected, pd.DataFrame):
            result_selected = selected
        elif isinstance(selected, list) and len(selected) > 0:
            result_selected = pd.DataFrame(selected)
        else:
            result_selected = pd.DataFrame()
    else:
        result_selected = pd.DataFrame()

    return result_data, result_selected


def badge(count: int, label: str) -> str:
    """Retorna HTML de badge colorido."""
    if count == 0:
        css = "badge-green"
    elif count <= 5:
        css = "badge-yellow"
    else:
        css = "badge-red"
    return f'<span class="issue-badge {css}">{count} {label}</span>'


# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🛡️ ART Check")
    st.markdown("**Análise de Risco de Tarefa**")
    st.markdown("---")

    uploaded_file = st.file_uploader(
        "📂 Carregar planilha (.xlsx)",
        type=["xlsx"],
        help="Carregue o arquivo Excel exportado do sistema de ARTs.",
    )

    use_sample = st.checkbox(
        "Usar dados de exemplo",
        value=uploaded_file is None and SAMPLE_EXISTS,
        disabled=not SAMPLE_EXISTS,
        help=(
            "Carrega o arquivo assets/data.xlsx como exemplo."
            if SAMPLE_EXISTS
            else "Dados de exemplo indisponíveis. Faça o upload de uma planilha .xlsx."
        ),
    )

    st.markdown("---")
    st.markdown("### Navegação")
    page = st.radio(
        "Selecione a seção:",
        [
            "📊 Painel Geral",
            "📋 Visualizar / Editar Dados",
            "🔍 Análise: Classificação de Risco",
            "🔄 Análise: ARTs Duplicadas",
            "📝 Análise: Diferenças entre ARTs",
            "⚠️ Análise: Consistência Tarefa/Passo",
            "🎯 Análise: Controles por Risco+Causa",
            "🔗 Análise: Controles por Risco Completo",
            "🔁 Análise: Riscos Constantes",
            "🔂 Análise: Constantes Completos",
            "⚖️ Análise: Linhas Divergentes por ID",
            "📌 Análise: Títulos Divergentes",
            "❓ Análise: Campos Vazios",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(
        "<small style='color:#90A4AE'>ART Check v1.0<br>"
        "Desenvolvido para análise e melhoria de ARTs<br><br>"
        "Produzido por: Leonardo Manzoli Stoco<br>"
        "leonardo.stoco@sodexo.com<br>"
        "27 9 8133 7562<br><br>"
        "Limpeza Industrial<br>"
        "Porto de Tubarão</small>",
        unsafe_allow_html=True,
    )


# ── Carregar dados ──────────────────────────────────────────────────────────────

@st.cache_data
def load_cached(file_bytes: bytes) -> pd.DataFrame:
    return load_excel(BytesIO(file_bytes))


@st.cache_data
def load_sample() -> pd.DataFrame:
    return load_excel(SAMPLE_PATH)


# Inicializar estado
if "df_edited" not in st.session_state:
    st.session_state.df_edited = None
if "_source_id" not in st.session_state:
    st.session_state["_source_id"] = None

# Definir qual fonte de dados usar
df_source = None
current_source_id = None
if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    current_source_id = f"upload_{uploaded_file.name}_{len(file_bytes)}"
    df_source = load_cached(file_bytes)
elif use_sample:
    current_source_id = "sample"
    try:
        df_source = load_sample()
    except FileNotFoundError:
        st.info("👆 Carregue um arquivo Excel na barra lateral para começar.")
        st.stop()

if df_source is None:
    st.info("👆 Carregue um arquivo Excel na barra lateral para começar.")
    st.stop()

# Se a fonte de dados mudou (novo arquivo ou troca de modo), resetar df_edited
if st.session_state["_source_id"] != current_source_id:
    st.session_state.df_edited = df_source.copy()
    st.session_state["_source_id"] = current_source_id
    st.session_state["_grid_version"] = st.session_state.get("_grid_version", 0) + 1

# Garantia de inicialização
if st.session_state.df_edited is None:
    st.session_state.df_edited = df_source.copy()

df = st.session_state.df_edited


# ═══════════════════════════════════════════════════════════════════════════════
#  PÁGINA: Painel Geral
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📊 Painel Geral":
    st.markdown("## 📊 Painel Geral")

    summary = generate_summary(df)

    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Linhas", f"{summary['Total de Linhas']:,}")
    with col2:
        st.metric("IDs ART Únicos", summary["IDs ART Únicos"])
    with col3:
        st.metric("Tarefas Únicas", summary["Tarefas Únicas"])
    with col4:
        st.metric("Situações de Risco", summary["Situações de Risco Únicas"])

    st.markdown("---")

    # ── Resumo de IDs e Passos da Tarefa ────────────────────────────────────
    st.markdown("### 📋 Estrutura das ARTs – IDs e Passos")

    # Construir tabela de resumo: ID ART, Título, Tarefa, Qtd Passos, Passos
    resume_rows = []
    for id_art, group in df.groupby("ID ART"):
        titulo = group["TITULO DA ART"].iloc[0] if "TITULO DA ART" in group.columns else ""
        tarefa = group["TAREFA"].iloc[0] if "TAREFA" in group.columns else ""
        passos = group["PASSO DA TAREFA"].dropna().unique() if "PASSO DA TAREFA" in group.columns else []
        itens = group["ITEM"].dropna().unique() if "ITEM" in group.columns else []
        resume_rows.append({
            "ID ART": id_art,
            "TITULO DA ART": titulo,
            "TAREFA": tarefa,
            "Qtd Passos": len(passos),
            "Qtd Itens": len(itens),
            "Passos": " | ".join(str(p) for p in sorted(passos)),
        })
    resume_df = pd.DataFrame(resume_rows)

    # Filtros
    with st.expander("🔍 Filtros", expanded=True):
        fc_r1, fc_r2, fc_r3 = st.columns(3)
        with fc_r1:
            id_opts_res = sorted(resume_df["ID ART"].unique())
            id_filter_res = st.multiselect("ID ART", options=id_opts_res, default=[], key="res_id")
        with fc_r2:
            tarefa_opts_res = sorted(resume_df["TAREFA"].dropna().unique())
            tarefa_filter_res = st.multiselect("TAREFA", options=tarefa_opts_res, default=[], key="res_tarefa")
        with fc_r3:
            titulo_opts_res = sorted(resume_df["TITULO DA ART"].dropna().unique())
            titulo_filter_res = st.multiselect("TITULO DA ART", options=titulo_opts_res, default=[], key="res_titulo")

    resume_view = resume_df.copy()
    if id_filter_res:
        resume_view = resume_view[resume_view["ID ART"].isin(id_filter_res)]
    if tarefa_filter_res:
        resume_view = resume_view[resume_view["TAREFA"].isin(tarefa_filter_res)]
    if titulo_filter_res:
        resume_view = resume_view[resume_view["TITULO DA ART"].isin(titulo_filter_res)]

    st.markdown(f"**{len(resume_view)}** ID(s) ART exibido(s)")
    render_aggrid(resume_view.reset_index(drop=True), key="resume_ids", height=400)
    st.download_button(
        "📥 Exportar Resumo",
        data=to_excel_bytes(resume_view.reset_index(drop=True)),
        file_name="Resumo_IDs_Passos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="exp_resume_ids",
    )

    st.markdown("---")

    # Distribuição de risco
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("### Risco Residual")
        if summary["Distribuição Risco"]:
            risk_df = pd.DataFrame(
                list(summary["Distribuição Risco"].items()),
                columns=["Nível", "Quantidade"],
            )
            st.bar_chart(risk_df.set_index("Nível"))

    with col_b:
        st.markdown("### Probabilidade")
        if summary["Distribuição Probabilidade"]:
            prob_df = pd.DataFrame(
                list(summary["Distribuição Probabilidade"].items()),
                columns=["Nível", "Quantidade"],
            )
            st.bar_chart(prob_df.set_index("Nível"))

    with col_c:
        st.markdown("### Severidade")
        if summary["Distribuição Severidade"]:
            sev_df = pd.DataFrame(
                list(summary["Distribuição Severidade"].items()),
                columns=["Nível", "Quantidade"],
            )
            st.bar_chart(sev_df.set_index("Nível"))

    # Resumo de análises
    st.markdown("---")
    st.markdown("### 🔍 Resumo das Análises")

    with st.spinner("Executando todas as análises..."):
        results = run_all_analyses(df)

    analysis_items = [
        ("Classificação de Risco", results["risk_classification"]),
        ("ARTs Duplicadas", results["duplicate_arts"][0]),
        ("Diferenças entre ARTs", results["similar_differences"]),
        ("Consistência Tarefa/Passo", results["task_consistency"]),
        ("Controles por Risco+Causa", results["risk_cause_controls"]),
        ("Controles por Risco Completo", results["full_risk_controls"]),
        ("Riscos Constantes", results["constant_risks"]),
        ("Constantes Completos", results["constant_risk_cause_controls"]),
        ("Títulos Divergentes", results["title_consistency"]),
        ("Campos Vazios", results["missing_fields"]),
    ]

    cols = st.columns(3)
    for i, (name, result_df) in enumerate(analysis_items):
        with cols[i % 3]:
            count = len(result_df)
            if count == 0:
                icon = "✅"
            elif count <= 5:
                icon = "⚠️"
            else:
                icon = "🔴"
            st.markdown(f"{icon} **{name}**: {count} ocorrência(s)")


# ═══════════════════════════════════════════════════════════════════════════════
#  PÁGINA: Visualizar / Editar Dados
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📋 Visualizar / Editar Dados":
    st.markdown("## 📋 Visualizar e Editar Dados")

    # Filtros
    with st.expander("🔍 Filtros", expanded=True):
        fc0a, fc0b = st.columns([1, 1])
        with fc0a:
            linha_filter_txt = st.text_input(
                "Nº Linha(s)",
                value="",
                placeholder="ex: 1687  ou  1680-1690",
                help="Digite um número, vários separados por vírgula ou um intervalo com hífen. Ex: 1687,1700  ou  1680-1690",
            )
        with fc0b:
            if "TIPO EFEITO" in df.columns:
                tipo_efeito_filter = st.multiselect(
                    "TIPO EFEITO",
                    options=sorted(df["TIPO EFEITO"].dropna().unique()),
                    default=[],
                )
            else:
                tipo_efeito_filter = []
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            id_filter = st.multiselect(
                "ID ART",
                options=sorted(df["ID ART"].unique()),
                default=[],
            )
        with fc2:
            tarefa_filter = st.multiselect(
                "TAREFA",
                options=sorted(df["TAREFA"].dropna().unique()),
                default=[],
            )
        with fc3:
            risco_filter = st.multiselect(
                "RISCO RESIDUAL",
                options=sorted(df["RISCO RESIDUAL (PRIORIDADE)"].dropna().unique()),
                default=[],
            )

        fc4, fc5, fc_sit = st.columns(3)
        with fc4:
            passo_filter = st.multiselect(
                "PASSO DA TAREFA",
                options=sorted(df["PASSO DA TAREFA"].dropna().unique()),
                default=[],
            )
        with fc5:
            item_filter = st.multiselect(
                "ITEM",
                options=sorted(df["ITEM"].dropna().unique()),
                default=[],
            )
        with fc_sit:
            sit_filter = st.multiselect(
                "SITUAÇÃO DE RISCO",
                options=sorted(df["SITUAÇÃO DE RISCO"].dropna().unique()),
                default=[],
            )

        fc6, fc7, fc8 = st.columns(3)
        with fc6:
            causa_filter = st.multiselect(
                "CAUSA",
                options=sorted(df["CAUSA"].dropna().unique()),
                default=[],
            )
        with fc7:
            conseq_filter = st.multiselect(
                "CONSEQUÊNCIA",
                options=sorted(df["CONSEQUÊNCIA"].dropna().unique()),
                default=[],
            )
        with fc8:
            medida_filter = st.multiselect(
                "MEDIDA DE CONTROLE",
                options=sorted(df["MEDIDA DE CONTROLE"].dropna().unique()),
                default=[],
            )

    # Aplicar filtros
    df_view = df.copy()
    # Filtro por Nº Linha (suporta valores individuais, listas e intervalos)
    if linha_filter_txt.strip():
        linha_nums = set()
        for part in linha_filter_txt.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    a, b = part.split("-", 1)
                    linha_nums.update(range(int(a.strip()), int(b.strip()) + 1))
                except ValueError:
                    pass
            elif part.isdigit():
                linha_nums.add(int(part))
        if linha_nums and "Nº Linha" in df_view.columns:
            df_view = df_view[df_view["Nº Linha"].isin(linha_nums)]
    if id_filter:
        df_view = df_view[df_view["ID ART"].isin(id_filter)]
    if tarefa_filter:
        df_view = df_view[df_view["TAREFA"].isin(tarefa_filter)]
    if risco_filter:
        df_view = df_view[df_view["RISCO RESIDUAL (PRIORIDADE)"].isin(risco_filter)]
    if passo_filter:
        df_view = df_view[df_view["PASSO DA TAREFA"].isin(passo_filter)]
    if item_filter:
        df_view = df_view[df_view["ITEM"].isin(item_filter)]
    if sit_filter:
        df_view = df_view[df_view["SITUAÇÃO DE RISCO"].isin(sit_filter)]
    if causa_filter:
        df_view = df_view[df_view["CAUSA"].isin(causa_filter)]
    if conseq_filter:
        df_view = df_view[df_view["CONSEQUÊNCIA"].isin(conseq_filter)]
    if medida_filter:
        df_view = df_view[df_view["MEDIDA DE CONTROLE"].isin(medida_filter)]
    if tipo_efeito_filter and "TIPO EFEITO" in df_view.columns:
        df_view = df_view[df_view["TIPO EFEITO"].isin(tipo_efeito_filter)]

    st.markdown(f"**{len(df_view):,}** linhas exibidas de **{len(df):,}** total")

    # Seleção de colunas
    all_cols = list(df_view.columns)
    extended_default = [c for c in KEY_COLS if c != "NOME DO PASSO"] + ["RISCO CONSTANTE"]
    default_cols = [c for c in extended_default if c in all_cols]
    selected_cols = st.multiselect(
        "Colunas visíveis",
        options=all_cols,
        default=default_cols,
        help="Selecione quais colunas deseja visualizar e editar.",
    )

    if not selected_cols:
        selected_cols = default_cols

    st.markdown("---")

    # Adicionar coluna de índice original para rastreamento (no final, para não
    # roubar o checkboxSelection que o AG-Grid coloca na primeira coluna visível)
    grid_data = df_view[selected_cols].copy()
    grid_data["_idx"] = df_view.index.values

    # Grid com seleção (sem edição inline — usar botão Salvar para editar)
    edited_df, selected_rows = render_aggrid(
        grid_data.reset_index(drop=True),
        key="main_grid",
        editable=True,
        height=600,
        selection=True,
    )

    # Persistir seleção no session_state para sobreviver ao rerun
    if not selected_rows.empty:
        st.session_state["_selected_indices"] = selected_rows["_idx"].tolist()
    elif "_selected_indices" not in st.session_state:
        st.session_state["_selected_indices"] = []

    n_selected = len(st.session_state.get("_selected_indices", []))
    if n_selected > 0:
        st.info(f"✅ {n_selected} linha(s) selecionada(s)")

    # Botões de ação
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)

    with col_btn1:
        if st.button("💾 Salvar Alterações", type="primary"):
            # Usar _idx para mapear de volta ao dataframe original
            if "_idx" in edited_df.columns:
                save_cols = [c for c in selected_cols if c in edited_df.columns and c in df.columns]
                for _, row in edited_df.iterrows():
                    orig_idx = int(row["_idx"])
                    if orig_idx in st.session_state.df_edited.index:
                        for col in save_cols:
                            st.session_state.df_edited.at[orig_idx, col] = row[col]

            # Incrementar versão do grid para refletir dados salvos
            st.session_state["_grid_version"] = st.session_state.get("_grid_version", 0) + 1
            st.success("✅ Alterações salvas com sucesso!")
            st.rerun()

    with col_btn2:
        if st.button("🔄 Recarregar Original"):
            st.session_state.df_edited = df_source.copy()
            st.session_state["_selected_indices"] = []
            # Incrementar versão do grid para forçar re-render
            st.session_state["_grid_version"] = st.session_state.get("_grid_version", 0) + 1
            st.success("🔄 Dados originais restaurados!")
            st.rerun()

    with col_btn3:
        excel_bytes = to_excel_bytes(st.session_state.df_edited)
        st.download_button(
            label="📥 Exportar Excel",
            data=excel_bytes,
            file_name="ART_Check_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col_btn4:
        if st.button("🗑️ Excluir Selecionados"):
            indices_to_remove = st.session_state.get("_selected_indices", [])
            if not indices_to_remove:
                st.warning("Selecione ao menos uma linha na tabela (checkbox) antes de excluir.")
            else:
                n_before = len(st.session_state.df_edited)
                st.session_state.df_edited = st.session_state.df_edited.drop(
                    index=[i for i in indices_to_remove if i in st.session_state.df_edited.index]
                ).reset_index(drop=True)
                n_removed = n_before - len(st.session_state.df_edited)
                st.session_state["_selected_indices"] = []
                # Incrementar versão do grid para forçar re-render
                st.session_state["_grid_version"] = st.session_state.get("_grid_version", 0) + 1
                st.success(f"✅ {n_removed} linha(s) excluída(s).")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Classificação de Risco
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🔍 Análise: Classificação de Risco":
    st.markdown("## 🔍 Validação da Classificação de Risco")
    st.markdown(
        "Verifica se a coluna **RISCO RESIDUAL (PRIORIDADE)** está coerente "
        "com a combinação de **PROBABILIDADE RESIDUAL × SEVERIDADE RESIDUAL** "
        "conforme a matriz de risco padrão."
    )

    with st.spinner("Analisando..."):
        result = check_risk_classification(df)

    if result.empty:
        st.success("✅ Todas as classificações estão consistentes com a matriz de risco!")
    else:
        st.error(f"🔴 {len(result)} inconsistência(s) encontrada(s)")
        st.caption(
            "Selecione as linhas (checkbox) e clique em **Corrigir** para ajustar "
            "o RISCO RESIDUAL (PRIORIDADE) para o RISCO ESPERADO da matriz."
        )
        _, rc_selected = render_aggrid(
            result, key="risk_class", height=400, selection=True
        )

        # Persistir seleção no session_state para sobreviver ao rerun
        if not rc_selected.empty and "Nº Linha" in rc_selected.columns:
            st.session_state["_rc_selected_linhas"] = rc_selected["Nº Linha"].tolist()
        elif "_rc_selected_linhas" not in st.session_state:
            st.session_state["_rc_selected_linhas"] = []

        n_rc_sel = len(st.session_state.get("_rc_selected_linhas", []))
        if n_rc_sel > 0:
            st.info(f"✅ {n_rc_sel} linha(s) selecionada(s) para correção")

        col_rc1, col_rc2 = st.columns(2)
        with col_rc1:
            if st.button("🛠️ Corrigir Selecionados", type="primary", key="btn_corrigir_risco"):
                linhas_sel = st.session_state.get("_rc_selected_linhas", [])
                if not linhas_sel:
                    st.warning("Selecione ao menos uma linha (checkbox) antes de corrigir.")
                else:
                    esperado_map = dict(
                        zip(result["Nº Linha"], result["RISCO ESPERADO"])
                    )
                    n_corr = 0
                    for linha in linhas_sel:
                        expected = esperado_map.get(linha)
                        if expected is None:
                            continue
                        mask = st.session_state.df_edited["Nº Linha"] == linha
                        if mask.any():
                            st.session_state.df_edited.loc[
                                mask, "RISCO RESIDUAL (PRIORIDADE)"
                            ] = expected
                            n_corr += int(mask.sum())
                    st.session_state["_rc_selected_linhas"] = []
                    st.session_state["_grid_version"] = st.session_state.get("_grid_version", 0) + 1
                    st.success(f"✅ {n_corr} linha(s) corrigida(s).")
                    st.rerun()

        with col_rc2:
            st.download_button(
                "📥 Exportar Resultado",
                data=to_excel_bytes(result),
                file_name="Classificacao_Risco.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="exp_risk_class",
            )

        # Mostrar matriz de referência
        with st.expander("📖 Matriz de Risco de Referência"):
            from analysis import RISK_MATRIX
            matrix_data = []
            for (prob, sev), risco in RISK_MATRIX.items():
                matrix_data.append({
                    "PROBABILIDADE": prob,
                    "SEVERIDADE": sev,
                    "RISCO ESPERADO": risco,
                })
            st.dataframe(pd.DataFrame(matrix_data), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: ARTs Duplicadas
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🔄 Análise: ARTs Duplicadas":
    st.markdown("## 🔄 ARTs com Dados Idênticos")
    st.markdown(
        "Identifica grupos de **ID ART** que possuem dados completamente idênticos "
        "nas colunas relevantes, candidatos à exclusão de duplicatas."
    )

    with st.spinner("Analisando..."):
        groups_df, dup_rows = find_duplicate_arts(df)

    if groups_df.empty:
        st.success("✅ Nenhuma ART duplicada encontrada!")
    else:
        n_groups = groups_df["Grupo"].nunique() if not groups_df.empty else 0
        n_ids = groups_df["ID ART"].nunique() if not groups_df.empty else 0
        st.error(f"🔴 {n_groups} grupo(s) de ARTs idênticas encontrado(s), totalizando {n_ids} IDs")

        st.markdown("### Grupos de Duplicatas")
        render_aggrid(groups_df, key="dup_groups", height=300, fit_columns=True)
        st.download_button(
            "📥 Exportar Grupos",
            data=to_excel_bytes(groups_df),
            file_name="Duplicatas_Grupos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_dup_groups",
        )

        st.markdown("### Dados das ARTs Duplicadas")

        # Filtro por grupo
        group_options = sorted(groups_df["Grupo"].unique())
        selected_group = st.selectbox(
            "Filtrar por Grupo:",
            options=["Todos"] + [f"Grupo {g}" for g in group_options],
        )

        if selected_group != "Todos":
            g_num = int(selected_group.split(" ")[1])
            group_ids = groups_df[groups_df["Grupo"] == g_num]["ID ART"].tolist()
            display_rows = dup_rows[dup_rows["ID ART"].isin(group_ids)]
        else:
            display_rows = dup_rows

        display_cols = [c for c in KEY_COLS if c in display_rows.columns and c != "NOME DO PASSO"]
        render_aggrid(
            display_rows[display_cols].reset_index(drop=True),
            key="dup_rows",
            height=400,
            selection=True,
        )

        dup_ids_to_remove = st.multiselect(
            "Selecione os IDs ART para REMOVER (excluir todas as linhas):",
            options=sorted(dup_rows["ID ART"].unique()),
        )

        if st.button("🗑️ Remover IDs Selecionados", type="primary"):
            if dup_ids_to_remove:
                st.session_state.df_edited = st.session_state.df_edited[
                    ~st.session_state.df_edited["ID ART"].isin(dup_ids_to_remove)
                ].reset_index(drop=True)
                st.success(
                    f"✅ {len(dup_ids_to_remove)} ID(s) removido(s): "
                    f"{', '.join(str(x) for x in dup_ids_to_remove)}"
                )
                st.rerun()
            else:
                st.warning("Selecione ao menos um ID para remover.")

    # ── ARTs idênticas por Situação + Causa + Medida ─────────────────────────
    st.markdown("---")
    st.markdown("## 🔗 ARTs Idênticas em Situação + Causa + Medida")
    st.markdown(
        "Identifica grupos de **ID ART** cujas combinações de "
        "**SITUAÇÃO DE RISCO + CAUSA + MEDIDA DE CONTROLE** são idênticas "
        "(ignora as demais colunas como CONSEQUÊNCIA, PROBABILIDADE, SEVERIDADE etc.)."
    )

    with st.spinner("Analisando..."):
        trio_groups_df, trio_dup_rows = find_duplicate_arts_trio(df)

    if trio_groups_df.empty:
        st.success("✅ Nenhum grupo encontrado com Situação+Causa+Medida idênticas!")
    else:
        n_trio_groups = trio_groups_df["Grupo"].nunique()
        n_trio_ids = trio_groups_df["ID ART"].nunique()
        st.warning(f"⚠️ {n_trio_groups} grupo(s) com Situação+Causa+Medida idênticas, totalizando {n_trio_ids} IDs")

        st.markdown("### Grupos")
        render_aggrid(trio_groups_df, key="trio_groups", height=300, fit_columns=True)
        st.download_button(
            "📥 Exportar Grupos (Trio)",
            data=to_excel_bytes(trio_groups_df),
            file_name="Duplicatas_Trio_Grupos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_trio_groups",
        )

        st.markdown("### Dados das ARTs")
        trio_group_options = sorted(trio_groups_df["Grupo"].unique())
        selected_trio_group = st.selectbox(
            "Filtrar por Grupo:",
            options=["Todos"] + [f"Grupo {g}" for g in trio_group_options],
            key="trio_group_sel",
        )

        if selected_trio_group != "Todos":
            g_num = int(selected_trio_group.split(" ")[1])
            trio_ids = trio_groups_df[trio_groups_df["Grupo"] == g_num]["ID ART"].tolist()
            trio_display = trio_dup_rows[trio_dup_rows["ID ART"].isin(trio_ids)]
        else:
            trio_display = trio_dup_rows

        trio_show_cols = ["Nº Linha", "ID ART", "TITULO DA ART", "TAREFA",
                         "PASSO DA TAREFA", "ITEM",
                         "SITUAÇÃO DE RISCO", "CAUSA", "MEDIDA DE CONTROLE"]
        trio_show_cols = [c for c in trio_show_cols if c in trio_display.columns]
        render_aggrid(
            trio_display[trio_show_cols].reset_index(drop=True),
            key="trio_rows",
            height=400,
        )
        st.download_button(
            "📥 Exportar Dados (Trio)",
            data=to_excel_bytes(trio_display[trio_show_cols].reset_index(drop=True)),
            file_name="Duplicatas_Trio_Dados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_trio_data",
        )

    # ── ARTs quase idênticas ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## 🔍 ARTs Quase Idênticas (IDs Distintos)")
    st.markdown(
        "Compara **todos os pares de ID ART** e calcula a similaridade das linhas. "
        "Pares com alta similaridade mas não 100 %% idênticos são listados abaixo."
    )

    sim_threshold = st.slider(
        "Similaridade mínima",
        min_value=50, max_value=99, value=75, step=5,
        format="%d%%",
        help="Pares com similaridade igual ou acima deste valor serão exibidos.",
        key="sim_thresh",
    )

    with st.spinner("Comparando pares de ARTs..."):
        # Construir conjunto de pares já 100% idênticos para excluí-los
        exact_pairs: set = set()
        if not groups_df.empty:
            for _, g in groups_df.groupby("Grupo"):
                g_ids = g["ID ART"].tolist()
                for ia in range(len(g_ids)):
                    for ib in range(ia + 1, len(g_ids)):
                        exact_pairs.add(frozenset([g_ids[ia], g_ids[ib]]))

        near_dup = find_near_duplicate_arts(
            df, threshold=sim_threshold / 100.0, exact_ids=exact_pairs,
        )

    if near_dup.empty:
        st.info("ℹ️ Nenhum par quase idêntico encontrado acima do limiar selecionado.")
    else:
        st.warning(f"⚠️ {len(near_dup)} par(es) quase idêntico(s) encontrado(s)")

        # Filtros
        with st.expander("🔍 Filtros", expanded=False):
            fc_nd1, fc_nd2 = st.columns(2)
            with fc_nd1:
                all_ids_nd = sorted(
                    set(near_dup["ID ART (A)"].tolist() + near_dup["ID ART (B)"].tolist())
                )
                id_filter_nd = st.multiselect("ID ART", options=all_ids_nd, default=[], key="nd_id")
            with fc_nd2:
                sim_values = sorted(near_dup["Similaridade"].unique(), reverse=True)
                sim_filter_nd = st.multiselect("Similaridade", options=sim_values, default=[], key="nd_sim")

        nd_view = near_dup.copy()
        if id_filter_nd:
            nd_view = nd_view[
                nd_view["ID ART (A)"].isin(id_filter_nd)
                | nd_view["ID ART (B)"].isin(id_filter_nd)
            ]
        if sim_filter_nd:
            nd_view = nd_view[nd_view["Similaridade"].isin(sim_filter_nd)]

        st.markdown(f"**{len(nd_view)}** par(es) exibido(s)")
        render_aggrid(nd_view.reset_index(drop=True), key="near_dup", height=500)
        st.download_button(
            "📥 Exportar Quase Idênticas",
            data=to_excel_bytes(nd_view.reset_index(drop=True)),
            file_name="ARTs_Quase_Identicas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_near_dup",
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Diferenças entre ARTs
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📝 Análise: Diferenças entre ARTs":
    st.markdown("## 📝 Diferenças entre ARTs com Mesmo Título")
    st.markdown(
        "Identifica IDs ART diferentes que compartilham o mesmo **TITULO DA ART** "
        "mas possuem dados divergentes, mostrando quais colunas diferem."
    )

    with st.spinner("Analisando..."):
        result = find_similar_art_differences(df)

    if result.empty:
        st.success("✅ Nenhuma divergência encontrada entre ARTs com mesmo título!")
    else:
        st.warning(f"⚠️ {len(result)} divergência(s) encontrada(s)")
        render_aggrid(result, key="diff_arts", height=400)
        st.download_button(
            "📥 Exportar Divergências",
            data=to_excel_bytes(result),
            file_name="Diferencas_ARTs.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_diff_arts",
        )

        # Detalhar um par específico
        if len(result) > 0:
            st.markdown("### 🔎 Detalhar Comparação")
            selected_pair = st.selectbox(
                "Selecione um par para comparar:",
                options=range(len(result)),
                format_func=lambda i: f"ID {result.iloc[i]['ID ART (A)']} vs {result.iloc[i]['ID ART (B)']}",
            )

            row = result.iloc[selected_pair]
            id_a = row["ID ART (A)"]
            id_b = row["ID ART (B)"]

            col_a, col_b = st.columns(2)
            compare_cols = [c for c in KEY_COLS if c != "ID ART" and c in df.columns]

            with col_a:
                st.markdown(f"**ID ART: {id_a}**")
                data_a = df[df["ID ART"] == id_a][compare_cols]
                render_aggrid(data_a.reset_index(drop=True), key=f"compare_a_{selected_pair}", height=300)

            with col_b:
                st.markdown(f"**ID ART: {id_b}**")
                data_b = df[df["ID ART"] == id_b][compare_cols]
                render_aggrid(data_b.reset_index(drop=True), key=f"compare_b_{selected_pair}", height=300)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Consistência Tarefa/Passo
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "⚠️ Análise: Consistência Tarefa/Passo":
    st.markdown("## ⚠️ Consistência entre TAREFA, ITEM e PASSO")
    st.markdown(
        "Verifica se no mesmo **NOME DO PASSO** de uma tarefa existem "
        "valores diferentes de **ITEM** ou **PASSO DA TAREFA**."
    )
    st.markdown("---")

    # Pré-calcular quais IDs têm inconsistências para filtrar o dropdown
    with st.spinner("Identificando IDs com inconsistências..."):
        all_result = check_task_step_consistency(df)

    if all_result.empty:
        st.success("✅ Todas as tarefas estão consistentes em todos os IDs!")
    else:
        ids_com_problema = sorted(all_result["ID ART"].unique())
        st.info(f"📌 {len(ids_com_problema)} ID(s) com inconsistências encontrado(s)")

        selected_id = st.selectbox(
            "🔍 Selecione o ID ART para analisar:",
            options=ids_com_problema,
            index=0,
        )

        result = all_result[all_result["ID ART"] == selected_id].reset_index(drop=True)
        df_filtered = df[df["ID ART"] == selected_id]
        st.caption(f"ID ART **{selected_id}** — {len(df_filtered)} linhas")

        st.warning(f"⚠️ {len(result)} inconsistência(s) encontrada(s) no ID {selected_id}")
        render_aggrid(result, key="task_consist", height=400)
        st.download_button(
            "📥 Exportar Inconsistências",
            data=to_excel_bytes(result),
            file_name="Consistencia_Tarefa_Passo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_task_consist",
        )

        # Mostrar dados do ID para referência
        with st.expander("📋 Ver dados do ID selecionado", expanded=False):
            ref_cols = ["ID ART", "TAREFA", "ITEM", "PASSO DA TAREFA", "NOME DO PASSO", "SITUAÇÃO DE RISCO"]
            ref_cols = [c for c in ref_cols if c in df_filtered.columns]
            render_aggrid(df_filtered[ref_cols].reset_index(drop=True), key="task_ref", height=300)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Controles por Risco + Causa
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🎯 Análise: Controles por Risco+Causa":
    st.markdown("## 🎯 Medidas de Controle por Situação de Risco + Causa")
    st.markdown(
        "Verifica se linhas com mesma **SITUAÇÃO DE RISCO** e **CAUSA** "
        "possuem a mesma **MEDIDA DE CONTROLE**."
    )

    with st.spinner("Analisando..."):
        result = check_risk_cause_controls(df)

    if result.empty:
        st.success("✅ Todas as combinações Risco+Causa possuem medidas consistentes!")
    else:
        st.warning(f"⚠️ {len(result)} divergência(s) encontrada(s)")

        # Filtros
        with st.expander("🔍 Filtros", expanded=True):
            fc_a, fc_b, fc_c = st.columns(3)
            with fc_a:
                # Extrair todos os IDs individuais das divergências
                all_ids_rc = set()
                for ids_str in result["IDs ART envolvidos"].dropna():
                    for id_val in str(ids_str).split(" | "):
                        id_val = id_val.strip()
                        if id_val:
                            all_ids_rc.add(id_val)
                id_opts_rc = sorted(all_ids_rc)
                id_filter_rc = st.multiselect("ID ART", options=id_opts_rc, default=[], key="rc_id")
            with fc_b:
                sit_opts = sorted(result["SITUAÇÃO DE RISCO"].dropna().unique()) if "SITUAÇÃO DE RISCO" in result.columns else []
                sit_filter_rc = st.multiselect("SITUAÇÃO DE RISCO", options=sit_opts, default=[], key="rc_sit")
            with fc_c:
                causa_opts = sorted(result["CAUSA"].dropna().unique()) if "CAUSA" in result.columns else []
                causa_filter_rc = st.multiselect("CAUSA", options=causa_opts, default=[], key="rc_causa")

        result_view = result.copy()
        if id_filter_rc:
            mask = result_view["IDs ART envolvidos"].apply(
                lambda x: any(id_val in str(x).split(" | ") for id_val in id_filter_rc)
            )
            result_view = result_view[mask]
        if sit_filter_rc:
            result_view = result_view[result_view["SITUAÇÃO DE RISCO"].isin(sit_filter_rc)]
        if causa_filter_rc:
            result_view = result_view[result_view["CAUSA"].isin(causa_filter_rc)]

        st.markdown(f"**{len(result_view)}** divergência(s) exibidas")
        render_aggrid(result_view.reset_index(drop=True), key="risk_cause", height=500)
        st.download_button(
            "📥 Exportar Resultado",
            data=to_excel_bytes(result_view.reset_index(drop=True)),
            file_name="Controles_Risco_Causa.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_risk_cause",
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Controles por Risco Completo
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🔗 Análise: Controles por Risco Completo":
    st.markdown("## 🔗 Medidas de Controle por Risco Completo")
    st.markdown(
        "Verifica se linhas com mesmo conjunto completo de risco "
        "(**SITUAÇÃO + CAUSA + CONSEQUÊNCIA + PROBABILIDADE + SEVERIDADE + RISCO**) "
        "possuem **MEDIDAS DE CONTROLE diferentes**, mostrando as divergências."
    )

    with st.spinner("Analisando..."):
        result = check_full_risk_controls(df)

    if result.empty:
        st.success("✅ Todas as combinações de risco completo possuem medidas consistentes!")
    else:
        st.warning(f"⚠️ {len(result)} combinação(ões) de risco com medidas DIFERENTES")

        # Filtros
        with st.expander("🔍 Filtros", expanded=True):
            fc_a, fc_b = st.columns(2)
            with fc_a:
                sit_opts_fr = sorted(result["SITUAÇÃO DE RISCO"].dropna().unique()) if "SITUAÇÃO DE RISCO" in result.columns else []
                sit_filter_fr = st.multiselect("SITUAÇÃO DE RISCO", options=sit_opts_fr, default=[], key="fr_sit")
            with fc_b:
                causa_opts_fr = sorted(result["CAUSA"].dropna().unique()) if "CAUSA" in result.columns else []
                causa_filter_fr = st.multiselect("CAUSA", options=causa_opts_fr, default=[], key="fr_causa")

        result_view = result.copy()
        if sit_filter_fr:
            result_view = result_view[result_view["SITUAÇÃO DE RISCO"].isin(sit_filter_fr)]
        if causa_filter_fr:
            result_view = result_view[result_view["CAUSA"].isin(causa_filter_fr)]

        st.markdown(f"**{len(result_view)}** divergência(s) exibidas")
        render_aggrid(result_view.reset_index(drop=True), key="full_risk", height=500)
        st.download_button(
            "📥 Exportar Resultado",
            data=to_excel_bytes(result_view.reset_index(drop=True)),
            file_name="Controles_Risco_Completo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_full_risk",
        )

        # Detalhe de uma divergência selecionada
        if len(result_view) > 0:
            st.markdown("### 🔎 Detalhar Divergência")
            sel_idx = st.selectbox(
                "Selecione uma combinação para ver as medidas diferentes:",
                options=range(len(result_view)),
                format_func=lambda i: f"{result_view.iloc[i]['SITUAÇÃO DE RISCO']} | {result_view.iloc[i]['CAUSA']}",
            )
            sel_row = result_view.iloc[sel_idx]
            medidas = sel_row.get("Medidas Encontradas", "")
            if medidas:
                st.markdown("**Medidas de Controle encontradas para esta combinação:**")
                for j, m in enumerate(medidas.split("\n---\n"), 1):
                    st.markdown(f"> **Medida {j}:** {m.strip()}")
            st.markdown(f"**IDs ART envolvidos:** {sel_row.get('IDs ART envolvidos', '')}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Riscos Constantes
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🔁 Análise: Riscos Constantes":
    st.markdown("## 🔁 Riscos Constantes da Tarefa")
    st.markdown(
        "Identifica combinações de risco que se repetem em **todos os ITEMs** "
        "de um mesmo ID ART, sugerindo que são riscos inerentes à tarefa inteira."
    )

    with st.spinner("Analisando..."):
        result = find_constant_risks(df)

    if result.empty:
        st.info("ℹ️ Nenhum risco constante identificado (presente em todos os passos).")
    else:
        st.success(f"🔁 {len(result)} risco(s) constante(s) identificado(s)")

        # Filtros
        with st.expander("🔍 Filtros", expanded=True):
            fc_cr1, fc_cr2, fc_cr3 = st.columns(3)
            with fc_cr1:
                id_opts_cr = sorted(result["ID ART"].dropna().unique())
                id_filter_cr = st.multiselect("ID ART", options=id_opts_cr, default=[], key="cr_id")
            with fc_cr2:
                risco_opts_cr = sorted(result["SITUAÇÃO DE RISCO"].dropna().unique()) if "SITUAÇÃO DE RISCO" in result.columns else []
                risco_filter_cr = st.multiselect("RISCO RESIDUAL (PRIORIDADE)", options=sorted(result["RISCO RESIDUAL (PRIORIDADE)"].dropna().unique()) if "RISCO RESIDUAL (PRIORIDADE)" in result.columns else [], default=[], key="cr_risco")
            with fc_cr3:
                tarefa_opts_cr = sorted(result["TAREFA"].dropna().unique()) if "TAREFA" in result.columns else []
                tarefa_filter_cr = st.multiselect("TAREFA", options=tarefa_opts_cr, default=[], key="cr_tarefa")

        result_view = result.copy()
        if id_filter_cr:
            result_view = result_view[result_view["ID ART"].isin(id_filter_cr)]
        if risco_filter_cr:
            result_view = result_view[result_view["RISCO RESIDUAL (PRIORIDADE)"].isin(risco_filter_cr)]
        if tarefa_filter_cr:
            result_view = result_view[result_view["TAREFA"].isin(tarefa_filter_cr)]

        st.markdown(f"**{len(result_view)}** risco(s) exibido(s)")
        render_aggrid(result_view.reset_index(drop=True), key="const_risk", height=500)
        st.download_button(
            "📥 Exportar Resultado",
            data=to_excel_bytes(result_view.reset_index(drop=True)),
            file_name="Riscos_Constantes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_const_risk",
        )

        # Sugestão
        st.info(
            "💡 **Sugestão:** Riscos constantes podem ser consolidados no início "
            "da ART como riscos gerais da atividade, evitando repetição em cada passo."
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Constantes Completos (Risco + Causa + Medida de Controle)
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🔂 Análise: Constantes Completos":
    st.markdown("## 🔂 Risco + Causa + Controle Constantes")
    st.markdown(
        "Identifica combinações de **SITUAÇÃO DE RISCO + CAUSA + MEDIDA DE CONTROLE** "
        "que se repetem em **todos os ITEMs** de um mesmo ID ART. "
        "Quando os três elementos são idênticos em cada passo, é um forte indicativo "
        "de que o risco pode ser tratado de forma consolidada para a tarefa inteira."
    )

    with st.spinner("Analisando..."):
        result = find_constant_risk_cause_controls(df)

    if result.empty:
        st.info("ℹ️ Nenhuma combinação Risco+Causa+Controle constante identificada.")
    else:
        st.success(f"🔂 {len(result)} combinação(ões) constante(s) identificada(s)")

        # Filtros
        with st.expander("🔍 Filtros", expanded=True):
            fc_cc1, fc_cc2, fc_cc3 = st.columns(3)
            with fc_cc1:
                id_filter_cc = st.multiselect(
                    "ID ART",
                    options=sorted(result["ID ART"].dropna().unique()),
                    default=[],
                    key="cc_id",
                )
            with fc_cc2:
                tarefa_filter_cc = st.multiselect(
                    "TAREFA",
                    options=sorted(result["TAREFA"].dropna().unique()) if "TAREFA" in result.columns else [],
                    default=[],
                    key="cc_tarefa",
                )
            with fc_cc3:
                sit_filter_cc = st.multiselect(
                    "SITUAÇÃO DE RISCO",
                    options=sorted(result["SITUAÇÃO DE RISCO"].dropna().unique()) if "SITUAÇÃO DE RISCO" in result.columns else [],
                    default=[],
                    key="cc_sit",
                )

        result_view = result.copy()
        if id_filter_cc:
            result_view = result_view[result_view["ID ART"].isin(id_filter_cc)]
        if tarefa_filter_cc:
            result_view = result_view[result_view["TAREFA"].isin(tarefa_filter_cc)]
        if sit_filter_cc:
            result_view = result_view[result_view["SITUAÇÃO DE RISCO"].isin(sit_filter_cc)]

        st.markdown(f"**{len(result_view)}** combinação(ões) exibida(s)")
        render_aggrid(result_view.reset_index(drop=True), key="const_complete", height=500)
        st.download_button(
            "📥 Exportar Resultado",
            data=to_excel_bytes(result_view.reset_index(drop=True)),
            file_name="Constantes_Completos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_const_complete",
        )

        st.info(
            "💡 **Sugestão:** Quando risco, causa e medida de controle são idênticos em todos os "
            "passos de uma tarefa, considere consolidá-los como um único item no cabeçalho da ART, "
            "eliminando a repetição em cada ITEM."
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Linhas Divergentes por ID (SITUAÇÃO + CAUSA + MEDIDA)
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "⚖️ Análise: Linhas Divergentes por ID":
    st.markdown("## ⚖️ Linhas Divergentes entre dois IDs ART")
    st.markdown(
        "Selecione **dois IDs ART** para comparar. A análise mostra quais "
        "combinações de **SITUAÇÃO DE RISCO + CAUSA + MEDIDA DE CONTROLE** "
        "existem em um ID mas não no outro, com os respectivos números de linha."
    )

    # ---------- Seleção dos dois IDs ----------
    all_ids_sorted = sorted(df["ID ART"].unique(), key=lambda x: str(x))
    col_sel_a, col_sel_b = st.columns(2)
    with col_sel_a:
        id_a_sel = st.selectbox("ID ART (A)", options=[""] + all_ids_sorted, index=0, key="div_sel_a")
    with col_sel_b:
        id_b_sel = st.selectbox("ID ART (B)", options=[""] + all_ids_sorted, index=0, key="div_sel_b")

    if not id_a_sel or not id_b_sel:
        st.info("👆 Selecione os dois IDs acima para iniciar a comparação.")
    elif id_a_sel == id_b_sel:
        st.warning("⚠️ Selecione dois IDs **diferentes**.")
    else:
        # Filtra o dataframe apenas para os dois IDs selecionados
        df_pair = df[df["ID ART"].isin([id_a_sel, id_b_sel])]

        with st.spinner("Comparando..."):
            summary_div, details_div = compare_art_risk_lines(df_pair)

        if summary_div.empty:
            st.success(
                f"✅ Os IDs **{id_a_sel}** e **{id_b_sel}** possuem exatamente "
                "as mesmas combinações Situação + Causa + Medida de Controle!"
            )
        else:
            row = summary_div.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Combinações Comuns", int(row["Combinações Comuns"]))
            c2.metric(f"Só em {id_a_sel}", int(row["Só em A"]))
            c3.metric(f"Só em {id_b_sel}", int(row["Só em B"]))

            st.markdown("---")

            # ---------- Resumo ----------
            st.markdown("### Resumo do Par")
            render_aggrid(summary_div.reset_index(drop=True), key="div_summary", height=120, fit_columns=True)
            st.download_button(
                "📥 Exportar Resumo",
                data=to_excel_bytes(summary_div.reset_index(drop=True)),
                file_name=f"Divergentes_{id_a_sel}_x_{id_b_sel}_Resumo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="exp_div_summary",
            )

            # ---------- Detalhe ----------
            if not details_div.empty:
                st.markdown("---")
                st.markdown("### Detalhe das Linhas Exclusivas")

                # Filtro por lado (A ou B)
                lados = sorted(details_div["Pertence a"].unique())
                lado_filter = st.multiselect(
                    "Filtrar por lado",
                    options=lados,
                    default=[],
                    key="div_lado",
                )
                details_view = details_div.copy()
                if lado_filter:
                    details_view = details_view[details_view["Pertence a"].isin(lado_filter)]

                st.markdown(f"**{len(details_view)}** linha(s) exclusiva(s)")
                render_aggrid(details_view.reset_index(drop=True), key="div_detail", height=500)
                st.download_button(
                    "📥 Exportar Detalhe",
                    data=to_excel_bytes(details_view.reset_index(drop=True)),
                    file_name=f"Divergentes_{id_a_sel}_x_{id_b_sel}_Detalhe.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="exp_div_detail",
                )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Títulos Divergentes
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📌 Análise: Títulos Divergentes":
    st.markdown("## 📌 Títulos Divergentes no Mesmo ID")
    st.markdown(
        "Verifica se um mesmo **ID ART** possui valores diferentes "
        "na coluna **TITULO DA ART**."
    )

    with st.spinner("Analisando..."):
        result = check_title_consistency(df)

    if result.empty:
        st.success("✅ Todos os IDs possuem título único!")
    else:
        st.warning(f"⚠️ {len(result)} ID(s) com títulos divergentes")
        render_aggrid(result, key="title_div", height=400, fit_columns=True)
        st.download_button(
            "📥 Exportar Resultado",
            data=to_excel_bytes(result),
            file_name="Titulos_Divergentes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_title_div",
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE: Campos Vazios
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "❓ Análise: Campos Vazios":
    st.markdown("## ❓ Campos Vazios em Colunas Críticas")
    st.markdown(
        "Identifica linhas com campos em branco nas colunas críticas de risco."
    )

    with st.spinner("Analisando..."):
        result = check_missing_fields(df)

    if result.empty:
        st.success("✅ Nenhum campo vazio encontrado nas colunas críticas!")
    else:
        st.warning(f"⚠️ {len(result)} linha(s) com campos vazios")
        render_aggrid(result, key="missing", height=500)
        st.download_button(
            "📥 Exportar Resultado",
            data=to_excel_bytes(result),
            file_name="Campos_Vazios.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="exp_missing",
        )

        # Resumo por coluna
        st.markdown("### Resumo por Coluna")
        if "Campos Vazios" in result.columns:
            all_fields = " | ".join(result["Campos Vazios"].tolist())
            field_counts = pd.Series(all_fields.split(" | ")).value_counts()
            st.bar_chart(field_counts)
