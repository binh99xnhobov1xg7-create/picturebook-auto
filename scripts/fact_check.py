"""科学事实正确性校验（科普非虚构绘本专用）。

用户拍板（2026-06-05）：科普 non-fiction 绘本的文字与画面，必须满足
「内容正确性符合科学实际逻辑」。本模块用文本模型对每页做事实核查：

  1. 文字科学事实正确性（数字/定义/常识，如"海洋约占地球 70%"）
  2. 真实逻辑与比例（动物大小、地理形态、自然现象是否符合现实）
  3. 图文一致（scene_cn 画面与本页 text 是否吻合、无矛盾）

对外暴露：
  - is_available()                         → 文本模型是否可用
  - fact_check_pages(pages, ...)           → 核查 [{index, text, scene_cn}]，返回 issues
  - fact_check_outline(outline)            → 直接核查 BookOutline（读 pages 的 text/scene_cn）
  - apply_fixes_to_outline(outline, issues)→ 把修正写回 outline（返回应用条数）
  - apply_fixes_to_ec_pages(pages, issues) → 把修正写回 ec.pages（dict 列表，供网页用）

issue dict 结构：
  {index, field("text"|"scene_cn"|"both"), severity("high"|"medium"|"low"),
   problem(中文问题), suggestion(中文建议), fixed_text(英文), fixed_scene_cn(中文)}

设计原则：保守且可回退——文本模型不可用或返回异常时返回空 issues，绝不阻断主流程。
scene_cn 的修正必须遵守既有铁律：只用人物名字 + 动作 + 环境 + 氛围，绝不写外观。
"""
from __future__ import annotations

from typing import Any

from deepseek_client import is_deepseek_available


_SCIENCE_FLAVORED_FICTION_TITLES = {
    "thelanguageofdolphins",
}


def _norm_title(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def is_science_flavored_fiction_whitelisted(title: str) -> bool:
    """只允许用户明确拍板的 science-flavored fiction 进入事实校验；不做宽泛自动检测。"""
    return _norm_title(title) in _SCIENCE_FLAVORED_FICTION_TITLES


def should_fact_check_outline(outline, *, is_nonfiction: bool = False) -> bool:
    """非虚构默认核查；科学味 fiction 仅白名单核查（当前只有 Book33）。"""
    if is_nonfiction:
        return True
    return is_science_flavored_fiction_whitelisted(getattr(outline, "title", "") or "")


def is_available() -> bool:
    return is_deepseek_available()


_SYSTEM_PROMPT = """You are a meticulous science/curriculum fact-checker for children's NON-FICTION (informational) picture books used by VIPKID Dino Reading Club. Output ONLY valid JSON.

Your job: review EACH page's English text AND its Chinese scene description (scene_cn), and flag anything that is scientifically wrong, factually inaccurate, or violates real-world logic/scale. Then provide a corrected drop-in version.

Check these three dimensions for every page:
1. TEXT factual/scientific accuracy — numbers, definitions, cause/effect, classifications, general-knowledge facts. (e.g. "Oceans cover about seventy percent of Earth" is correct; "spiders are insects" is WRONG.)
2. REAL-WORLD logic & scale in scene_cn — sizes/proportions of animals, plants, geography, natural phenomena; physically/biologically plausible scenes. (e.g. a hamster the size of a dog is WRONG; a river flowing uphill is WRONG.)
3. TEXT-IMAGE consistency — scene_cn must match what the page text says; no contradictions, no missing key fact, no invented facts.

Rules for corrections:
- fixed_text: corrected English page text. Keep it the SAME reading level and length, simple book sentences, English only. Leave "" if text needs no change.
- fixed_scene_cn: corrected Chinese scene description. CRITICAL — keep the existing scene_cn writing rules: refer to characters BY NAME ONLY (Mia / Tommy / ...), describe ONLY action + environment + atmosphere, and NEVER write any appearance words (no hair/clothes/colors/glasses/age/face). Fix only the factual/scale/logic problem. Leave "" if scene_cn needs no change.
- Only report pages that actually have a problem. A clean book may return an empty issues list.
- Be precise and conservative: do not invent problems; only flag genuine scientific/factual/logic errors. Do NOT nitpick art style, mood, or wording preferences.
- problem and suggestion are written in Simplified Chinese (concise, one sentence each).
- severity: "high" = clearly wrong fact/biology/physics; "medium" = misleading or imprecise; "low" = minor.

Output schema (strict JSON):
{
  "issues": [
    {
      "index": <page index int, cover=0, story pages 1-7>,
      "field": "text" | "scene_cn" | "both",
      "severity": "high" | "medium" | "low",
      "problem": "<中文：哪里不符合科学/事实/比例/图文一致>",
      "suggestion": "<中文：应如何修正>",
      "fixed_text": "<corrected English text, or empty string>",
      "fixed_scene_cn": "<修正后的中文画面描述（只含名字+动作+环境+氛围，无外观词），或空字符串>"
    }
  ]
}
"""


def _build_user_prompt(pages: list[dict], title: str, level: str, fiction_type: str = "") -> str:
    genre = (
        "SCIENCE-FLAVORED FICTION (whitelisted for factual/biology/setting sanity check)"
        if is_science_flavored_fiction_whitelisted(title) and not str(fiction_type or "").lower().startswith("non")
        else "NON-FICTION (informational picture book)"
    )
    lines = [
        f"Book title: {title}",
        f"Level: {level}",
        f"Genre: {genre}",
        "Special visual fact checks when relevant: no impossible animal anatomy, no misleading captive-animal setting details, and scene_cn must not contradict the story page.",
        "",
        "Pages to fact-check (index / text / scene_cn):",
    ]
    for p in pages:
        idx = p.get("index")
        text = (p.get("text") or "").strip()
        scene_cn = (p.get("scene_cn") or "").strip()
        if not text and not scene_cn:
            continue
        lines.append("")
        lines.append(f"## Page index {idx}")
        lines.append(f"text: {text or '(none)'}")
        lines.append(f"scene_cn: {scene_cn or '(none)'}")
    lines.append("")
    lines.append("Return the JSON object with the issues array. Empty array if everything is correct.")
    return "\n".join(lines)


def fact_check_pages(
    pages: list[dict], *, title: str = "", level: str = "", fiction_type: str = "",
) -> list[dict]:
    """核查页面列表 [{index, text, scene_cn}]，返回 issues 列表。

    文本模型不可用 / 调用失败 / 解析失败 → 返回 []（不阻断主流程）。
    """
    if not is_available():
        return []
    usable = [p for p in pages if (p.get("text") or p.get("scene_cn"))]
    if not usable:
        return []

    from deepseek_client import deepseek_chat_json

    data = deepseek_chat_json(
        system=_SYSTEM_PROMPT,
        user=_build_user_prompt(usable, title, level, fiction_type),
        temperature=0.0,
        max_tokens=3000,
        fallback=None,
    )
    if not isinstance(data, dict):
        return []
    raw = data.get("issues")
    if not isinstance(raw, list):
        return []
    return [_normalize_issue(it) for it in raw if isinstance(it, dict) and _normalize_issue(it)]


def _normalize_issue(it: dict) -> dict | None:
    try:
        idx = int(it.get("index"))
    except (TypeError, ValueError):
        return None
    field = str(it.get("field") or "").strip().lower()
    if field not in ("text", "scene_cn", "both"):
        field = "both"
    sev = str(it.get("severity") or "medium").strip().lower()
    if sev not in ("high", "medium", "low"):
        sev = "medium"
    problem = str(it.get("problem") or "").strip()
    if not problem:
        return None
    return {
        "index": idx,
        "field": field,
        "severity": sev,
        "problem": problem,
        "suggestion": str(it.get("suggestion") or "").strip(),
        "fixed_text": str(it.get("fixed_text") or "").strip(),
        "fixed_scene_cn": str(it.get("fixed_scene_cn") or "").strip(),
    }


def fact_check_outline(outline) -> list[dict]:
    """直接核查 BookOutline（读取每页 text + scene_cn）。"""
    pages = [
        {"index": p.index, "text": p.text, "scene_cn": getattr(p, "scene_cn", "")}
        for p in outline.pages
    ]
    return fact_check_pages(
        pages,
        title=outline.title,
        level=outline.level,
        fiction_type=getattr(outline, "fiction_type", "") or getattr(outline, "reader_type", ""),
    )


def apply_fixes_to_outline(outline, issues: list[dict]) -> int:
    """把 issues 里的 fixed_text / fixed_scene_cn 写回 outline。返回实际改动的字段数。"""
    by_index = {p.index: p for p in outline.pages}
    n = 0
    for it in issues or []:
        page = by_index.get(it.get("index"))
        if page is None:
            continue
        ft = it.get("fixed_text")
        fs = it.get("fixed_scene_cn")
        if ft and ft != page.text:
            page.text = ft
            n += 1
        if fs and fs != getattr(page, "scene_cn", ""):
            page.scene_cn = fs
            n += 1
    return n


def apply_fixes_to_ec_pages(ec_pages: list[dict], issues: list[dict]) -> int:
    """把 issues 写回 ec.pages（dict 列表，供网页交互用）。返回改动字段数。"""
    by_index = {int(p.get("index") or 0): p for p in ec_pages}
    n = 0
    for it in issues or []:
        page = by_index.get(it.get("index"))
        if page is None:
            continue
        ft = it.get("fixed_text")
        fs = it.get("fixed_scene_cn")
        if ft and ft != page.get("text"):
            page["text"] = ft
            n += 1
        if fs and fs != page.get("scene_cn"):
            page["scene_cn"] = fs
            n += 1
    return n


def summarize_issues(issues: list[dict]) -> str:
    """把 issues 汇总成一段中文日志（供批处理日志/网页提示）。"""
    if not issues:
        return "科学事实校验：未发现问题。"
    parts = [f"科学事实校验：发现 {len(issues)} 处问题。"]
    for it in issues:
        loc = "Cover" if it["index"] == 0 else f"Page {it['index'] + 1}"
        parts.append(f"[{it['severity']}] {loc}（{it['field']}）：{it['problem']}")
    return "\n".join(parts)
