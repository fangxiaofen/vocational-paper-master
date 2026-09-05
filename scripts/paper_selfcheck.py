#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
职业教育论文成稿自动化初筛。

用法:
    python paper_selfcheck.py <论文文件.md> [--json]

功能:
    1. 结构完整性：标题/摘要/关键词/引言/正文/结论/参考文献 是否齐备
    2. 摘要四要素：目的—方法—结果—结论 是否齐备
    3. 关键词数量：解析 3—6 个
    4. AI腔排查：高频套话词频统计
    5. 参考文献：GB/T 7714 形式初判（[n] 编号 + 文献类型标识）
    6. 字数估计：中文字符数（不含标点/空格的近似）

注意: 本脚本仅做机械初筛，结果须人工复核；不判断学术质量与查重。
"""
import argparse
import json
import re
import sys

# 高频 AI 套话（出现即记录，供改写参考）
AI_PHRASES = [
    "总而言之", "综上所述", "值得注意的是", "毋庸置疑", "在当今社会",
    "随着", "日益", "赋能", "抓手", "痛点和难点", "一方面", "另一方面",
    "首先", "其次", "最后", "由此可见", "在这个背景下", "发挥着重要作用",
    "具有重要意义", "不可忽视",
]

# 摘要四要素关键词
ABSTRACT_KEYS = ["目的", "方法", "结果", "结论"]

SECTION_MARKERS = {
    "摘要": r"摘要",
    "关键词": r"关键词",
    "引言": r"引言|问题提出|一[、．.]",
    "正文": r"二[、．.]|三[、．.]|四[、．.]|核心分析|现状",
    "结论": r"结论|五[、．.]",
    "参考文献": r"参考文献",
}


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def count_cn_chars(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def check_sections(text: str) -> dict:
    res = {}
    for name, pat in SECTION_MARKERS.items():
        res[name] = bool(re.search(pat, text))
    return res


def check_abstract(text: str) -> dict:
    # 抽取摘要段
    m = re.search(r"摘要[：:]\s*(.*?)(?:\n\s*\n|关键词)", text, re.S)
    seg = m.group(1) if m else text
    found = {k: (k in seg) for k in ABSTRACT_KEYS}
    return {"segment_found": bool(m), "keys": found,
            "missing": [k for k, v in found.items() if not v]}


def check_keywords(text: str) -> dict:
    m = re.search(r"关键词[：:]\s*(.*)", text)
    if not m:
        return {"found": False, "count": 0, "items": []}
    line = m.group(1).strip()
    items = re.split(r"[；;，,\s]+", line)
    items = [i for i in items if i]
    return {"found": True, "count": len(items),
            "items": items,
            "ok": 3 <= len(items) <= 6}


def check_ai_phrases(text: str) -> dict:
    hits = {}
    for p in AI_PHRASES:
        c = text.count(p)
        if c:
            hits[p] = c
    return {"total": sum(hits.values()), "hits": hits}


def check_references(text: str) -> dict:
    # 取参考文献段
    m = re.search(r"参考文献\s*(.*)", text, re.S)
    seg = m.group(1) if m else ""
    lines = [l.strip() for l in seg.splitlines() if l.strip()]
    numbered = [l for l in lines if re.match(r"^\[\d+\]", l)]
    # GB/T 7714 文献类型标识
    typed = [l for l in numbered if re.search(r"\[[A-Z]+\]", l) or "/" in l]
    return {
        "count": len(numbered),
        "gb_format_hint": len(typed),
        "ok": len(numbered) > 0,
        "format_ratio": round(len(typed) / len(numbered), 2) if numbered else 0,
    }


def main():
    ap = argparse.ArgumentParser(description="职业教育论文成稿自动化初筛")
    ap.add_argument("path", help="论文文件路径 (.md/.txt)")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args()

    try:
        text = read_text(args.path)
    except Exception as e:
        print(f"无法读取文件: {e}", file=sys.stderr)
        sys.exit(1)

    report = {
        "file": args.path,
        "cn_chars": count_cn_chars(text),
        "sections": check_sections(text),
        "abstract": check_abstract(text),
        "keywords": check_keywords(text),
        "ai_phrases": check_ai_phrases(text),
        "references": check_references(text),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # 人类可读报告
    print(f"论文初筛报告：{args.path}")
    print(f"中文字数估计：{report['cn_chars']}（核心期刊常见区间 6000—12000）")
    print("\n【结构完整性】")
    for k, v in report["sections"].items():
        print(f"  {'✓' if v else '✗'} {k}")
    print("\n【摘要四要素】")
    ab = report["abstract"]
    if ab["segment_found"]:
        for k, v in ab["keys"].items():
            print(f"  {'✓' if v else '✗'} {k}")
        if ab["missing"]:
            print(f"  缺失：{', '.join(ab['missing'])}")
    else:
        print("  ✗ 未识别到摘要段")
    print("\n【关键词】")
    kw = report["keywords"]
    if kw["found"]:
        print(f"  数量 {kw['count']} {'✓' if kw['ok'] else '✗(建议3—6个)'}：{', '.join(kw['items'])}")
    else:
        print("  ✗ 未识别到关键词")
    print("\n【AI腔词频】")
    if report["ai_phrases"]["total"]:
        for p, c in report["ai_phrases"]["hits"].items():
            print(f"  {p} ×{c}")
        print(f"  合计 {report['ai_phrases']['total']} 处，建议改写")
    else:
        print("  未发现高频套话")
    print("\n【参考文献】")
    rf = report["references"]
    print(f"  条数 {rf['count']}；GB/T 7714 形式命中 {rf['gb_format_hint']}（比例 {rf['format_ratio']}）")
    print("\n提示：本结果为机械初筛，须人工复核学术质量与查重。")


if __name__ == "__main__":
    main()
