"""生成 0-6 难度梯度对比图（柱状图）。

读取 level_profiles 的权威参数，输出 outputs/_framework/L0-L6_difficulty_chart.png：
  • 上图：单本正文字数（取区间中值）随级别上升，标注 CEFR + 解码体系（自然拼读→构词法）
  • 下图：题目难度配比堆叠柱（L0 字面 / L1 推断 / L2 分析）

字体：自动挑选系统中文字体（Windows: 微软雅黑/黑体）。
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from level_profiles import LEVEL_PROFILES, ORDERED_LEVELS


def _pick_cjk_font() -> str | None:
    candidates = [
        "Microsoft YaHei", "SimHei", "Microsoft YaHei UI", "SimSun",
        "Alibaba PuHuiTi", "Noto Sans CJK SC", "PingFang SC",
    ]
    avail = {f.name for f in font_manager.fontManager.ttflist}
    for c in candidates:
        if c in avail:
            return c
    # 兜底：扫常见 Windows 字体文件
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if Path(p).exists():
            font_manager.fontManager.addfont(p)
            return font_manager.FontProperties(fname=p).get_name()
    return None


def _word_mid(s: str) -> float:
    nums = [int(n) for n in re.findall(r"\d+", s or "")]
    if not nums:
        return 0
    if len(nums) >= 2:
        return (nums[0] + nums[1]) / 2
    return nums[0]


def build_chart(out_path: Path | None = None) -> Path:
    font = _pick_cjk_font()
    if font:
        plt.rcParams["font.sans-serif"] = [font]
    plt.rcParams["axes.unicode_minus"] = False

    levels = list(ORDERED_LEVELS)
    profs = [LEVEL_PROFILES[lv] for lv in levels]
    xlabels = [f"L{lv}" for lv in levels]
    words = [_word_mid(p.word_count) for p in profs]

    # 颜色：低段绿 / 中段蓝 / 高段紫
    band_color = {"low": "#7FB069", "mid": "#4A90D9", "high": "#9B72CF"}
    bar_colors = [band_color[p.band] for p in profs]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 9), gridspec_kw={"height_ratios": [1.25, 1]}
    )

    # ---- 上图：字数阶梯 ----
    bars = ax1.bar(xlabels, words, color=bar_colors, edgecolor="white", linewidth=1.5, zorder=3)
    ax1.plot(xlabels, words, color="#C0392B", marker="o", linewidth=2, zorder=4, alpha=0.85)
    for b, p, w in zip(bars, profs, words):
        ax1.text(b.get_x() + b.get_width() / 2, w + 4,
                 f"{int(w)}词", ha="center", va="bottom", fontsize=10, fontweight="bold")
        decode = "自然拼读" if "拼读" in p.decoding_system or "音素" in p.decoding_system else "构词法"
        ax1.text(b.get_x() + b.get_width() / 2, 8,
                 f"{p.cefr}\n{decode}\n{p.ip_age}岁形象",
                 ha="center", va="bottom", fontsize=8.5, color="white", fontweight="bold")
    ax1.set_title("0-6 级难度梯度：单本正文字数 + CEFR + 解码体系",
                  fontsize=14, fontweight="bold", pad=12)
    ax1.set_ylabel("单本正文字数（区间中值）", fontsize=11)
    ax1.set_ylim(0, max(words) * 1.18)
    ax1.grid(axis="y", alpha=0.25, zorder=0)
    for sp in ("top", "right"):
        ax1.spines[sp].set_visible(False)

    # 两条分水岭
    ax1.axvline(2.5, color="#888", linestyle="--", linewidth=1, alpha=0.7)
    ax1.axvline(4.5, color="#888", linestyle="--", linewidth=1, alpha=0.7)
    ax1.text(2.5, max(words) * 1.1, "分水岭 L2→L3\n预教→语境内学词",
             ha="center", fontsize=8, color="#555")
    ax1.text(4.5, max(words) * 1.1, "分水岭 L4→L5\n拼读→构词法",
             ha="center", fontsize=8, color="#555")

    # ---- 下图：题目难度配比 ----
    lit = [p.question_mix[0] * 100 for p in profs]
    inf = [p.question_mix[1] * 100 for p in profs]
    ana = [p.question_mix[2] * 100 for p in profs]
    ax2.bar(xlabels, lit, color="#A8D5BA", label="L0 字面/回忆", zorder=3)
    ax2.bar(xlabels, inf, bottom=lit, color="#7FB3D5", label="L1 推断", zorder=3)
    ax2.bar(xlabels, ana, bottom=[l + i for l, i in zip(lit, inf)],
            color="#C39BD3", label="L2 分析/评价", zorder=3)
    for idx, (l, i, a) in enumerate(zip(lit, inf, ana)):
        if l >= 8:
            ax2.text(idx, l / 2, f"{int(l)}%", ha="center", va="center", fontsize=8)
        if i >= 8:
            ax2.text(idx, l + i / 2, f"{int(i)}%", ha="center", va="center", fontsize=8)
        if a >= 6:
            ax2.text(idx, l + i + a / 2, f"{int(a)}%", ha="center", va="center", fontsize=8)
    ax2.set_title("题目难度配比：从「看图说话」到「分析评价」", fontsize=13, fontweight="bold", pad=10)
    ax2.set_ylabel("占比 %", fontsize=11)
    ax2.set_ylim(0, 100)
    ax2.legend(loc="lower right", ncol=3, fontsize=9, framealpha=0.9)
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)

    fig.tight_layout()
    out_path = out_path or (Path(__file__).resolve().parent.parent
                            / "outputs" / "_framework" / "L0-L6_difficulty_chart.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    p = build_chart()
    print("WROTE", p)
