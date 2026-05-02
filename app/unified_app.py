from __future__ import annotations

import sys
import os
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
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit("缺少 PySide6。请先运行：pip install -r requirements.txt") from exc

from .ai_service import AIConfig, generate_ai_summary
from .analysis_service import analyze_batch
from .config_service import load_config as load_ai_config, save_config as save_ai_config
from .exceptions import ValidationError
from .excel_service import create_score_template, load_detail_table, load_score_sheet
from .models import QuestionItem, StudentAnalysis, StudentScores
from . import pdf_parser
from . import ai_client
import pandas

WORKFLOW_SYSTEM_PROMPT = """你是一位专业的初中科学试卷分析专家。请根据提供的试卷内容，生成标准化的试卷细目表。

要求：
1. 输出格式：JSON数组，每个元素包含以下字段：
   - "题号"：整数或字符串
   - "题型"：选择题/填空题/实验探究题/计算题
   - "核心考点"：必须严格按照浙教版初中科学教材的官方知识点命名，禁止自创名称
   - "分值"：数字
   - "难度等级"：基础/中档/难题
   - "易错点"：针对该题目的常见错误

2. 只输出JSON，不要其他文字说明。"""


class PDFAnalysisWorker(QObject):
    progress = Signal(int, int, str)
    log = Signal(str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, pdf_path: str, api_url: str, api_key: str, model: str):
        super().__init__()
        self.pdf_path = pdf_path
        self.api_url = api_url
        self.api_key = api_key
        self.model = model

    def run(self) -> None:
        try:
            self.log.emit("步骤1/4: 正在解析PDF文件...")
            self.progress.emit(0, 4, "解析PDF")

            pdf_content = pdf_parser.extract_pdf_content(self.pdf_path)
            if not pdf_content:
                self.error.emit("PDF解析失败，请检查PDF文件是否有效")
                return

            self.log.emit("步骤2/4: PDF解析成功")
            self.log.emit("步骤3/4: 正在调用AI分析...")
            self.progress.emit(1, 4, "AI分析中")

            messages = [
                {"role": "system", "content": WORKFLOW_SYSTEM_PROMPT},
                {"role": "user", "content": f"请分析以下试卷内容并生成细目表：\n\n{pdf_content}"}
            ]

            import requests

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3
            }

            response = requests.post(
                self.api_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            import json
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start == -1 or json_end == 0:
                self.error.emit("AI返回内容不是有效的JSON格式")
                return

            json_str = content[json_start:json_end]
            analysis_data = json.loads(json_str)

            self.log.emit(f"步骤4/4: 分析完成！共识别 {len(analysis_data)} 道题目")
            self.progress.emit(4, 4, "完成")
            self.finished.emit(analysis_data)

        except Exception as e:
            self.error.emit(f"发生错误: {str(e)}")


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
        from .pdf_service import build_student_report

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

                safe_name = analysis.name.replace('\\/*?"<>|', "_").strip() or "未命名学生"
                build_student_report(analysis, self.output_dir / f"{safe_name}_个人分析报告.pdf")
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
        self.setWindowTitle("初中科学试卷分析系统 - 整合版")
        self.resize(1000, 800)

        self.detail_path: Optional[Path] = None
        self.score_path: Optional[Path] = None
        self.current_pdf_path: Optional[str] = None
        self.items: List[QuestionItem] = []
        self.analyses: List[StudentAnalysis] = []
        self.analysis_data: List[dict] = []
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[PDFAnalysisWorker] = None
        self.report_worker_thread: Optional[QThread] = None
        self.report_worker: Optional[ReportWorker] = None

        self.config = load_ai_config()
        self._build_ui()
        self._load_config_to_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        tabs = QTabWidget()
        tabs.addTab(self._build_workflow_tab(), "完整工作流")
        tabs.addTab(self._build_detail_tab(), "细目表与模板")
        tabs.addTab(self._build_report_tab(), "报告生成")
        tabs.addTab(self._build_config_tab(), "API配置")

        layout.addWidget(tabs)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("运行日志")
        layout.addWidget(self.log_box, 1)

        self.setCentralWidget(root)

    def _build_workflow_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        step1 = QGroupBox("步骤1: 上传PDF并生成细目表")
        step1_layout = QVBoxLayout(step1)
        row1 = QHBoxLayout()
        self.workflow_pdf_label = QLabel("未选择PDF文件")
        choose_btn = QPushButton("选择PDF文件")
        choose_btn.clicked.connect(self.workflow_choose_pdf)
        self.workflow_analyze_btn = QPushButton("开始AI分析")
        self.workflow_analyze_btn.clicked.connect(self.workflow_start_analysis)
        self.workflow_analyze_btn.setEnabled(False)
        row1.addWidget(self.workflow_pdf_label, 1)
        row1.addWidget(choose_btn)
        row1.addWidget(self.workflow_analyze_btn)
        step1_layout.addLayout(row1)

        self.workflow_progress = QProgressBar()
        step1_layout.addWidget(self.workflow_progress)

        self.workflow_save_table_btn = QPushButton("保存细目表Excel")
        self.workflow_save_table_btn.clicked.connect(self.workflow_save_table)
        self.workflow_save_table_btn.setEnabled(False)
        step1_layout.addWidget(self.workflow_save_table_btn)

        self.workflow_use_step1_btn = QPushButton("直接使用细目表")
        self.workflow_use_step1_btn.clicked.connect(self.workflow_use_step1_table)
        self.workflow_use_step1_btn.setEnabled(False)
        step1_layout.addWidget(self.workflow_use_step1_btn)
        layout.addWidget(step1)

        step2 = QGroupBox("步骤2: 生成小题分模板")
        step2_layout = QVBoxLayout(step2)
        row2 = QHBoxLayout()
        self.workflow_detail_label = QLabel("未选择细目表")
        choose_detail_btn = QPushButton("选择细目表")
        choose_detail_btn.clicked.connect(self.workflow_choose_detail)
        self.workflow_template_btn = QPushButton("生成小题分模板")
        self.workflow_template_btn.clicked.connect(self.workflow_generate_template)
        self.workflow_template_btn.setEnabled(False)
        row2.addWidget(self.workflow_detail_label, 1)
        row2.addWidget(choose_detail_btn)
        row2.addWidget(self.workflow_template_btn)
        step2_layout.addLayout(row2)
        layout.addWidget(step2)

        step3 = QGroupBox("步骤3: 上传成绩并生成报告")
        step3_layout = QVBoxLayout(step3)
        row3 = QHBoxLayout()
        self.workflow_score_label = QLabel("未选择成绩表")
        choose_score_btn = QPushButton("选择已填写成绩表")
        choose_score_btn.clicked.connect(self.workflow_choose_score)
        self.workflow_analyze_score_btn = QPushButton("读取并分析")
        self.workflow_analyze_score_btn.clicked.connect(self.workflow_analyze_scores)
        self.workflow_analyze_score_btn.setEnabled(False)
        row3.addWidget(self.workflow_score_label, 1)
        row3.addWidget(choose_score_btn)
        row3.addWidget(self.workflow_analyze_score_btn)
        step3_layout.addLayout(row3)

        row4 = QHBoxLayout()
        self.workflow_output_label = QLabel("未选择输出目录")
        choose_output_btn = QPushButton("选择输出目录")
        choose_output_btn.clicked.connect(self.workflow_choose_output)
        self.workflow_generate_reports_btn = QPushButton("批量生成PDF报告")
        self.workflow_generate_reports_btn.clicked.connect(self.workflow_generate_reports)
        self.workflow_generate_reports_btn.setEnabled(False)
        row4.addWidget(self.workflow_output_label, 1)
        row4.addWidget(choose_output_btn)
        row4.addWidget(self.workflow_generate_reports_btn)
        step3_layout.addLayout(row4)

        self.workflow_report_progress = QProgressBar()
        step3_layout.addWidget(self.workflow_report_progress)
        layout.addWidget(step3)

        layout.addStretch()
        return widget

    def _build_detail_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        detail_group = QGroupBox("细目表操作")
        detail_layout = QVBoxLayout(detail_group)
        row = QHBoxLayout()
        self.detail_label = QLabel("未选择细目表")
        choose_btn = QPushButton("选择细目表")
        choose_btn.clicked.connect(self.choose_detail_file)
        template_btn = QPushButton("生成并保存小题分模板")
        template_btn.clicked.connect(self.generate_template)
        row.addWidget(self.detail_label, 1)
        row.addWidget(choose_btn)
        row.addWidget(template_btn)
        detail_layout.addLayout(row)
        layout.addWidget(detail_group)

        score_group = QGroupBox("成绩上传与校验")
        score_layout = QVBoxLayout(score_group)
        row2 = QHBoxLayout()
        self.score_label = QLabel("未选择已填写小题分模板")
        choose_score_btn = QPushButton("选择成绩表")
        choose_score_btn.clicked.connect(self.choose_score_file)
        analyze_btn = QPushButton("读取并分析")
        analyze_btn.clicked.connect(self.analyze_scores)
        row2.addWidget(self.score_label, 1)
        row2.addWidget(choose_score_btn)
        row2.addWidget(analyze_btn)
        score_layout.addLayout(row2)
        layout.addWidget(score_group)

        layout.addStretch()
        return widget

    def _build_report_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("报告生成")
        group_layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.output_label = QLabel("未选择报告输出文件夹")
        choose_btn = QPushButton("选择输出文件夹")
        choose_btn.clicked.connect(self.choose_output_dir)
        self.generate_reports_btn = QPushButton("批量生成个人 PDF")
        self.generate_reports_btn.clicked.connect(self.generate_reports)
        row.addWidget(self.output_label, 1)
        row.addWidget(choose_btn)
        row.addWidget(self.generate_reports_btn)
        group_layout.addLayout(row)

        self.progress = QProgressBar()
        group_layout.addWidget(self.progress)
        layout.addWidget(group)

        layout.addStretch()
        return widget

    def _build_config_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("OpenAI兼容接口配置")
        form = QFormLayout(group)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("https://api.openai.com/v1/chat/completions")
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("gpt-4")
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 300)
        self.timeout_input.setValue(120)
        self.remember_key_input = QCheckBox("记住 API Key（会保存到本机配置文件）")
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_ai_config)
        form.addRow("API Key", self.api_key_input)
        form.addRow("API URL", self.api_url_input)
        form.addRow("模型名", self.model_input)
        form.addRow("超时秒数", self.timeout_input)
        form.addRow("", self.remember_key_input)
        form.addRow("", save_btn)
        layout.addWidget(group)

        layout.addStretch()
        return widget

    def _load_config_to_ui(self) -> None:
        self.api_key_input.setText(self.config.api_key)
        self.api_url_input.setText(self.config.base_url)
        self.model_input.setText(self.config.model)
        self.timeout_input.setValue(self.config.timeout)

    def _current_ai_config(self) -> AIConfig:
        return AIConfig(
            api_key=self.api_key_input.text().strip(),
            base_url=self.api_url_input.text().strip() or "https://api.openai.com/v1",
            model=self.model_input.text().strip(),
            timeout=self.timeout_input.value(),
        )

    def log(self, message: str) -> None:
        self.log_box.appendPlainText(message)

    def workflow_choose_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择PDF文件", "", "PDF 文件 (*.pdf)")
        if not path:
            return
        self.current_pdf_path = path
        self.workflow_pdf_label.setText(os.path.basename(path))
        self.workflow_analyze_btn.setEnabled(True)
        self.log(f"已选择PDF: {os.path.basename(path)}")

    def workflow_start_analysis(self) -> None:
        if not self.current_pdf_path:
            QMessageBox.warning(self, "警告", "请先选择PDF文件")
            return
        if not self.api_key_input.text().strip():
            QMessageBox.warning(self, "警告", "请先配置API Key")
            return

        api_url = self.api_url_input.text().strip() or "https://api.openai.com/v1/chat/completions"
        api_key = self.api_key_input.text().strip()
        model = self.model_input.text().strip() or "gpt-4"

        self.workflow_analyze_btn.setEnabled(False)
        self.workflow_progress.setValue(0)

        self.worker_thread = QThread()
        self.worker = PDFAnalysisWorker(self.current_pdf_path, api_url, api_key, model)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.workflow_on_progress)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self.workflow_on_analysis_finished)
        self.worker.error.connect(self.workflow_on_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def workflow_on_progress(self, current: int, total: int, name: str) -> None:
        self.workflow_progress.setMaximum(total)
        self.workflow_progress.setValue(current)
        if name:
            self.workflow_progress.setFormat(f"{current}/{total} {name}")

    def workflow_on_analysis_finished(self, data: list) -> None:
        self.analysis_data = data
        self.workflow_analyze_btn.setEnabled(True)
        self.workflow_save_table_btn.setEnabled(True)
        self.workflow_use_step1_btn.setEnabled(True)
        self.log(f"AI分析完成，共 {len(data)} 道题目")

    def workflow_on_error(self, error_msg: str) -> None:
        self.log(f"错误: {error_msg}")
        self.workflow_analyze_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", error_msg)

    def workflow_save_table(self) -> None:
        if not self.analysis_data:
            QMessageBox.warning(self, "警告", "没有可保存的分析数据")
            return

        path, _ = QFileDialog.getSaveFileName(self, "保存细目表", "细目表.xlsx", "Excel 文件 (*.xlsx)")
        if not path:
            return

        try:
            df_data = []
            for item in self.analysis_data:
                df_data.append({
                    "题号": item.get("题号", ""),
                    "题型": item.get("题型", ""),
                    "核心考点": item.get("核心考点", ""),
                    "分值": item.get("分值", 0),
                    "难度等级": item.get("难度等级", ""),
                    "易错点": item.get("易错点", "")
                })

            df = pandas.DataFrame(df_data)
            columns_order = ["题号", "题型", "核心考点", "分值", "难度等级", "易错点"]
            df = df[columns_order]
            df.to_excel(path, index=False, engine="openpyxl")

            self.log(f"细目表已保存: {path}")
            QMessageBox.information(self, "完成", f"细目表已保存：\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "错误", str(exc))

    def workflow_use_step1_table(self) -> None:
        if not self.analysis_data:
            QMessageBox.warning(self, "警告", "没有可用的分析数据")
            return
        try:
            self.items = [
                QuestionItem(
                    number=str(item.get("题号", "")),
                    question_type=str(item.get("题型", "")),
                    core_concept=str(item.get("核心考点", "")),
                    score=float(item.get("分值", 0)),
                    difficulty=str(item.get("难度等级", "")),
                    misconception=str(item.get("易错点", "")),
                )
                for item in self.analysis_data
            ]
            total = sum(item.score for item in self.items)
            self.workflow_detail_label.setText("步骤1细目表（已转换）")
            self.workflow_template_btn.setEnabled(True)
            self.log(f"已使用步骤1细目表：{len(self.items)} 题，满分 {total:.1f}")
        except Exception as exc:
            QMessageBox.critical(self, "转换错误", str(exc))

    def workflow_choose_detail(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择细目表", "", "Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            self.items = load_detail_table(path)
            self.detail_path = Path(path)
            total = sum(item.score for item in self.items)
            self.workflow_detail_label.setText(str(self.detail_path))
            self.workflow_template_btn.setEnabled(True)
            self.log(f"细目表读取成功：{len(self.items)} 题，满分 {total:.1f}")
        except Exception as exc:
            QMessageBox.critical(self, "细目表错误", str(exc))

    def workflow_generate_template(self) -> None:
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

    def workflow_choose_score(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择已填写小题分模板", "", "Excel 文件 (*.xlsx)")
        if not path:
            return
        self.score_path = Path(path)
        self.workflow_score_label.setText(str(self.score_path))
        self.workflow_analyze_score_btn.setEnabled(True)
        self.log(f"已选择成绩表: {os.path.basename(path)}")

    def workflow_analyze_scores(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "缺少细目表", "请先在步骤1或2中加载细目表")
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
            self.workflow_generate_reports_btn.setEnabled(True)
            QMessageBox.information(self, "完成", f"已完成 {len(self.analyses)} 名学生分析")
        except ValidationError as exc:
            QMessageBox.critical(self, "成绩表错误", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "分析失败", str(exc))

    def workflow_choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择报告输出文件夹")
        if not path:
            return
        self.output_dir = Path(path)
        self.workflow_output_label.setText(str(self.output_dir))

    def workflow_generate_reports(self) -> None:
        if not self.analyses:
            QMessageBox.warning(self, "缺少分析结果", "请先读取并分析成绩表")
            return
        if not getattr(self, 'output_dir', None):
            QMessageBox.warning(self, "缺少输出目录", "请先选择报告输出文件夹")
            return

        self.workflow_generate_reports_btn.setEnabled(False)
        self.workflow_report_progress.setValue(0)
        self.workflow_report_progress.setMaximum(len(self.analyses))

        self.report_worker_thread = QThread()
        self.report_worker = ReportWorker(self.analyses, self.output_dir, self._current_ai_config())
        self.report_worker.moveToThread(self.report_worker_thread)
        self.report_worker_thread.started.connect(self.report_worker.run)
        self.report_worker.progress.connect(self.workflow_report_on_progress)
        self.report_worker.log.connect(self.log)
        self.report_worker.finished.connect(self.workflow_report_on_finished)
        self.report_worker.finished.connect(self.report_worker_thread.quit)
        self.report_worker.finished.connect(self.report_worker.deleteLater)
        self.report_worker_thread.finished.connect(self.report_worker_thread.deleteLater)
        self.report_worker_thread.start()

    def workflow_report_on_progress(self, current: int, total: int, name: str) -> None:
        self.workflow_report_progress.setMaximum(total)
        self.workflow_report_progress.setValue(current)
        if name:
            self.workflow_report_progress.setFormat(f"{current}/{total} {name}")

    def workflow_report_on_finished(self, success: int, failed: int) -> None:
        self.workflow_generate_reports_btn.setEnabled(True)
        self.log(f"报告生成结束：成功 {success}，失败 {failed}")
        QMessageBox.information(self, "报告生成结束", f"成功 {success} 份，失败 {failed} 份")

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
        save_ai_config(self.config, self.remember_key_input.isChecked())
        self.log("OpenAI 兼容配置已保存")

    def generate_reports(self) -> None:
        if not self.analyses:
            QMessageBox.warning(self, "缺少分析结果", "请先读取并分析成绩表")
            return
        if not getattr(self, 'output_dir', None):
            QMessageBox.warning(self, "缺少输出目录", "请先选择报告输出文件夹")
            return
        self.generate_reports_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setMaximum(len(self.analyses))

        self.report_worker_thread = QThread()
        self.report_worker = ReportWorker(self.analyses, self.output_dir, self._current_ai_config())
        self.report_worker.moveToThread(self.report_worker_thread)
        self.report_worker_thread.started.connect(self.report_worker.run)
        self.report_worker.progress.connect(self.on_progress)
        self.report_worker.log.connect(self.log)
        self.report_worker.finished.connect(self.on_reports_finished)
        self.report_worker.finished.connect(self.report_worker_thread.quit)
        self.report_worker.finished.connect(self.report_worker.deleteLater)
        self.report_worker_thread.finished.connect(self.report_worker_thread.deleteLater)
        self.report_worker_thread.start()

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
