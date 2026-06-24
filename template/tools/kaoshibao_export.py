"""
将毛中特概论三册题库（markdown）转换为考试宝 Word 导入格式。
输出：纯文本文件，可直接复制到 Word 后导入考试宝。

考试宝格式规范：
- 单选题：序号、题目、ABCD选项（用点或顿号）、答案另起一行
- 多选题：同上，答案2个及以上选项字母连写
- 支持 解析（选填）和 章节（选填）

Usage: python tools/kaoshibao_export.py
"""
import re
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(BASE, "_INBOX", "毛中特概论678题-考试宝导入版.txt")

VOL1 = os.path.join(BASE, "wiki", "outputs", "2026-06-24-mao-zedong-thought-exam-question-bank.md")
VOL2 = os.path.join(BASE, "wiki", "outputs", "2026-06-24-mao-zedong-thought-exam-question-bank-vol2.md")
VOL3 = os.path.join(BASE, "wiki", "outputs", "2026-06-24-mao-zedong-thought-exam-question-bank-vol3.md")

# ── Chapter definitions ──
CHAPTERS = {
    "导论": {"single_start": "D01", "multi_start": "D31"},
    "第一章": {"single_start": "C01", "multi_start": "C76"},
    "第二章": {"single_start": "X01", "multi_start": "X91"},
    "第三章": {"single_start": "G01", "multi_start": "G61"},
    "第四章": {"single_start": "S01", "multi_start": "S46"},
}

# Vol3 chapters (提高卷)
VOL3_CHAPTERS = {
    "导论（提高）": {"single": ["D51","D52","D53","D54","D55","D56","D57","D61","D62","D63","D64","D67","D68"],
                      "multi": ["D58","D59","D60","D65","D66","D69","D70","D71"]},
    "第一章（提高）": {"single": ["C126","C127","C128","C129","C130","C131","C132","C133","C134","C140","C141","C142","C143","C144","C145","C152","C153","C154"],
                       "multi": ["C135","C136","C137","C138","C139","C146","C147","C148","C149","C150","C151","C155","C156","C157","C158"]},
    "第二章（提高）": {"single": ["X151","X152","X153","X154","X155","X156","X157","X158","X159","X166","X167","X168","X169","X170","X171","X172","X173","X181","X182","X183","X184"],
                       "multi": ["X160","X161","X162","X163","X164","X165","X174","X175","X176","X177","X178","X179","X180","X185","X186","X187","X188","X189","X190"]},
    "第三章（提高）": {"single": ["G101","G102","G103","G104","G105","G106","G107","G113","G114","G115","G116","G117","G118","G125","G126","G127"],
                       "multi": ["G108","G109","G110","G111","G112","G119","G120","G121","G122","G123","G124","G128","G129","G130","G131"]},
    "第四章（提高）": {"single": ["S76","S77","S78","S79","S80","S81","S82","S83","S89","S90","S91","S92","S93","S94","S101","S102","S103","S104"],
                       "multi": ["S84","S85","S86","S87","S88","S95","S96","S97","S98","S99","S100","S105","S106","S107","S108"]},
    "跨章综合（提高）": {"single": ["K01","K02","K03","K04","K05","K06","K07","K08","K11","K12","K13","K14"],
                          "multi": ["K09","K10","K15","K16","K17","K18","K19","K20"]},
}


def load_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def find_answer(text, qid, answer_section):
    """Find answer for question qid in answer section."""
    # Look for table row: | Q01 | A | Q02 | B |
    # Or: | Q01 | A |
    pattern = re.compile(rf'\|\s*{re.escape(qid)}\s*\|\s*([A-G]+)\s*\|')
    m = pattern.search(answer_section)
    if m:
        return m.group(1)
    return None


def extract_single_block(text, qid):
    """Extract a single-choice question block from text."""
    # Pattern: **Q01.** question text ... until next **Q or --- or ##
    # Lines starting with A. B. C. D. are options
    pattern = re.compile(
        rf'\*\*{re.escape(qid)}\.\*\*\s*(.+?)\n'
        rf'(.*?)'
        rf'(?=\n\*\*[A-Z]\d+\.\*\*|\n---|\n## |\n\*\(因篇幅)',
        re.DOTALL
    )
    m = pattern.search(text)
    if not m:
        return None, None

    stem = m.group(1).strip()
    body = m.group(2).strip()

    # Extract options: A. ... B. ... C. ... D. ... E. ...
    options = []
    for opt_match in re.finditer(r'([A-G])\.\s*(.+?)(?=\s*[A-G]\.\s|\s*$)', body, re.DOTALL):
        options.append((opt_match.group(1), opt_match.group(2).strip()))

    return stem, options


def extract_multi_block(text, qid):
    """Extract a multi-choice question block from text."""
    # Pattern: **Q01.**（多选）question text
    pattern = re.compile(
        rf'\*\*{re.escape(qid)}\.\*\*\s*(?:（多选）)?\s*(.+?)\n'
        rf'(.*?)'
        rf'(?=\n\*\*[A-Z]\d+\.\*\*|\n---|\n## |\n\*\(因篇幅)',
        re.DOTALL
    )
    m = pattern.search(text)
    if not m:
        return None, None

    stem = m.group(1).strip()
    body = m.group(2).strip()

    options = []
    for opt_match in re.finditer(r'([A-G])\.\s*(.+?)(?=\s*[A-G]\.\s|\s*$)', body, re.DOTALL):
        options.append((opt_match.group(1), opt_match.group(2).strip()))

    return stem, options


def format_kaoshibao_single(qid, stem, options, answer, chapter_name):
    """Format a single-choice question in Kaoshibao format."""
    lines = []
    lines.append(f"{qid}、{stem}")
    # Options on one line with spacing
    opt_strs = []
    for letter, text in options:
        opt_strs.append(f"{letter}.{text}")
    lines.append("  ".join(opt_strs))
    lines.append(f"答案：{answer}")
    lines.append(f"章节：{chapter_name}")
    lines.append("")
    return "\n".join(lines)


def format_kaoshibao_multi(qid, stem, options, answer, chapter_name):
    """Format a multi-choice question in Kaoshibao format."""
    lines = []
    lines.append(f"{qid}、{stem}")
    opt_strs = []
    for letter, text in options:
        opt_strs.append(f"{letter}.{text}")
    lines.append("  ".join(opt_strs))
    lines.append(f"答案：{answer}")
    lines.append(f"章节：{chapter_name}")
    lines.append("")
    return "\n".join(lines)


def process_chapter(text, chap_name, single_start, multi_start, answer_text):
    """Process questions from a chapter in vol1/vol2 format."""
    singles = []
    multis = []

    # Find single-choice questions
    prefix = single_start[0]  # D, C, X, G, S
    for i in range(200):  # generous range
        if prefix == 'D':
            num = i + 1
            if num > 75:
                break
            qid = f"D{num:02d}"
        elif prefix == 'C':
            num = i + 1
            if num > 125:
                break
            qid = f"C{num:02d}"
        elif prefix == 'X':
            num = i + 1
            if num > 150:
                break
            qid = f"X{num:02d}"
        elif prefix == 'G':
            num = i + 1
            if num > 124:
                break
            qid = f"G{num:02d}"
        elif prefix == 'S':
            num = i + 1
            if num > 100:
                break
            qid = f"S{num:02d}"
        else:
            break

        stem, options = extract_single_block(text, qid)
        if stem is None:
            continue
        # Skip if it's a multi-choice — check the line immediately after **QID.**
        qid_pattern = re.compile(rf'\*\*{re.escape(qid)}\.\*\*')
        qid_match = qid_pattern.search(text)
        if qid_match:
            # Only check the 2 lines right after the match (not a giant 300-char window)
            after_match = text[qid_match.end():qid_match.end() + 200]
            first_line = after_match.split('\n')[0] if '\n' in after_match else after_match
            if '（多选）' in first_line:
                continue  # It's a multi-choice

        answer = find_answer(answer_text, qid, answer_text)
        if answer:
            singles.append((qid, stem, options, answer))

    # Find multi-choice questions
    for i in range(200):
        if prefix == 'D':
            num = i + 31
            if num > 70:
                break
            qid = f"D{num:02d}"
        elif prefix == 'C':
            num = i + 76
            if num > 125:
                break
            qid = f"C{num:02d}"
        elif prefix == 'X':
            num = i + 91
            if num > 150:
                break
            qid = f"X{num:02d}"
        elif prefix == 'G':
            num = i + 61
            if num > 100:
                break
            qid = f"G{num:02d}"
        elif prefix == 'S':
            num = i + 46
            if num > 75:
                break
            qid = f"S{num:02d}"
        else:
            break

        stem, options = extract_multi_block(text, qid)
        if stem is None:
            continue
        answer = find_answer(answer_text, qid, answer_text)
        if answer:
            multis.append((qid, stem, options, answer))

    return singles, multis


def process_vol3_chapter(text, chap_name, single_ids, multi_ids):
    """Process questions from a vol3 chapter."""
    singles = []
    multis = []

    for qid in single_ids:
        stem, options = extract_single_block(text, qid)
        if stem is None:
            continue
        # Find answer in the answer section
        answer_pattern = re.compile(rf'\|\s*{re.escape(qid)}\s*\|\s*([A-G]+)\s*\|')
        m = answer_pattern.search(text)
        if m:
            singles.append((qid, stem, options, m.group(1)))

    for qid in multi_ids:
        stem, options = extract_multi_block(text, qid)
        if stem is None:
            continue
        answer_pattern = re.compile(rf'\|\s*{re.escape(qid)}\s*\|\s*([A-G]+)\s*\|')
        m = answer_pattern.search(text)
        if m:
            multis.append((qid, stem, options, m.group(1)))

    return singles, multis


def main():
    output_lines = []

    # Header
    output_lines.append("毛中特概论选择题题库（考试宝导入版）")
    output_lines.append("")
    output_lines.append("一、单选题要求：")
    output_lines.append("1. 试题必须有序号；2. ABCD选项用点或顿号；3. 答案必须另起一行；4. 解析和章节选填。")
    output_lines.append("二、多选题要求：")
    output_lines.append("1. 其他要求和单选题一致；2. 多选题最多支持8个选项，答案必须有2个及以上选项。")
    output_lines.append("")
    output_lines.append("=" * 60)
    output_lines.append("")

    # ── Process Vol 1 & 2 ──
    for vol_path, vol_label in [(VOL1, "上册"), (VOL2, "下册")]:
        if not os.path.exists(vol_path):
            print(f"WARNING: {vol_path} not found, skipping")
            continue

        text = load_text(vol_path)

        chapters_in_vol = {
            "导论": vol_label == "上册",
            "第一章": vol_label == "上册",
            "第二章": vol_label == "下册",
            "第三章": vol_label == "下册",
            "第四章": vol_label == "下册",
        }

        for chap_name, config in CHAPTERS.items():
            if not chapters_in_vol.get(chap_name):
                continue

            singles, multis = process_chapter(
                text, chap_name,
                config["single_start"], config["multi_start"],
                text  # answer section is in the same file
            )

            if singles or multis:
                output_lines.append(f"# {chap_name}")
                output_lines.append("")

            if singles:
                output_lines.append("单选题")
                output_lines.append("")
                for i, (qid, stem, options, answer) in enumerate(singles, 1):
                    output_lines.append(format_kaoshibao_single(
                        qid, stem, options, answer, chap_name
                    ))

            if multis:
                output_lines.append("多选题")
                output_lines.append("")
                for i, (qid, stem, options, answer) in enumerate(singles, 1):
                    pass  # reset counter
                for qid, stem, options, answer in multis:
                    output_lines.append(format_kaoshibao_multi(
                        qid, stem, options, answer, chap_name
                    ))

            output_lines.append("")
            print(f"  [{vol_label}] {chap_name}: {len(singles)} 单选 + {len(multis)} 多选")

    # ── Process Vol 3 (提高卷) ──
    if os.path.exists(VOL3):
        text = load_text(VOL3)
        output_lines.append("=" * 60)
        output_lines.append("# 提高卷")
        output_lines.append("")

        for chap_name, ids in VOL3_CHAPTERS.items():
            singles, multis = process_vol3_chapter(text, chap_name, ids["single"], ids["multi"])

            if singles or multis:
                output_lines.append(f"## {chap_name}")
                output_lines.append("")

            if singles:
                output_lines.append("单选题")
                output_lines.append("")
                for qid, stem, options, answer in singles:
                    # Clean up stem - remove difficulty markers
                    stem = re.sub(r'^[🟡🔴]\s*', '', stem)
                    output_lines.append(format_kaoshibao_single(
                        qid, stem, options, answer, chap_name
                    ))

            if multis:
                output_lines.append("多选题")
                output_lines.append("")
                for qid, stem, options, answer in multis:
                    stem = re.sub(r'^[🟡🔴]\s*', '', stem)
                    output_lines.append(format_kaoshibao_multi(
                        qid, stem, options, answer, chap_name
                    ))

            output_lines.append("")
            print(f"  [提高卷] {chap_name}: {len(singles)} 单选 + {len(multis)} 多选")

    # ── Write output ──
    output_text = "\n".join(output_lines)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(output_text)

    # Count totals
    total_single = len(re.findall(r'^答案：[A-E]$', output_text, re.MULTILINE))
    total_multi = len(re.findall(r'^答案：[A-E]{2,}$', output_text, re.MULTILINE))

    print(f"\n✅ 输出: {OUTPUT}")
    print(f"📊 总计: {total_single} 单选 + {total_multi} 多选 = {total_single + total_multi} 题")
    print(f"📏 文件大小: {os.path.getsize(OUTPUT):,} bytes")


if __name__ == "__main__":
    main()
