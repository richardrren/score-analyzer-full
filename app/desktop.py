from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

try:
    from PySide6.QtCore import QObject, QThread, Signal
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - only used for a friendlier runtime error.
    raise SystemExit("缺少 PySide6。请先运行：pip install -r requirements.txt") from exc

from .ai_service import AIConfig, generate_ai_summary
from .analysis_service import analyze_batch
from .config_service import load_config, save_config
from .exceptions import ValidationError
from .excel_service import create_score_template, load_detail_table, load_score_sheet
from .models import QuestionItem, StudentAnalysis
from .pdf_service import build_student_report


class ReportWorker(QObject):
    progress = Signal(int, int, str)
    log = Signal(str)
    finished = Signal(int, int)

    def __init__(self, analyses: List[StudentAnalysis], output_dir: Path, ai_config: AIConfig):
        super().__init__()
        self.analyses = analyses
        self.output_dir = output_dir
        self.ai_config = ai_config

    def run(self) -> None:
        success = 0
        failed = 0
        total = len(self.analyses)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for index, analysis in enumerate(self.analyses, start=1):
            self.progress.emit(index - 1, total, analysis.name)
            try:
                if self.ai_config.enabled:
                    try:
                        analysis.ai_summary = generate_ai_summary(self.ai_config, analysis)
                    except Exception as exc:
                        analysis.ai_error = str(exc)
                        self.log.emit(f"{analysis.name}：AI 建议生成失败，已使用本地建议。{exc}")
                build_student_report(analysis, self.output_dir / f"{self._safe_name(analysis.name)}_个人分析报告.pdf")
                success += 1
                self.log.emit(f"{analysis.name}：报告已生成")
            except Exception as exc:
                failed += 1
                self.log.emit(f"{analysis.name}：报告生成失败：{exc}")
            self.progress.emit(index, total, analysis.name)
        self.finished.emit(success, failed)

    @staticmethod
    def _safe_name(name: str) -> str:
        for char in '\\/:*?"<>|':
            name = name.replace(char, "_")
        return name.strip() or "未命名学生"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("小题分模板与个人分析报告生成工具")
        self.resize(980, 760)

        self.detail_path: Optional[Path] = None
        self.score_path: Optional[Path] = None
        self.items: List[QuestionItem] = []
        self.analyses: List[StudentAnalysis] = []
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[ReportWorker] = None

        self.config = load_config()
        self._build_ui()
        self._load_config_to_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_detail_group())
        layout.addWidget(self._build_score_group())
        layout.addWidget(self._build_report_group())
        layout.addWidget(self._build_ai_group())

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("运行日志")
        layout.addWidget(self.log_box, 1)

        self.setCentralWidget(root)

    def _build_detail_group(self) -> QGroupBox:
        box = QGroupBox("细目表与模板")
        layout = QVBoxLayout(box)
        row = QHBoxLayout()
        self.detail_label = QLabel("未选择细目表")
        choose_btn = QPushButton("选择细目表")
        choose_btn.clicked.connect(self.choose_detail_file)
        template_btn = QPushButton("生成并保存小题分模板")
        template_btn.clicked.connect(self.generate_template)
        row.addWidget(self.detail_label, 1)
        row.addWidget(choose_btn)
        row.addWidget(template_btn)
        layout.addLayout(row)
        return box

    def _build_score_group(self) -> QGroupBox:
        box = QGroupBox("成绩上传与校验")
        layout = QVBoxLayout(box)
        row = QHBoxLayout()
        self.score_label = QLabel("未选择已填写小题分模板")
        choose_btn = QPushButton("选择成绩表")
        choose_btn.clicked.connect(self.choose_score_file)
        analyze_btn = QPushButton("读取并分析")
        analyze_btn.clicked.connect(self.analyze_scores)
        row.addWidget(self.score_label, 1)
        row.addWidget(choose_btn)
        row.addWidget(analyze_btn)
        layout.addLayout(row)
        return box

    def _build_report_group(self) -> QGroupBox:
        box = QGroupBox("报告生成")
        layout = QVBoxLayout(box)
        row = QHBoxLayout()
        self.output_label = QLabel("未选择报告输出文件夹")
        choose_btn = QPushButton("选择输出文件夹")
        choose_btn.clicked.connect(self.choose_output_dir)
        self.generate_reports_btn = QPushButton("批量生成个人 PDF")
        self.generate_reports_btn.clicked.connect(self.generate_reports)
        row.addWidget(self.output_label, 1)
        row.addWidget(choose_btn)
        row.addWidget(self.generate_reports_btn)
        layout.addLayout(row)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.output_dir: Optional[Path] = None
        return box

    def _build_ai_group(self) -> QGroupBox:
        box = QGroupBox("OpenAI配置")
        form = QFormLayout(box)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.base_url_input = QLineEdit()
        self.model_input = QLineEdit()
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 300)
        self.remember_key_input = QCheckBox("记住 API Key（会保存到本机配置文件）")
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_ai_config)
        form.addRow("API Key", self.api_key_input)
        form.addRow("Base URL", self.base_url_input)
        form.addRow("模型名", self.model_input)
        form.addRow("超时秒数", self.timeout_input)
        form.addRow("", self.remember_key_input)
        form.addRow("", save_btn)
        return box

    def _load_config_to_ui(self) -> None:
        self.api_key_input.setText(self.config.api_key)
        self.base_url_input.setText(self.config.base_url)
        self.model_input.setText(self.config.model)
        self.timeout_input.setValue(self.config.timeout)

    def _current_ai_config(self) -> AIConfig:
        return AIConfig(
            api_key=self.api_key_input.text().strip(),
            base_url=self.base_url_input.text().strip() or "https://api.openai.com/v1",
            model=self.model_input.text().strip(),
            timeout=self.timeout_input.value(),
        )

    def log(self, message: str) -> None:
        self.log_box.appendPlainText(message)

    def choose_detail_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择细目表", "", "Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            self.items = load_detail_table(path)
            self.detail_path = Path(path)
            total = sum(item.score for item in self.items)
            self.detail_label.setText(str(self.detail_path))
            self.log(f"细目表读取成功：{len(self.items)} 题，满分 {total:.1f}")
        except Exception as exc:
            QMessageBox.critical(self, "细目表错误", str(exc))

    def generate_template(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "缺少细目表", "请先选择并读取细目表")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存小题分模板", "小题分模板.xlsx", "Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            output = create_score_template(self.items, path)
            self.log(f"小题分模板已生成：{output}")
            QMessageBox.information(self, "完成", f"模板已生成：\n{output}")
        except Exception as exc:
            QMessageBox.critical(self, "生成失败", str(exc))

    def choose_score_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择已填写小题分模板", "", "Excel 文件 (*.xlsx)")
        if not path:
            return
        self.score_path = Path(path)
        self.score_label.setText(str(self.score_path))

    def analyze_scores(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "缺少细目表", "请先选择并读取细目表")
            return
        if not self.score_path:
            QMessageBox.warning(self, "缺少成绩表", "请先选择已填写的小题分模板")
            return
        try:
            students, warnings = load_score_sheet(self.score_path, self.items)
            self.analyses = analyze_batch(self.items, students)
            for warning in warnings:
                self.log(f"警告：{warning}")
            self.log(f"成绩读取完成：{len(self.analyses)} 名学生")
            QMessageBox.information(self, "完成", f"已完成 {len(self.analyses)} 名学生分析")
        except ValidationError as exc:
            QMessageBox.critical(self, "成绩表错误", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "分析失败", str(exc))

    def choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择报告输出文件夹")
        if not path:
            return
        self.output_dir = Path(path)
        self.output_label.setText(str(self.output_dir))

    def save_ai_config(self) -> None:
        self.config = self._current_ai_config()
        save_config(self.config, self.remember_key_input.isChecked())
        self.log("OpenAI 兼容配置已保存")

    def generate_reports(self) -> None:
        if not self.analyses:
            QMessageBox.warning(self, "缺少分析结果", "请先读取并分析成绩表")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "缺少输出目录", "请先选择报告输出文件夹")
            return
        self.generate_reports_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setMaximum(len(self.analyses))

        self.worker_thread = QThread()
        self.worker = ReportWorker(self.analyses, self.output_dir, self._current_ai_config())
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self.on_reports_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def on_progress(self, current: int, total: int, name: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        if name:
            self.progress.setFormat(f"{current}/{total} {name}")

    def on_reports_finished(self, success: int, failed: int) -> None:
        self.generate_reports_btn.setEnabled(True)
        self.log(f"报告生成结束：成功 {success}，失败 {failed}")
        QMessageBox.information(self, "报告生成结束", f"成功 {success} 份，失败 {failed} 份")


def run() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
