#!/usr/bin/env python3
"""Regression tests for deterministic Case validation rules."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_case.py"
SPEC = importlib.util.spec_from_file_location("validate_case", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


BASE_BODY = """| 字段 | 填写内容 |
|---|---|
| 品牌名称 | Example Brand |
| 业务模式 | B2C |
| 品类 | 彩色宝石首饰 |
| 目标客户 | 日常佩戴首饰的消费者 |
| 痛点 | 天然彩色宝石价格昂贵，日常佩戴款式有限 |
| 使用场景 | 日常通勤佩戴，休闲聚会搭配 |
| 产品特性 | 培育彩色宝石，可日常佩戴的设计 |
| 差异化优势 | 兼顾彩色宝石外观和日常价格带 |
| 适用边界 | 适合日常佩戴且不以天然宝石收藏为目标的人群 |
| 主题 | {topics} |
| 官方域名 | https://example.com |
| 竞品 1 | Competitor One |
| 竞品 1 官网域名 | https://one.example |
| 竞品 2 | Competitor Two |
| 竞品 2 官网域名 | https://two.example |
| 竞品 3 | Competitor Three |
| 竞品 3 官网域名 | https://three.example |
"""


class TopicValidationTest(unittest.TestCase):
    def errors_for(self, topics: str) -> list[str]:
        return MODULE.validate_case(1, BASE_BODY.format(topics=topics))

    def test_accepts_concise_topic_names(self) -> None:
        self.assertEqual([], self.errors_for("彩色宝石首饰，日常佩戴宝石首饰"))

    def test_accepts_coverage_topic_with_two_depth_topics(self) -> None:
        self.assertEqual(
            [],
            self.errors_for("彩色宝石首饰，日常佩戴宝石首饰，礼赠宝石首饰"),
        )

    def test_rejects_a_single_topic(self) -> None:
        errors = self.errors_for("彩色宝石首饰")
        self.assertTrue(any("主题数量必须为 2–3" in error for error in errors))

    def test_rejects_more_than_two_depth_topics(self) -> None:
        errors = self.errors_for("彩色宝石首饰，日常佩戴宝石首饰，礼赠宝石首饰，婚礼宝石首饰")
        self.assertTrue(any("主题数量必须为 2–3" in error for error in errors))

    def test_rejects_english_prompt_as_topic(self) -> None:
        errors = self.errors_for(
            "What are the best lab-grown colored gemstone jewelry brands for everyday wear?"
        )
        self.assertTrue(any("完整问题" in error for error in errors))
        self.assertTrue(any("Best / Top" in error for error in errors))

    def test_rejects_chinese_prompt_as_topic(self) -> None:
        errors = self.errors_for("哪些培育彩色宝石首饰品牌适合日常佩戴？")
        self.assertTrue(any("完整问题" in error for error in errors))


B2B_BODY = """| 字段 | 填写内容 |
|---|---|
| 品牌名称 | Example Travel |
| 业务模式 | B2B |
| 品类 | 企业差旅管理平台 |
| 目标企业画像 | 在亚太多个市场开展业务且有集中差旅管理需求的企业 |
| 目标客户 | 差旅负责人，采购负责人 |
| 痛点 | 多个市场的资源和服务差异大，跨市场政策执行复杂 |
| 使用场景 | 集中预订差旅，政策校验与审批 |
| 产品特性 | 全球库存与协议内容，政策审批工作流 |
| 差异化优势 | 集团供应链，本地服务网络 |
| 适用边界 | 适合有多市场差旅需求的企业；不面向个人休闲旅游 |
| 购买标准 | 内容源与渠道偏见，佣金与回扣披露，服务级别承诺 |
| 集成与兼容 | 对接财务与费用系统，对接 HR 系统 |
| 信任与合规 | 数据驻留，安全认证 |
| 地理与市场 | 亚太多个市场，中国相关行程 |
| 主题 | {topics} |
| 官方域名 | https://example.com |
| 竞品 1 | Competitor One |
| 竞品 1 官网域名 | https://one.example |
| 竞品 2 | Competitor Two |
| 竞品 2 官网域名 | https://two.example |
| 竞品 3 | Competitor Three |
| 竞品 3 官网域名 | https://three.example |
"""

B2B_TOPICS = "企业差旅管理，亚太多市场差旅运营"


class TargetCompanyProfileValidationTest(unittest.TestCase):
    def test_accepts_blank_profile_for_b2c(self) -> None:
        errors = MODULE.validate_case(1, BASE_BODY.format(topics="彩色宝石首饰，日常佩戴宝石首饰"))
        self.assertEqual([], errors)

    def test_rejects_profile_for_b2c(self) -> None:
        body = BASE_BODY.format(topics="彩色宝石首饰，日常佩戴宝石首饰").replace(
            "| 品类 | 彩色宝石首饰 |",
            "| 品类 | 彩色宝石首饰 |\n| 目标企业画像 | 三级医院呼吸科与 ICU |",
        )
        errors = MODULE.validate_case(1, body)
        self.assertTrue(any("纯 B2C" in error for error in errors))


class B2BAttributeFieldTest(unittest.TestCase):
    """B2B 专属字段：B2B 必填，纯 B2C 必须省略。"""

    def b2b_errors(self, body: str | None = None) -> list[str]:
        return MODULE.validate_case(1, (body or B2B_BODY).format(topics=B2B_TOPICS))

    def test_accepts_b2b_case_with_b2b_only_fields(self) -> None:
        self.assertEqual([], self.b2b_errors())

    def test_accepts_omitting_optional_geography(self) -> None:
        body = B2B_BODY.replace("| 地理与市场 | 亚太多个市场，中国相关行程 |\n", "")
        self.assertEqual([], self.b2b_errors(body))

    def test_rejects_b2b_without_buying_criteria(self) -> None:
        body = B2B_BODY.replace(
            "| 购买标准 | 内容源与渠道偏见，佣金与回扣披露，服务级别承诺 |\n", ""
        )
        self.assertTrue(
            any("B2B Case 必须填写购买标准" in error for error in self.b2b_errors(body))
        )

    def test_rejects_b2b_only_fields_for_b2c(self) -> None:
        body = BASE_BODY.format(topics="彩色宝石首饰，日常佩戴宝石首饰").replace(
            "| 品类 | 彩色宝石首饰 |",
            "| 品类 | 彩色宝石首饰 |\n"
            "| 购买标准 | 价格与性价比，口碑与复购 |\n"
            "| 集成与兼容 | 对接财务系统 |\n"
            "| 信任与合规 | 安全认证 |",
        )
        errors = MODULE.validate_case(1, body)
        for field in ("购买标准", "集成与兼容", "信任与合规"):
            self.assertTrue(
                any(f"纯 B2C Case 的{field}必须留空" in error for error in errors),
                f"{field} 未按纯 B2C 报错：{errors}",
            )

    def test_rejects_split_b2b_field_rows(self) -> None:
        body = B2B_BODY.replace(
            "| 购买标准 | 内容源与渠道偏见，佣金与回扣披露，服务级别承诺 |",
            "| 购买标准 1 | 内容源与渠道偏见 |\n| 购买标准 2 | 佣金与回扣披露 |",
        )
        errors = self.b2b_errors(body)
        self.assertTrue(any("必须合并到不带序号的同名字段" in error for error in errors))


class CaseParsingTest(unittest.TestCase):
    def parse(self, markdown: str) -> list[str]:
        return [match.group("body") for match in MODULE.CASE_RE.finditer(markdown)]

    def test_accepts_heading_without_sequence_number(self) -> None:
        cases = self.parse(f"## Example Brand\n\n{BASE_BODY.format(topics='彩色宝石首饰')}\n")
        self.assertEqual(1, len(cases))

    def test_keeps_legacy_numbered_heading_compatible(self) -> None:
        cases = self.parse(f"## 1. Example Brand\n\n{BASE_BODY.format(topics='彩色宝石首饰')}\n")
        self.assertEqual(1, len(cases))

    def test_ignores_explanatory_second_level_heading(self) -> None:
        markdown = (
            "## 字段填写说明\n\n这里是说明，不是 Case。\n\n"
            f"## Example Brand\n\n{BASE_BODY.format(topics='彩色宝石首饰')}\n"
        )
        cases = self.parse(markdown)
        self.assertEqual(1, len(cases))


if __name__ == "__main__":
    unittest.main()
