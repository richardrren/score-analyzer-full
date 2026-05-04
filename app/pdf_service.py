from __future__ import annotations

import platform
import re
from pathlib import Path
from typing import Iterable, List, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import GroupStat, StudentAnalysis

FONT_NAME = "STSong-Light"
FONT_FALLBACKS = {
    "Windows": "STSong-Light",
    "Linux": "STSong-Light",
    "Darwin": "STSong-Light",
}


def _register_font() -> None:
    try:
        pdfmetrics.getFont(FONT_NAME)
    except KeyError:
        system = platform.system()
        font_name = FONT_FALLBACKS.get(system, "STSong-Light")
        if system == "Linux":
            # 在Linux上直接使用reportlab内置的CID字体，避免TTC字体兼容性问题
            try:
                pdfmetrics.registerFont(UnicodeCIDFont(font_name))
            except Exception:
                # 如果STSong不可用，尝试其他内置字体
                for fallback_font in ["MSung-Light", "STHeiti-Light", "STKaiti-Light"]:
                    try:
                        pdfmetrics.registerFont(UnicodeCIDFont(fallback_font))
                        break
                    except Exception:
                        continue
        else:
            pdfmetrics.registerFont(UnicodeCIDFont(font_name))


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return cleaned or "未命名学生"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    normal = ParagraphStyle("ChineseNormal", parent=base["Normal"], fontName=FONT_NAME, fontSize=10.5, leading=16)
    title = ParagraphStyle(
        "ChineseTitle",
        parent=base["Title"],
        fontName=FONT_NAME,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    heading = ParagraphStyle("ChineseHeading", parent=base["Heading2"], fontName=FONT_NAME, fontSize=13, leading=18, spaceBefore=8)
    small = ParagraphStyle("ChineseSmall", parent=normal, fontSize=9, leading=13)
    return {"normal": normal, "title": title, "heading": heading, "small": small}


def _paragraph(text: object, style: ParagraphStyle) -> Paragraph:
    safe = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def _stat_table(title: str, stats: Iterable[GroupStat], styles: dict[str, ParagraphStyle]) -> List[object]:
    rows = [["项目", "得分", "满分", "得分率"]]
    for stat in list(stats)[:8]:
        rows.append([stat.name, f"{stat.earned:.1f}", f"{stat.possible:.1f}", _pct(stat.rate)])
    table = Table(rows, colWidths=[72 * mm, 28 * mm, 28 * mm, 28 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]
        )
    )
    return [_paragraph(title, styles["heading"]), table, Spacer(1, 5 * mm)]


def build_student_report(analysis: StudentAnalysis, output_path: str | Path) -> Path:
    _register_font()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    story: List[object] = []
    story.append(_paragraph(f"{analysis.name} 个人试卷分析报告", styles["title"]))

    overview = [
        ["全卷得分", analysis.total_display, "得分率", _pct(analysis.score_rate)],
        ["模板总分", "" if analysis.declared_total is None else f"{analysis.declared_total:.1f}", "报告依据", "小题分与细目表"],
    ]
    overview_table = Table(overview, colWidths=[32 * mm, 42 * mm, 32 * mm, 62 * mm])
    overview_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F1F5F9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.extend([overview_table, Spacer(1, 5 * mm)])

    story.extend(_stat_table("题型表现", analysis.type_stats, styles))
    story.extend(_stat_table("难度表现", analysis.difficulty_stats, styles))
    story.extend(_stat_table("薄弱考点", analysis.weaknesses or analysis.concept_stats[-5:], styles))

    story.append(_paragraph("错题与易错点", styles["heading"]))
    wrong_rows: List[list[object]] = [["题号", "题型", "考点", "得分/满分", "易错点"]]
    for weak in analysis.weak_questions[:10]:
        wrong_rows.append(
            [
                weak.question.number,
                weak.question.question_type,
                _paragraph(weak.question.core_concept, styles["small"]),
                f"{weak.earned:.1f}/{weak.question.score:.1f}",
                _paragraph(weak.question.misconception, styles["small"]),
            ]
        )
    if len(wrong_rows) == 1:
        wrong_rows.append(["-", "-", "没有明显失分题", "-", "继续保持"])
    wrong_table = Table(wrong_rows, colWidths=[16 * mm, 24 * mm, 35 * mm, 24 * mm, 69 * mm], repeatRows=1)
    wrong_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 1), (1, -1), "CENTER"),
                ("ALIGN", (3, 1), (3, -1), "CENTER"),
            ]
        )
    )
    story.extend([wrong_table, Spacer(1, 5 * mm)])

    story.append(_paragraph("个性化建议", styles["heading"]))
    story.append(_paragraph(analysis.ai_summary or analysis.local_advice, styles["normal"]))
    if analysis.ai_error:
        story.append(Spacer(1, 2 * mm))
        story.append(_paragraph(f"AI 建议未启用或调用失败，已使用本地规则建议。原因：{analysis.ai_error}", styles["small"]))

    doc.build(story)
    return output


def build_batch_reports(analyses: Iterable[StudentAnalysis], output_dir: str | Path) -> List[Tuple[StudentAnalysis, Path]]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    built: List[Tuple[StudentAnalysis, Path]] = []
    for analysis in analyses:
        path = output / f"{_safe_filename(analysis.name)}_个人分析报告.pdf"
        built.append((analysis, build_student_report(analysis, path)))
    return built
