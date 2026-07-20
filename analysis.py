"""
Módulo de análise de dados ART.
Contém todas as funções de checagem e identificação de oportunidades de melhoria.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from itertools import combinations


# ── Colunas relevantes ──────────────────────────────────────────────────────────
KEY_COLS = [
    "Nº Linha", "ID ART", "TITULO DA ART", "TAREFA", "PASSO DA TAREFA", "ITEM",
    "NOME DO PASSO", "SITUAÇÃO DE RISCO", "CAUSA", "CONSEQUÊNCIA",
    "PROBABILIDADE RESIDUAL", "SEVERIDADE RESIDUAL",
    "RISCO RESIDUAL (PRIORIDADE)", "MEDIDA DE CONTROLE",
]

RISK_COLS = [
    "SITUAÇÃO DE RISCO", "CAUSA", "CONSEQUÊNCIA",
    "PROBABILIDADE RESIDUAL", "SEVERIDADE RESIDUAL",
    "RISCO RESIDUAL (PRIORIDADE)",
]

# Valores válidos de PROBABILIDADE (inclui "NA" que é um valor real, não nulo)
VALID_PROB = {"MUITO REMOTO", "REMOTO", "NA", "POSSÍVEL", "PROVÁVEL", "MUITO PROVÁVEL"}

# Matriz de risco esperada: (PROBABILIDADE, SEVERIDADE) → RISCO
RISK_MATRIX: Dict[Tuple[str, str], str] = {
    ("MUITO REMOTO", "LEVE"): "NA",
    ("MUITO REMOTO", "MODERADO"): "NA",
    ("MUITO REMOTO", "SIGNIFICATIVO"): "MÉDIA",
    ("MUITO REMOTO", "CRÍTICO"): "ALTA",
    ("REMOTO", "LEVE"): "NA",
    ("REMOTO", "MODERADO"): "NA",
    ("REMOTO", "SIGNIFICATIVO"): "MÉDIA",
    ("REMOTO", "CRÍTICO"): "ALTA",
    ("NA", "LEVE"): "BAIXA",
    ("NA", "MODERADO"): "MÉDIA",
    ("NA", "SIGNIFICATIVO"): "NA",
    ("NA", "CRÍTICO"): "NA",
    ("POSSÍVEL", "LEVE"): "NA",
    ("POSSÍVEL", "MODERADO"): "NA",
    ("POSSÍVEL", "SIGNIFICATIVO"): "ALTA",
    ("POSSÍVEL", "CRÍTICO"): "ALTA",
    ("PROVÁVEL", "LEVE"): "NA",
    ("PROVÁVEL", "MODERADO"): "NA",
    ("PROVÁVEL", "SIGNIFICATIVO"): "ALTA",
    ("PROVÁVEL", "CRÍTICO"): "MUITO ALTA",
    ("MUITO PROVÁVEL", "LEVE"): "NA",
    ("MUITO PROVÁVEL", "MODERADO"): "NA",
    ("MUITO PROVÁVEL", "SIGNIFICATIVO"): "MUITO ALTA",
    ("MUITO PROVÁVEL", "CRÍTICO"): "MUITO ALTA",
}


def _normalize(val: Optional[str]) -> str:
    """Normaliza string para comparações: strip, upper, remove espaços duplos."""
    if pd.isna(val) or val is None:
        return ""
    return " ".join(str(val).strip().upper().split())


def _normalize_series(s: pd.Series) -> pd.Series:
    """Normaliza uma série inteira."""
    return s.fillna("").astype(str).str.strip().str.upper().str.replace(r"\s+", " ", regex=True)


def load_excel_safe(file) -> pd.DataFrame:
    """
    Carrega Excel preservando o valor textual "NA" (que pandas converte em NaN).
    """
    return pd.read_excel(
        file, engine="openpyxl",
        keep_default_na=False,   # impede que "NA" vire NaN
        na_values=[""],          # apenas strings vazias são NaN
    )


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove linhas de resumo/totais e normaliza textos das colunas CAUSA e CONSEQUÊNCIA.
    """
    # Remove linhas onde ID ART não é numérico (Total, filtros, etc.)
    df = df.copy()
    df["ID ART"] = pd.to_numeric(df["ID ART"], errors="coerce")
    df = df.dropna(subset=["ID ART"])
    df["ID ART"] = df["ID ART"].astype(int)

    # Adicionar Nº da linha no Excel (header=1, dados a partir da linha 2)
    # Se já existe (arquivo re-importado após exportação), preservar os valores originais
    if "Nº Linha" not in df.columns:
        df["Nº Linha"] = df.index + 2

    # Normaliza CAUSA e CONSEQUÊNCIA → Primeira letra maiúscula de cada frase
    for col in ["CAUSA", "CONSEQUÊNCIA"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.capitalize()
            )

    # Reordenar para que Nº Linha seja a primeira coluna
    cols = ["Nº Linha"] + [c for c in df.columns if c != "Nº Linha"]
    df = df[cols]

    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 1 – Validação da classificação de risco
# ═══════════════════════════════════════════════════════════════════════════════

def check_risk_classification(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica se RISCO RESIDUAL (PRIORIDADE) está coerente com PROBABILIDADE × SEVERIDADE
    conforme a matriz de risco padrão.
    Retorna DataFrame com as linhas divergentes e a classificação esperada.
    """
    results = []
    for idx, row in df.iterrows():
        prob = _normalize(row.get("PROBABILIDADE RESIDUAL"))
        sev = _normalize(row.get("SEVERIDADE RESIDUAL"))
        risco = _normalize(row.get("RISCO RESIDUAL (PRIORIDADE)"))

        if not prob or not sev or not risco:
            continue

        expected = RISK_MATRIX.get((prob, sev))
        if expected and expected != risco:
            results.append({
                "Nº Linha": row.get("Nº Linha", idx + 2),
                "ID ART": row.get("ID ART"),
                "TAREFA": row.get("TAREFA"),
                "PASSO DA TAREFA": row.get("PASSO DA TAREFA"),
                "SITUAÇÃO DE RISCO": row.get("SITUAÇÃO DE RISCO"),
                "PROBABILIDADE RESIDUAL": row.get("PROBABILIDADE RESIDUAL"),
                "SEVERIDADE RESIDUAL": row.get("SEVERIDADE RESIDUAL"),
                "RISCO ATUAL": row.get("RISCO RESIDUAL (PRIORIDADE)"),
                "RISCO ESPERADO": expected,
            })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 2 – ARTs duplicadas (completamente idênticas)
# ═══════════════════════════════════════════════════════════════════════════════

def find_duplicate_arts(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Identifica ID ARTs com dados completamente idênticos.
    Retorna (grupos_duplicados, dataframe_com_linhas_duplicadas).
    """
    compare_cols = [c for c in KEY_COLS if c != "ID ART" and c in df.columns]

    # Agrupa por ID ART e cria assinatura
    art_groups = {}
    for id_art, group in df.groupby("ID ART"):
        # Normaliza e ordena para comparação
        subset = group[compare_cols].copy()
        for col in subset.columns:
            subset[col] = _normalize_series(subset[col])
        # Cria uma assinatura canônica (ordena as linhas para comparação)
        sorted_vals = subset.sort_values(by=compare_cols).reset_index(drop=True)
        signature = sorted_vals.to_json()
        art_groups[id_art] = signature

    # Encontra IDs com assinaturas idênticas
    sig_to_ids: Dict[str, List[int]] = {}
    for id_art, sig in art_groups.items():
        sig_to_ids.setdefault(sig, []).append(id_art)

    duplicates = {k: v for k, v in sig_to_ids.items() if len(v) > 1}

    # Retorna grupos (com todos os IDs de cada grupo) em vez de apenas pares
    groups = []
    dup_ids = set()
    for group_idx, (sig, ids) in enumerate(duplicates.items(), 1):
        for id_art in ids:
            groups.append({
                "Grupo": group_idx,
                "ID ART": id_art,
                "Qtd IDs no Grupo": len(ids),
                "Todos IDs do Grupo": " | ".join(str(x) for x in ids),
            })
            dup_ids.add(id_art)

    groups_df = pd.DataFrame(groups) if groups else pd.DataFrame(
        columns=["Grupo", "ID ART", "Qtd IDs no Grupo", "Todos IDs do Grupo"]
    )
    dup_rows = df[df["ID ART"].isin(dup_ids)] if dup_ids else pd.DataFrame(columns=df.columns)

    return groups_df, dup_rows


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 2c – ARTs idênticas em SITUAÇÃO + CAUSA + MEDIDA DE CONTROLE
# ═══════════════════════════════════════════════════════════════════════════════

def find_duplicate_arts_trio(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Identifica ID ARTs cujo conjunto de (SITUAÇÃO DE RISCO, CAUSA, MEDIDA DE
    CONTROLE) – normalizado e ordenado – é idêntico.
    Retorna (grupos_duplicados, dataframe_com_linhas_duplicadas).
    """
    trio_cols = ["SITUAÇÃO DE RISCO", "CAUSA", "MEDIDA DE CONTROLE"]
    available = [c for c in trio_cols if c in df.columns]
    if len(available) < 3:
        empty_groups = pd.DataFrame(
            columns=["Grupo", "ID ART", "Qtd IDs no Grupo", "Todos IDs do Grupo"]
        )
        return empty_groups, pd.DataFrame(columns=df.columns)

    art_groups: Dict[int, str] = {}
    for id_art, group in df.groupby("ID ART"):
        subset = group[trio_cols].copy()
        for col in trio_cols:
            subset[col] = _normalize_series(subset[col])
        sorted_vals = subset.sort_values(by=trio_cols).reset_index(drop=True)
        art_groups[id_art] = sorted_vals.to_json()

    sig_to_ids: Dict[str, List[int]] = {}
    for id_art, sig in art_groups.items():
        sig_to_ids.setdefault(sig, []).append(id_art)

    duplicates = {k: v for k, v in sig_to_ids.items() if len(v) > 1}

    groups = []
    dup_ids = set()
    for group_idx, (sig, ids) in enumerate(duplicates.items(), 1):
        for id_art in ids:
            groups.append({
                "Grupo": group_idx,
                "ID ART": id_art,
                "Qtd IDs no Grupo": len(ids),
                "Todos IDs do Grupo": " | ".join(str(x) for x in ids),
            })
            dup_ids.add(id_art)

    groups_df = pd.DataFrame(groups) if groups else pd.DataFrame(
        columns=["Grupo", "ID ART", "Qtd IDs no Grupo", "Todos IDs do Grupo"]
    )
    dup_rows = df[df["ID ART"].isin(dup_ids)] if dup_ids else pd.DataFrame(columns=df.columns)
    return groups_df, dup_rows


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 2b – ARTs quase idênticas (alta similaridade, IDs distintos)
# ═══════════════════════════════════════════════════════════════════════════════

def find_near_duplicate_arts(
    df: pd.DataFrame,
    threshold: float = 0.8,
    exact_ids: Optional[set] = None,
) -> pd.DataFrame:
    """
    Compara pares de ID ART e calcula a similaridade (Jaccard) das linhas
    normalizadas.  Retorna apenas pares com similaridade >= *threshold*
    que NÃO sejam 100 % idênticos (esses já são tratados por
    ``find_duplicate_arts``).

    Parameters
    ----------
    df : DataFrame com os dados das ARTs.
    threshold : similaridade mínima (0-1) para considerar "quase idêntica".
    exact_ids : conjunto de pares (frozenset) já identificados como 100 %
        idênticos, a serem excluídos do resultado.
    """
    compare_cols = [c for c in KEY_COLS
                    if c not in ("ID ART", "Nº Linha", "TITULO DA ART")
                    and c in df.columns]
    if not compare_cols:
        return pd.DataFrame()

    # Cria assinatura de linhas por ID ART
    art_sigs: Dict[int, set] = {}
    art_titles: Dict[int, str] = {}
    art_row_linhas: Dict[int, Dict[tuple, list]] = {}   # id_art -> {row_tuple: [Nº Linha, ...]}
    has_linha = "Nº Linha" in df.columns
    for id_art, group in df.groupby("ID ART"):
        subset = group[compare_cols].copy()
        for col in subset.columns:
            subset[col] = _normalize_series(subset[col])
        row_tuples = subset.sort_values(by=compare_cols).apply(tuple, axis=1)
        art_sigs[id_art] = set(row_tuples)
        art_titles[id_art] = group["TITULO DA ART"].iloc[0] if "TITULO DA ART" in group.columns else ""
        # Mapear tupla -> lista de Nº Linha
        if has_linha:
            mapping: Dict[tuple, list] = {}
            for idx_row, tup in zip(group.index, row_tuples):
                mapping.setdefault(tup, []).append(group.at[idx_row, "Nº Linha"])
            art_row_linhas[id_art] = mapping

    if exact_ids is None:
        exact_ids = set()

    ids = list(art_sigs.keys())
    results = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            id_a, id_b = ids[i], ids[j]
            # Pular pares já marcados como 100 % idênticos
            if frozenset([id_a, id_b]) in exact_ids:
                continue
            set_a, set_b = art_sigs[id_a], art_sigs[id_b]
            inter = len(set_a & set_b)
            union = len(set_a | set_b)
            if union == 0:
                continue
            sim = inter / union
            if sim >= threshold and sim < 1.0:
                # Descobre colunas divergentes
                only_a = set_a - set_b
                only_b = set_b - set_a
                diff_cols = []
                for idx_c, col in enumerate(compare_cols):
                    vals_a = {row[idx_c] for row in only_a}
                    vals_b = {row[idx_c] for row in only_b}
                    if vals_a != vals_b:
                        diff_cols.append(col)

                # Coletar Nº Linha das linhas exclusivas de cada ART
                linhas_a = []
                linhas_b = []
                if has_linha:
                    map_a = art_row_linhas.get(id_a, {})
                    map_b = art_row_linhas.get(id_b, {})
                    for tup in only_a:
                        linhas_a.extend(map_a.get(tup, []))
                    for tup in only_b:
                        linhas_b.extend(map_b.get(tup, []))
                    linhas_a = sorted(linhas_a)
                    linhas_b = sorted(linhas_b)

                results.append({
                    "ID ART (A)": id_a,
                    "Título (A)": art_titles[id_a],
                    "ID ART (B)": id_b,
                    "Título (B)": art_titles[id_b],
                    "Similaridade": f"{sim:.0%}",
                    "Linhas Comuns": inter,
                    "Linhas Só em A": len(only_a),
                    "Nº Linhas Só A": ", ".join(str(x) for x in linhas_a) if linhas_a else "",
                    "Linhas Só em B": len(only_b),
                    "Nº Linhas Só B": ", ".join(str(x) for x in linhas_b) if linhas_b else "",
                    "Colunas Divergentes": " | ".join(diff_cols) if diff_cols else "(só qtd linhas)",
                })

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        # Ordenar pela maior similaridade
        result_df["_sim_val"] = result_df["Similaridade"].str.rstrip("%").astype(float)
        result_df = result_df.sort_values("_sim_val", ascending=False).drop(columns="_sim_val").reset_index(drop=True)
    return result_df


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 3 – Diferenças entre IDs similares (não 100% idênticos)
# ═══════════════════════════════════════════════════════════════════════════════

def find_similar_art_differences(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para IDs com mesmo TITULO DA ART mas IDs diferentes, mostra quais colunas diferem.
    """
    compare_cols = [c for c in KEY_COLS if c not in ("ID ART", "TITULO DA ART") and c in df.columns]

    results = []
    title_groups = df.groupby("TITULO DA ART")

    for titulo, group in title_groups:
        ids = group["ID ART"].unique()
        if len(ids) < 2:
            continue

        for id_a, id_b in combinations(ids, 2):
            rows_a = group[group["ID ART"] == id_a][compare_cols].copy()
            rows_b = group[group["ID ART"] == id_b][compare_cols].copy()

            for col in compare_cols:
                rows_a[col] = _normalize_series(rows_a[col])
                rows_b[col] = _normalize_series(rows_b[col])

            vals_a = set(rows_a.sort_values(by=compare_cols).apply(tuple, axis=1))
            vals_b = set(rows_b.sort_values(by=compare_cols).apply(tuple, axis=1))

            if vals_a != vals_b:
                # Identifica colunas com diferenças
                diff_cols = []
                for col in compare_cols:
                    set_a = set(rows_a[col].values)
                    set_b = set(rows_b[col].values)
                    if set_a != set_b:
                        diff_cols.append(col)

                results.append({
                    "TITULO DA ART": titulo,
                    "ID ART (A)": id_a,
                    "ID ART (B)": id_b,
                    "Qtd Linhas (A)": len(rows_a),
                    "Qtd Linhas (B)": len(rows_b),
                    "Colunas Divergentes": " | ".join(diff_cols),
                })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 4 – TAREFA com ITEM / PASSO DA TAREFA inconsistentes no mesmo passo
# ═══════════════════════════════════════════════════════════════════════════════

def check_task_step_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica se no mesmo NOME DO PASSO de uma TAREFA existem
    valores diferentes de ITEM ou PASSO DA TAREFA.
    """
    results = []
    grouped = df.groupby(["ID ART", "TAREFA", "NOME DO PASSO"])

    for (id_art, tarefa, passo), group in grouped:
        items = group["ITEM"].dropna().unique()
        passos = group["PASSO DA TAREFA"].dropna().unique()

        if len(items) > 1 or len(passos) > 1:
            linhas = sorted(group["Nº Linha"].tolist()) if "Nº Linha" in group.columns else []
            results.append({
                "ID ART": id_art,
                "TAREFA": tarefa,
                "PASSO DA TAREFA": passo,
                "ITEMs encontrados": " | ".join(str(x) for x in sorted(items)),
                "PASSOSs encontrados": " | ".join(str(x) for x in sorted(passos)),
                "Qtd Linhas": len(group),
                "Nº Linhas": ", ".join(str(x) for x in linhas),
            })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 5 – Mesma SITUAÇÃO + CAUSA → mesma MEDIDA DE CONTROLE?
# ═══════════════════════════════════════════════════════════════════════════════

def check_risk_cause_controls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica se linhas com mesma SITUAÇÃO DE RISCO e CAUSA possuem
    a mesma MEDIDA DE CONTROLE.
    """
    work = df.copy()
    for col in ["SITUAÇÃO DE RISCO", "CAUSA", "MEDIDA DE CONTROLE"]:
        work[f"_norm_{col}"] = _normalize_series(work[col])

    results = []
    grouped = work.groupby(["_norm_SITUAÇÃO DE RISCO", "_norm_CAUSA"])

    for (sit, causa), group in grouped:
        if not sit or not causa:
            continue
        controls = group["_norm_MEDIDA DE CONTROLE"].unique()
        if len(controls) > 1:
            ids = group["ID ART"].unique()
            # Coletar títulos únicos das ARTs envolvidas
            titulos = group.drop_duplicates(subset=["ID ART"])
            if "TITULO DA ART" in titulos.columns:
                titulos_list = titulos.set_index("ID ART")["TITULO DA ART"].to_dict()
                titulos_str = " | ".join(f"{k}: {v}" for k, v in titulos_list.items())
            else:
                titulos_str = ""
            results.append({
                "SITUAÇÃO DE RISCO": sit,
                "CAUSA": causa,
                "Qtd Medidas Diferentes": len(controls),
                "IDs ART envolvidos": " | ".join(str(x) for x in ids),
                "Nº Linhas": ", ".join(str(x) for x in sorted(group["Nº Linha"].tolist())) if "Nº Linha" in group.columns else "",
                "Títulos das ARTs": titulos_str,
                "Medidas Encontradas": "\n---\n".join(
                    group.drop_duplicates(subset=["_norm_MEDIDA DE CONTROLE"])["MEDIDA DE CONTROLE"].tolist()
                ),
            })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 6 – Mesmo risco completo → mesma MEDIDA DE CONTROLE?
# ═══════════════════════════════════════════════════════════════════════════════

def check_full_risk_controls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica se linhas com mesmo conjunto completo de risco
    (SITUAÇÃO + CAUSA + CONSEQUÊNCIA + PROB + SEV + RISCO) possuem mesma MEDIDA DE CONTROLE.
    """
    work = df.copy()
    norm_cols = RISK_COLS + ["MEDIDA DE CONTROLE"]
    for col in norm_cols:
        work[f"_norm_{col}"] = _normalize_series(work[col])

    group_keys = [f"_norm_{c}" for c in RISK_COLS]
    results = []
    grouped = work.groupby(group_keys)

    for keys, group in grouped:
        key_dict = dict(zip(RISK_COLS, keys))
        if not all(key_dict.values()):
            continue

        controls = group["_norm_MEDIDA DE CONTROLE"].unique()
        if len(controls) > 1:
            ids = group["ID ART"].unique()
            results.append({
                **key_dict,
                "Qtd Medidas Diferentes": len(controls),
                "IDs ART envolvidos": " | ".join(str(x) for x in ids),
                "Nº Linhas": ", ".join(str(x) for x in sorted(group["Nº Linha"].tolist())) if "Nº Linha" in group.columns else "",
                "Medidas Encontradas": "\n---\n".join(
                    group.drop_duplicates(subset=["_norm_MEDIDA DE CONTROLE"])["MEDIDA DE CONTROLE"].tolist()
                ),
            })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 7 – Risco + Causa + Medida de Controle constantes em todos os ITEMs
# ═══════════════════════════════════════════════════════════════════════════════

def find_constant_risk_cause_controls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifica combinações de SITUAÇÃO DE RISCO + CAUSA + MEDIDA DE CONTROLE
    que se repetem em TODOS os ITEMs de um mesmo ID ART,
    indicando que não apenas o risco mas também a causa e a medida são iguais
    em todos os passos – forte candidato a consolidação.
    """
    work = df.copy()
    group_cols = ["SITUAÇÃO DE RISCO", "CAUSA", "MEDIDA DE CONTROLE"]
    available = [c for c in group_cols if c in work.columns]
    if not available:
        return pd.DataFrame()

    norm_keys = [f"_norm_{c}" for c in available]
    for col in available:
        work[f"_norm_{col}"] = _normalize_series(work[col])

    results = []
    for id_art, art_group in work.groupby("ID ART"):
        all_items = art_group["ITEM"].dropna().unique()
        if len(all_items) < 2:
            continue

        for keys, risk_group in art_group.groupby(norm_keys):
            keys_tuple = keys if isinstance(keys, tuple) else (keys,)
            key_dict = dict(zip(available, keys_tuple))
            if not all(key_dict.values()):
                continue

            items_with_risk = risk_group["ITEM"].dropna().unique()
            if len(items_with_risk) == len(all_items) and len(items_with_risk) > 1:
                linhas = sorted(risk_group["Nº Linha"].tolist()) if "Nº Linha" in risk_group.columns else []
                results.append({
                    "ID ART": id_art,
                    "TAREFA": risk_group["TAREFA"].iloc[0],
                    "SITUAÇÃO DE RISCO": key_dict.get("SITUAÇÃO DE RISCO", ""),
                    "CAUSA": key_dict.get("CAUSA", ""),
                    "MEDIDA DE CONTROLE": key_dict.get("MEDIDA DE CONTROLE", ""),
                    "Qtd ITEMs": len(all_items),
                    "Nº Linhas": ", ".join(str(x) for x in linhas),
                    "Constante?": "SIM",
                })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 10 – Linhas divergentes entre IDs (SITUAÇÃO + CAUSA + MEDIDA)
# ═══════════════════════════════════════════════════════════════════════════════

def compare_art_risk_lines(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Para cada par de ID ART, compara os conjuntos de
    (SITUAÇÃO DE RISCO, CAUSA, MEDIDA DE CONTROLE) e lista as linhas
    cuja combinação existe em um ID mas não no outro.

    Retorna
    -------
    summary : DataFrame  – Um registro por par, com contagens e visão geral.
    details : DataFrame  – Uma linha por registro exclusivo, indicando a qual
              ID pertence e o Nº Linha original.
    """
    trio_cols = ["SITUAÇÃO DE RISCO", "CAUSA", "MEDIDA DE CONTROLE"]
    available = [c for c in trio_cols if c in df.columns]
    if len(available) < 3:
        return pd.DataFrame(), pd.DataFrame()

    has_linha = "Nº Linha" in df.columns

    # Montar assinaturas por ID ART
    art_data: Dict[int, dict] = {}  # id -> {"title", "tuples": set, "rows": {tuple: [Nº Linha,...]}}
    for id_art, group in df.groupby("ID ART"):
        subset = group[trio_cols].copy()
        for col in trio_cols:
            subset[col] = _normalize_series(subset[col])
        tuples_series = subset.apply(tuple, axis=1)
        row_map: Dict[tuple, list] = {}  # normalized tuple -> [Nº Linha, ...]
        orig_map: Dict[tuple, list] = {}  # normalized tuple -> [original row dicts]
        for i, (idx_row, tup) in enumerate(zip(group.index, tuples_series)):
            row_map.setdefault(tup, []).append(
                group.at[idx_row, "Nº Linha"] if has_linha else idx_row + 2
            )
            orig_map.setdefault(tup, []).append({
                "SITUAÇÃO DE RISCO": group.at[idx_row, "SITUAÇÃO DE RISCO"],
                "CAUSA": group.at[idx_row, "CAUSA"],
                "MEDIDA DE CONTROLE": group.at[idx_row, "MEDIDA DE CONTROLE"],
            })
        title = group["TITULO DA ART"].iloc[0] if "TITULO DA ART" in group.columns else ""
        art_data[id_art] = {
            "title": title,
            "tuples": set(tuples_series),
            "rows": row_map,
            "orig": orig_map,
        }

    ids = list(art_data.keys())
    summary_rows = []
    detail_rows = []

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            id_a, id_b = ids[i], ids[j]
            set_a = art_data[id_a]["tuples"]
            set_b = art_data[id_b]["tuples"]
            only_a = set_a - set_b
            only_b = set_b - set_a
            common = set_a & set_b

            if not only_a and not only_b:
                continue  # pares 100% iguais nessas 3 colunas → sem interesse

            # Linhas exclusivas de A
            linhas_a = []
            for tup in only_a:
                linhas_a.extend(art_data[id_a]["rows"].get(tup, []))
            linhas_a = sorted(linhas_a)
            # Linhas exclusivas de B
            linhas_b = []
            for tup in only_b:
                linhas_b.extend(art_data[id_b]["rows"].get(tup, []))
            linhas_b = sorted(linhas_b)

            summary_rows.append({
                "ID ART (A)": id_a,
                "Título (A)": art_data[id_a]["title"],
                "ID ART (B)": id_b,
                "Título (B)": art_data[id_b]["title"],
                "Combinações Comuns": len(common),
                "Só em A": len(only_a),
                "Só em B": len(only_b),
                "Nº Linhas Só A": ", ".join(str(x) for x in linhas_a),
                "Nº Linhas Só B": ", ".join(str(x) for x in linhas_b),
            })

            # Detalhe de cada linha exclusiva
            for tup in only_a:
                for nl in art_data[id_a]["rows"].get(tup, []):
                    orig = art_data[id_a]["orig"].get(tup, [{}])[0]
                    detail_rows.append({
                        "Par": f"{id_a} × {id_b}",
                        "Pertence a": f"ID {id_a}",
                        "ID ART": id_a,
                        "Nº Linha": nl,
                        "SITUAÇÃO DE RISCO": orig.get("SITUAÇÃO DE RISCO", ""),
                        "CAUSA": orig.get("CAUSA", ""),
                        "MEDIDA DE CONTROLE": orig.get("MEDIDA DE CONTROLE", ""),
                    })
            for tup in only_b:
                for nl in art_data[id_b]["rows"].get(tup, []):
                    orig = art_data[id_b]["orig"].get(tup, [{}])[0]
                    detail_rows.append({
                        "Par": f"{id_a} × {id_b}",
                        "Pertence a": f"ID {id_b}",
                        "ID ART": id_b,
                        "Nº Linha": nl,
                        "SITUAÇÃO DE RISCO": orig.get("SITUAÇÃO DE RISCO", ""),
                        "CAUSA": orig.get("CAUSA", ""),
                        "MEDIDA DE CONTROLE": orig.get("MEDIDA DE CONTROLE", ""),
                    })

    summary = pd.DataFrame(summary_rows)
    details = pd.DataFrame(detail_rows)
    return summary, details


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 8 – Títulos divergentes no mesmo ID ART
# ═══════════════════════════════════════════════════════════════════════════════

def check_title_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Verifica se um mesmo ID ART possui TITULO DA ART diferentes.
    """
    results = []
    for id_art, group in df.groupby("ID ART"):
        titles = group["TITULO DA ART"].dropna().unique()
        if len(titles) > 1:
            results.append({
                "ID ART": id_art,
                "Qtd Títulos": len(titles),
                "Títulos": " ‖ ".join(titles),
            })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANÁLISE 9 – Campos em branco em colunas críticas
# ═══════════════════════════════════════════════════════════════════════════════

def check_missing_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifica linhas com campos em branco nas colunas críticas.
    """
    critical_cols = [
        "SITUAÇÃO DE RISCO", "CAUSA", "CONSEQUÊNCIA",
        "PROBABILIDADE RESIDUAL", "SEVERIDADE RESIDUAL",
        "RISCO RESIDUAL (PRIORIDADE)", "MEDIDA DE CONTROLE",
    ]
    available = [c for c in critical_cols if c in df.columns]

    results = []
    for idx, row in df.iterrows():
        missing = []
        for col in available:
            val = row.get(col)
            if pd.isna(val) or str(val).strip() == "":
                missing.append(col)
        if missing:
            results.append({
                "Nº Linha": row.get("Nº Linha", idx + 2),
                "ID ART": row.get("ID ART"),
                "TAREFA": row.get("TAREFA"),
                "NOME DO PASSO": row.get("NOME DO PASSO"),
                "Campos Vazios": " | ".join(missing),
            })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESUMO GERAL
# ═══════════════════════════════════════════════════════════════════════════════

def generate_summary(df: pd.DataFrame) -> Dict[str, any]:
    """Gera estatísticas resumidas do dataset."""
    return {
        "Total de Linhas": len(df),
        "IDs ART Únicos": df["ID ART"].nunique(),
        "Tarefas Únicas": df["TAREFA"].nunique() if "TAREFA" in df.columns else 0,
        "Situações de Risco Únicas": df["SITUAÇÃO DE RISCO"].nunique() if "SITUAÇÃO DE RISCO" in df.columns else 0,
        "Distribuição Risco": df["RISCO RESIDUAL (PRIORIDADE)"].value_counts().to_dict()
            if "RISCO RESIDUAL (PRIORIDADE)" in df.columns else {},
        "Distribuição Probabilidade": df["PROBABILIDADE RESIDUAL"].value_counts().to_dict()
            if "PROBABILIDADE RESIDUAL" in df.columns else {},
        "Distribuição Severidade": df["SEVERIDADE RESIDUAL"].value_counts().to_dict()
            if "SEVERIDADE RESIDUAL" in df.columns else {},
    }


def run_all_analyses(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Executa todas as análises e retorna um dicionário com os resultados."""
    return {
        "risk_classification": check_risk_classification(df),
        "duplicate_arts": find_duplicate_arts(df),
        "similar_differences": find_similar_art_differences(df),
        "task_consistency": check_task_step_consistency(df),
        "risk_cause_controls": check_risk_cause_controls(df),
        "full_risk_controls": check_full_risk_controls(df),
        "constant_risk_cause_controls": find_constant_risk_cause_controls(df),
        "title_consistency": check_title_consistency(df),
        "missing_fields": check_missing_fields(df),
    }
