# Ceres6 Report / Field Query Tool
# Converted from Streamlit to NiceGUI

from __future__ import annotations
import re
from pathlib import Path

import pandas as pd
from nicegui import ui

from fsdhelpers.config import CERES6_CSV

# ---------- Config ----------
STOPWORDS = {
    "where", "can", "i", "find", "the", "a", "an", "of", "to", "for", "in", "on", "and", "or",
    "is", "are", "do", "does", "what", "whats", "please", "me", "show", "tell"
}

ENTITY_HINTS = {
    "agency":  {"agency", "agencies"},
    "donors":  {"donor", "donors"},
    "vendors": {"vendor", "vendors", "supplier", "suppliers"},
    "items":   {"item", "items", "product", "sku"},
    "ledger":  {"gl", "g/l", "ledger", "general ledger", "journal"},
}

COL_COMMON   = "Common"
COL_KEYWORD  = "Keyword / Search Term"
COL_REPORT   = "Database/Report Location"
COL_FULLKEY  = "Full Information Key"
COL_ENTITY   = "Entity Type"
COL_CANON    = "Canonical Field"
COL_SYNONYMS = "Synonyms / Ask Phrases"

REQUIRED_COLS = [COL_COMMON, COL_KEYWORD, COL_REPORT, COL_FULLKEY, COL_ENTITY, COL_CANON, COL_SYNONYMS]


# ---------- Text utilities ----------
def normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s,/-]", " ", text)
    text = text.replace("/", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> set[str]:
    t = normalize(text)
    return {w for w in t.split() if len(w) >= 3 and w not in STOPWORDS}


def phrase_list(synonyms: str) -> list[str]:
    raw = [(synonyms or "").split(",")]
    flat = []
    for chunk in raw:
        flat.extend(chunk)
    cleaned = [normalize(p) for p in flat]
    return [p for p in cleaned if len(p) >= 3]


# ---------- Scoring ----------
def score_row(q_norm: str, q_tokens: set[str], row: pd.Series) -> tuple[int, dict]:
    common   = normalize(str(row.get(COL_COMMON, "")))
    keyword  = normalize(str(row.get(COL_KEYWORD, "")))
    report   = normalize(str(row.get(COL_REPORT, "")))
    synonyms = str(row.get(COL_SYNONYMS, ""))
    entity   = normalize(str(row.get(COL_ENTITY, "")))

    score = 0
    why = {"syn_phrase_hit": 0, "token_overlap": 0, "entity_bonus": 0}

    best_phrase = 0
    for phr in phrase_list(synonyms):
        if phr and phr in q_norm:
            best_phrase = max(best_phrase, 8 + (len(phr) // 10))
    score += best_phrase
    why["syn_phrase_hit"] = best_phrase

    row_tokens = tokenize(common) | tokenize(keyword) | tokenize(report)
    overlap = len(q_tokens & row_tokens)
    tok_pts = min(6, overlap * 2)
    score += tok_pts
    why["token_overlap"] = tok_pts

    for ent, words in ENTITY_HINTS.items():
        if any(w in q_norm for w in words):
            if ent == entity:
                score += 4
                why["entity_bonus"] = 4
            else:
                score -= 1
            break

    return score, why


# ---------- Data loading ----------
_df_cache: pd.DataFrame | None = None


def load_data() -> pd.DataFrame | None:
    global _df_cache
    if _df_cache is not None:
        return _df_cache
    try:
        df = pd.read_csv(CERES6_CSV)
        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            return None
        _df_cache = df
        return df
    except Exception:
        return None


# ---------- NiceGUI render ----------
def render():
    df = load_data()

    with ui.column().classes("w-full mx-auto px-4 py-4 gap-6"):
        # Header
        with ui.column().classes("gap-3"):
            ui.label("Ceres6 Report / Field Query").style(
                "font-size: 2.5rem; font-weight: 700; color: var(--q-primary);"
            )

            ui.label('Ask something like: "Where can I find agency delivery zone codes?"').style(
            "color: var(--q-secondary); font-size: 1.25rem; font-style: italic;")

        if df is None:
            ui.label("⚠️ Could not load Ceres6 Cheatsheet CSV. Check data path.").style(
                "color: red; font-weight: 600;"
            )
            return

        ui.separator()

        # Search controls
        results_container = ui.column().classes("w-full gap-4")

        with ui.row().classes("w-full items-end gap-4 flex-wrap"):
            question_input = ui.input(
                label="Your question",
                placeholder='e.g. "Where can I find donor contact info?"',
            ).classes("flex-1")

            top_k_select = ui.select(
                label="Results to show",
                options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                value=3,
            ).classes('entity-select')

        def do_search():
            results_container.clear()
            q = question_input.value.strip()
            if not q:
                with results_container:
                    ui.label("Please enter a question above.").style("color: var(--q-primary);")
                return

            q_norm = normalize(q)
            q_tokens = tokenize(q)
            top_k = int(top_k_select.value)

            scored = []
            for _, row in df.iterrows():
                s, why = score_row(q_norm, q_tokens, row)
                scored.append((s, why, row))

            scored.sort(key=lambda x: x[0], reverse=True)
            best = scored[:top_k]

            with results_container:
                # Best answer highlight
                best_row = best[0][2]
                with ui.card().classes("w-full").style(
                    "border-radius: 8px; border-left: 4px solid #1a7a3a; background: #f0fff4;"
                ):
                    with ui.column().classes("gap-1 p-2"):
                        ui.label("✅ Best Match").style(
                            "font-size: 0.8rem; font-weight: 700; color: #1a7a3a; text-transform: uppercase;"
                        )
                        ui.label(str(best_row[COL_COMMON])).style(
                            "font-size: 1.2rem; font-weight: 700; color: var(--q-primary);"
                        )
                        with ui.row().classes("gap-6 flex-wrap"):
                            for label, col in [
                                ("Table", COL_REPORT),
                                ("Column", COL_KEYWORD),
                                ("Key", COL_FULLKEY),
                            ]:
                                with ui.column().classes("gap-0"):
                                    ui.label(label).style(
                                        "font-size: 0.85rem; color: #666; text-transform: uppercase;"
                                    )
                                    ui.label(str(best_row[col])).style(
                                        "font-family: monospace; font-size: 1.0rem; color: var(--q-secondary);"
                                    )

                ui.separator()
                ui.label(f"Top {top_k} Matches").style(
                    "font-weight: 600; color: var(--q-primary); font-size: 1.2rem;"
                )

                for rank, (s, why, row) in enumerate(best, start=1):
                    with ui.card().classes("w-full").style("border-radius: 8px;"):
                        with ui.row().classes("items-start gap-4 p-1"):
                            ui.label(f"#{rank}").style(
                                "font-size: 1.2rem; font-weight: 700; color: #aaa; min-width: 2rem;"
                            )
                            with ui.column().classes("gap-1 flex-1"):
                                ui.label(str(row[COL_COMMON])).style(
                                    "font-weight: 600; color: var(--q-primary);"
                                )
                                with ui.row().classes("gap-6 flex-wrap"):
                                    for label, col in [
                                        ("Table", COL_REPORT),
                                        ("Column", COL_KEYWORD),
                                        ("Key", COL_FULLKEY),
                                    ]:
                                        with ui.column().classes("gap-0"):
                                            ui.label(label).style(
                                                "font-size: 0.7rem; color: #888; text-transform: uppercase;"
                                            )
                                            ui.label(str(row[col])).style(
                                                "font-family: monospace; font-size: 0.85rem; color: var(--q-secondary);"
                                            )

        ui.button("Search", on_click=do_search).props("unelevated").classes("button")

        # Allow Enter key to trigger search
        question_input.on("keydown.enter", do_search)

        results_container
