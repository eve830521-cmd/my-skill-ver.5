# -*- coding: utf-8 -*-
"""
convert_guide.py - Converts 이용방법.md into a styled, interactive HTML dashboard (이용방법.html v5.0)
Dynamically binds Tier-1 (Flagship) and Tier-2 (High-Speed) model names from korean-stock-analyzer/model_config.json.
"""
import json
import os
import re
import sys
import markdown

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
md_path = os.path.join(WORKSPACE_DIR, "이용방법.md")
html_path = os.path.join(WORKSPACE_DIR, "이용방법.html")
model_cfg_path = os.path.join(WORKSPACE_DIR, "korean-stock-analyzer", "model_config.json")

tier1_name = "Gemini 4.0 Argon (Medium)"
tier2_name = "Gemini 3.8 Flash High"
tier1_short = "4.0 Argon Medium"
tier2_short = "3.8 Flash High"

if os.path.exists(model_cfg_path):
    try:
        with open(model_cfg_path, "r", encoding="utf-8") as cf:
            mcfg = json.load(cf)
            tier1_name = mcfg.get("tier1_model", {}).get("name", tier1_name)
            tier2_name = mcfg.get("tier2_model", {}).get("name", tier2_name)
            tier1_short = mcfg.get("tier1_model", {}).get("short_name", tier1_short)
            tier2_short = mcfg.get("tier2_model", {}).get("short_name", tier2_short)
    except Exception:
        pass

with open(md_path, "r", encoding="utf-8") as f:
    raw_md = f.read()

html_body = markdown.markdown(
    raw_md, extensions=["extra", "tables", "fenced_code", "toc", "nl2br"]
)


def format_callouts(text):
    text = re.sub(
        r"<blockquote>\s*<p>\s*<strong>(.*?)</strong>(.*?)</p>\s*</blockquote>",
        r'<div class="callout callout-tip"><div class="callout-header"><strong>\1</strong></div><div class="callout-body"><p>\2</p></div></div>',
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"<blockquote>\s*(.*?)\s*</blockquote>",
        r'<div class="callout"><div class="callout-body">\1</div></div>',
        text,
        flags=re.DOTALL,
    )
    return text


html_body = format_callouts(html_body)

full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Antigravity 한국 주식 분석 시스템 마스터 이용방법 (v5.0)</title>
    <link rel="preconnect" href="https://cdn.jsdelivr.net">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css">
    <style>
        :root {{
            --bg-color: #0b0f17;
            --surface-color: #121824;
            --surface-hover: #1a2233;
            --border-color: #232d40;
            --text-primary: #e6edf3;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --accent-green: #10b981;
            --accent-purple: #8b5cf6;
            --accent-amber: #f59e0b;
            --code-bg: #070a10;
            --table-header-bg: #182234;
            --table-row-even: #121824;
            --table-row-odd: #0e131d;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.75;
            font-size: 15px;
            padding: 36px 20px;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            max-width: 1120px;
            margin: 0 auto;
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 44px;
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
        }}

        .doc-header {{
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 22px;
            margin-bottom: 28px;
        }}

        .badge-row {{
            display: flex;
            gap: 10px;
            margin-bottom: 14px;
            flex-wrap: wrap;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12.5px;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}

        .badge-primary {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.35);
        }}

        .badge-version {{
            background: rgba(139, 92, 246, 0.15);
            color: #a78bfa;
            border: 1px solid rgba(139, 92, 246, 0.35);
        }}

        .badge-tier1 {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.35);
        }}

        .badge-tier2 {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }}

        h1 {{
            font-size: 27px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 14px;
            line-height: 1.35;
        }}

        h2 {{
            font-size: 20.5px;
            font-weight: 700;
            color: #ffffff;
            margin-top: 42px;
            margin-bottom: 18px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }}

        h3 {{
            font-size: 17px;
            font-weight: 600;
            color: #60a5fa;
            margin-top: 28px;
            margin-bottom: 12px;
        }}

        h4 {{
            font-size: 15px;
            font-weight: 600;
            color: #ffffff;
            margin-top: 20px;
            margin-bottom: 8px;
        }}

        p {{
            margin-bottom: 14px;
        }}

        ul, ol {{
            margin-bottom: 16px;
            padding-left: 24px;
        }}

        li {{
            margin-bottom: 7px;
        }}

        .callout {{
            background: rgba(59, 130, 246, 0.08);
            border-left: 4px solid var(--accent-blue);
            border-radius: 10px;
            padding: 16px 20px;
            margin: 20px 0;
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-left-width: 4px;
        }}

        .callout.callout-tip {{
            background: rgba(6, 182, 212, 0.08);
            border-left-color: var(--accent-cyan);
            border-color: rgba(6, 182, 212, 0.2);
            border-left-width: 4px;
        }}

        .callout-header {{
            color: #22d3ee;
            font-size: 15px;
            margin-bottom: 6px;
        }}

        .table-wrapper {{
            overflow-x: auto;
            margin: 22px 0;
            border-radius: 10px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13.5px;
            text-align: left;
        }}

        th {{
            background-color: var(--table-header-bg);
            color: #ffffff;
            font-weight: 600;
            padding: 13px 15px;
            border-bottom: 2px solid var(--border-color);
            white-space: nowrap;
        }}

        td {{
            padding: 12px 15px;
            border-bottom: 1px solid var(--border-color);
            vertical-align: top;
            line-height: 1.65;
        }}

        tr:nth-child(even) {{
            background-color: var(--table-row-even);
        }}

        tr:nth-child(odd) {{
            background-color: var(--table-row-odd);
        }}

        tr:hover {{
            background-color: var(--surface-hover);
        }}

        code {{
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: rgba(148, 163, 184, 0.15);
            color: #f87171;
            padding: 2px 6px;
            border-radius: 5px;
            font-size: 13px;
        }}

        pre {{
            background-color: var(--code-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 16px 20px;
            overflow-x: auto;
            margin: 14px 0 18px 0;
            position: relative;
        }}

        pre code {{
            background: none;
            color: #4ade80;
            padding: 0;
            font-size: 13.5px;
            line-height: 1.6;
            display: block;
        }}

        .copy-btn {{
            position: absolute;
            top: 10px;
            right: 12px;
            background: rgba(59, 130, 246, 0.2);
            color: #93c5fd;
            border: 1px solid rgba(59, 130, 246, 0.4);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11.5px;
            cursor: pointer;
            transition: all 0.15s;
        }}

        .copy-btn:hover {{
            background: rgba(59, 130, 246, 0.4);
            color: #ffffff;
        }}

        hr {{
            border: none;
            border-top: 1px solid var(--border-color);
            margin: 34px 0;
        }}

        @media print {{
            body {{
                background-color: #ffffff !important;
                color: #1e293b !important;
                padding: 0 !important;
                font-size: 10.5pt !important;
            }}
            .container {{
                max-width: 100% !important;
                border: none !important;
                padding: 0 !important;
                box-shadow: none !important;
                background: #ffffff !important;
            }}
            .copy-btn {{
                display: none !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="doc-header">
            <div class="badge-row">
                <span class="badge badge-primary">Korean Stock Analyzer v5.0</span>
                <span class="badge badge-version">원샷 오케스트레이터 (ksa_orchestrator.py)</span>
                <span class="badge badge-tier1">👑 1순위 최상위 모델: {tier1_name}</span>
                <span class="badge badge-tier2">⚡ 2순위 고속 모델: {tier2_name}</span>
            </div>
        </div>
        <div class="content">
            {html_body}
        </div>
    </div>
    <script>
        document.querySelectorAll('table').forEach(tbl => {{
            const wrapper = document.createElement('div');
            wrapper.className = 'table-wrapper';
            tbl.parentNode.insertBefore(wrapper, tbl);
            wrapper.appendChild(tbl);
        }});
        document.querySelectorAll('pre').forEach(pre => {{
            const btn = document.createElement('button');
            btn.className = 'copy-btn';
            btn.textContent = '명령어 복사';
            btn.addEventListener('click', () => {{
                const code = pre.querySelector('code') ? pre.querySelector('code').innerText : pre.innerText;
                navigator.clipboard.writeText(code.trim()).then(() => {{
                    btn.textContent = '✅ 복사됨!';
                    setTimeout(() => {{ btn.textContent = '명령어 복사'; }}, 1500);
                }});
            }});
            pre.appendChild(btn);
        }});
    </script>
</body>
</html>"""

with open(html_path, "w", encoding="utf-8") as f:
    f.write(full_html)

print(f"Generated HTML: {html_path} ({os.path.getsize(html_path):,} bytes) | Tier-1: {tier1_name} | Tier-2: {tier2_name}")
