import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_domain_judgments.py"


def _collect(tmp_path: Path, urls: list[str]) -> Path:
    collect = tmp_path / "collect" / "scraper.chatgpt" / "US"
    collect.mkdir(parents=True)
    # 自检和报告同口径：只数有效回答里的引用，所以夹具要带正文
    payload = {"task_result": {
        "result_text": "Here is a reasonably long answer that lists several options and explains the trade-offs.",
        # 正文里实际引用了才算（cited_count，2026-10-13 起的格式）；只出现在来源清单里的不算
        "content_references": [{"url": u, "cited_count": 1} for u in urls]}}
    (collect / "0001.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path / "collect"


def _run(tmp_path: Path, collect: Path, cache: dict, lexicon: dict | None, reasons: dict | None):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    args = [sys.executable, "-I", str(SCRIPT), "--collect", str(collect), "--cache", str(cache_path),
            "--reasons", str(tmp_path / "reasons.json")]
    if lexicon is not None:
        lex_path = tmp_path / "lex.json"
        lex_path.write_text(json.dumps(lexicon, ensure_ascii=False), encoding="utf-8")
        args += ["--lexicon", str(lex_path)]
    if reasons is not None:
        (tmp_path / "reasons.json").write_text(json.dumps(reasons, ensure_ascii=False), encoding="utf-8")
    return subprocess.run(args, capture_output=True, text=True)


def test_unjudged_top_domain_fails(tmp_path):
    # 达到长尾阈值（下限 5 次）的未判读域名必须判
    collect = _collect(tmp_path, ["https://unknown-site.com/a"] * 5)
    result = _run(tmp_path, collect, cache={}, lexicon=None, reasons=None)
    assert result.returncode == 1
    assert "未判读" in result.stdout


def test_low_volume_unjudged_domain_does_not_block(tmp_path):
    # 不足长尾阈值的未判读域名归「其他」、单独提示，不拦
    collect = _collect(tmp_path, ["https://unknown-site.com/a"] * 4 + ["https://media.example/b"] * 20)
    result = _run(tmp_path, collect, cache={"media.example": "media_review"}, lexicon=None, reasons=None)
    assert result.returncode == 0, result.stdout
    assert "长尾未判" in result.stdout


def test_other_without_reason_fails(tmp_path):
    collect = _collect(tmp_path, ["https://vendor.example/a"])
    result = _run(tmp_path, collect, cache={"vendor.example": "other"}, lexicon=None, reasons={})
    assert result.returncode == 1
    assert "没有理由" in result.stdout


def test_brand_subdomain_counts_as_brand(tmp_path):
    collect = _collect(tmp_path, ["https://guides.brand.com/page"] * 5)
    lexicon = {"brands": [{"name": "Brand", "aliases": ["Brand"], "official_domains": ["brand.com"]}]}
    result = _run(tmp_path, collect, cache={}, lexicon=lexicon, reasons={})
    assert result.returncode == 0, result.stdout
    assert "通过" in result.stdout


def test_other_share_limit(tmp_path):
    urls = ["https://vendor.example/a", "https://media.example/b"]
    collect = _collect(tmp_path, urls)
    result = _run(tmp_path, collect, cache={"vendor.example": "other", "media.example": "media_review"},
                  lexicon=None, reasons={"vendor.example": "小工具站，不属六类"})
    assert result.returncode == 1
    assert "超过上限" in result.stdout
