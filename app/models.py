from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class QuestionItem:
    number: str
    question_type: str
    core_concept: str
    score: float
    difficulty: str
    misconception: str

    @property
    def template_header(self) -> str:
        return f"{self.question_type}{self.number}（{self.score:.1f}分）"


@dataclass
class StudentScores:
    name: str
    declared_total: Optional[float]
    scores_by_question: Dict[str, float]
    row_number: int


@dataclass
class GroupStat:
    name: str
    earned: float
    possible: float

    @property
    def rate(self) -> float:
        return self.earned / self.possible if self.possible else 0.0


@dataclass
class WeakQuestion:
    question: QuestionItem
    earned: float

    @property
    def lost(self) -> float:
        return max(self.question.score - self.earned, 0.0)

    @property
    def rate(self) -> float:
        return self.earned / self.question.score if self.question.score else 0.0


@dataclass
class StudentAnalysis:
    name: str
    declared_total: Optional[float]
    calculated_total: float
    possible_total: float
    score_rate: float
    type_stats: List[GroupStat]
    difficulty_stats: List[GroupStat]
    concept_stats: List[GroupStat]
    strengths: List[GroupStat]
    weaknesses: List[GroupStat]
    weak_questions: List[WeakQuestion]
    local_advice: str
    ai_summary: Optional[str] = None
    ai_error: Optional[str] = None

    @property
    def total_display(self) -> str:
        return f"{self.calculated_total:.1f}/{self.possible_total:.1f}"


@dataclass
class BatchResult:
    analyses: List[StudentAnalysis] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
