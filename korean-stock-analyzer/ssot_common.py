"""
Shared helpers for the Korean Stock Analyzer pipeline (v5.0).

1) Path configuration  - every default equals the previously hard-coded value, so behaviour is
   unchanged unless an environment variable overrides it (portable across PCs / drives).
       KSA_STOCK_RESEARCH_ROOT : folder that holds one sub-folder per company
       KSA_MY_LIST_ROOT        : folder with my-list/cache.db and */Data.xlsx
       KSA_S_CURVE_REGISTRY    : path to korean cycle s_curve_registry.json
2) Model configuration - loads and updates model_config.json so Tier-1 (Flagship) and Tier-2 (High-Speed)
   models can be customized seamlessly when successor Gemini models (e.g. Argon Flash) are released.
3) Warning registry    - replaces silent `except: pass`. Warnings are written into
   valuation_metrics.json -> "data_quality" so degraded runs are never invisible.
"""
import json
import os
from datetime import datetime
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent
_WORKSPACE = _SKILL_DIR.parent  # ...\my-skill

STOCK_RESEARCH_ROOT = os.environ.get(
    "KSA_STOCK_RESEARCH_ROOT", str(_WORKSPACE / "Stock_Research")
)
MY_LIST_ROOT = os.environ.get(
    "KSA_MY_LIST_ROOT", r"e:\antigravity-work\my-stock\my-list"
)
S_CURVE_REGISTRY_PATH = os.environ.get(
    "KSA_S_CURVE_REGISTRY",
    r"e:\antigravity-work\korean cycle\00_megatrend\docs\s_curve_registry.json",
)
REPORT_CSS_PATH = os.environ.get(
    "KSA_REPORT_CSS", str(_SKILL_DIR / "report_style.css")
)
MODEL_CONFIG_PATH = os.environ.get(
    "KSA_MODEL_CONFIG", str(_SKILL_DIR / "model_config.json")
)

_WARNINGS = []


def get_model_config():
    """Loads customizable Tier-1 / Tier-2 model configuration from model_config.json."""
    default_cfg = {
        "version": "5.0",
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "tier1_model": {
            "role": "1순위 최상위 추론 모델 (Flagship Deep-Reasoning Model)",
            "name": "Gemini 4.0 Argon (Medium)",
            "short_name": "4.0 Argon (Medium)",
        },
        "tier2_model": {
            "role": "2순위 고속 구조화 추론 모델 (High-Speed Structured Model)",
            "name": "Gemini 3.8 Flash High",
            "short_name": "3.8 Flash High",
        },
    }
    if os.path.exists(MODEL_CONFIG_PATH):
        try:
            with open(MODEL_CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_cfg.update(loaded)
        except Exception:
            pass
    return default_cfg


def update_model_config(tier1_name=None, tier2_name=None):
    """Updates Tier-1 and/or Tier-2 model names in model_config.json for future Gemini releases."""
    cfg = get_model_config()
    if tier1_name:
        cfg.setdefault("tier1_model", {})["name"] = tier1_name.strip()
        cfg["tier1_model"]["short_name"] = tier1_name.replace("Gemini ", "").strip()
    if tier2_name:
        cfg.setdefault("tier2_model", {})["name"] = tier2_name.strip()
        cfg["tier2_model"]["short_name"] = tier2_name.replace("Gemini ", "").strip()
    cfg["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    with open(MODEL_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def record_warning(stage, detail, severity="warn"):
    """Record a non-fatal problem. severity: 'warn' (informational) | 'degraded' (numbers may be affected)."""
    entry = {"stage": str(stage), "severity": severity, "detail": str(detail)}
    if entry not in _WARNINGS:
        _WARNINGS.append(entry)
    print(f"  [WARN:{severity}] {stage}: {detail}")


def get_warnings():
    return list(_WARNINGS)


def reset_warnings():
    _WARNINGS.clear()


def data_quality_summary():
    """Compact block stored in valuation_metrics.json."""
    status = "degraded" if any(w["severity"] == "degraded" for w in _WARNINGS) else (
        "warn" if _WARNINGS else "ok"
    )
    return {"status": status, "warnings": get_warnings()}
