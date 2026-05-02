from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from .models import GroupStat, QuestionItem, StudentAnalysis, StudentScores, WeakQuestion


def _group_stats(items: List[QuestionItem], scores: Dict[str, float], attr: str) -> List[GroupStat]:
    earned = defaultdict(float)
    possible = defaultdict(float)
    for item in items:
        key = getattr(item, attr) or "未标注"
        earned[key] += scores.get(item.number, 0.0)
        possible[key] += item.score
    return sorted((GroupStat(k, earned[k], possible[k]) for k in possible), key=lambda stat: (-stat.rate, stat.name))


def _local_advice(weaknesses: List[GroupStat], weak_questions: List[WeakQuestion]) -> str:
    if not weaknesses and not weak_questions:
        return "本次各模块掌握较稳定。后续建议保持订正节奏，并用限时练习巩固审题与表达。"
    focus = "、".join(stat.name for stat in weaknesses[:3]) or "低得分题目"
    question_numbers = "、".join(wq.question.number for wq in weak_questions[:5])
    if question_numbers:
        return f"建议优先复盘 {focus}，重点订正第 {question_numbers} 题，整理对应概念、失分原因和可迁移的解题步骤。"
    return f"建议优先复盘 {focus}，用错题中的易错点反推知识漏洞，再进行同类题巩固。"


def analyze_student(items: Iterable[QuestionItem], student: StudentScores) -> StudentAnalysis:
    questions = list(items)
    possible_total = sum(item.score for item in questions)
    calculated_total = sum(student.scores_by_question.get(item.number, 0.0) for item in questions)
    score_rate = calculated_total / possible_total if possible_total else 0.0

    type_stats = _group_stats(questions, student.scores_by_question, "question_type")
    difficulty_stats = _group_stats(questions, student.scores_by_question, "difficulty")
    concept_stats = _group_stats(questions, student.scores_by_question, "core_concept")

    strengths = [stat for stat in concept_stats if stat.possible > 0 and stat.rate >= 0.85][:5]
    weaknesses = sorted(
        [stat for stat in concept_stats if stat.possible > 0 and stat.rate < 0.75],
        key=lambda stat: (stat.rate, -stat.possible, stat.name),
    )[:5]

    weak_questions = sorted(
        [
            WeakQuestion(item, student.scores_by_question.get(item.number, 0.0))
            for item in questions
            if student.scores_by_question.get(item.number, 0.0) < item.score
        ],
        key=lambda wq: (-wq.lost, wq.rate, wq.question.number),
    )[:12]

    return StudentAnalysis(
        name=student.name,
        declared_total=student.declared_total,
        calculated_total=calculated_total,
        possible_total=possible_total,
        score_rate=score_rate,
        type_stats=type_stats,
        difficulty_stats=difficulty_stats,
        concept_stats=concept_stats,
        strengths=strengths,
        weaknesses=weaknesses,
        weak_questions=weak_questions,
        local_advice=_local_advice(weaknesses, weak_questions),
    )


def analyze_batch(items: Iterable[QuestionItem], students: Iterable[StudentScores]) -> List[StudentAnalysis]:
    questions = list(items)
    return [analyze_student(questions, student) for student in students]
