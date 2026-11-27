"""引用来源分类回归：每条都是 2026-11-18 复核时真实踩过的坑，改 sources.py / util.py 后必跑。

    cd .agents/skills/geo-metrics && python3 -m pytest -q tests/test_source_classification.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from geo_presales_core.sources import (  # noqa: E402
    _normalize_cache_keys,
    classify_source,
    low_volume_threshold,
    unjudged_coverage,
)
from geo_presales_core.util import registrable_domain  # noqa: E402


def kind(host, cache=None, **extra):
    return classify_source(host, {"domain_category_cache": cache or {}, **extra})["source_type"]


def basis(host, cache=None):
    return classify_source(host, {"domain_category_cache": cache or {}})["basis"]


class TestLongestMatch:
    def test_subdomain_override_beats_parent_regardless_of_order(self):
        # 2026-11-18 前按表顺序取第一个后缀命中，apple.com 排在 support.apple.com 前
        cache = {"apple.com": "other", "support.apple.com": "media_review"}
        assert kind("support.apple.com", cache) == "media_review"
        assert kind("www.apple.com", cache) == "other"

    def test_unjudged_subdomain_inherits_parent(self):
        assert kind("blog.example.com", {"example.com": "media_review"}) == "media_review"

    def test_cache_overrides_builtin_same_key(self):
        assert kind("reddit.com", {"reddit.com": "other"}) == "other"

    def test_more_specific_cache_beats_builtin_parent(self):
        assert kind("x.substack.com", {"x.substack.com": "media_review"}) == "media_review"
        assert kind("y.substack.com") == "ugc"


class TestCacheKeys:
    def test_www_and_mobile_prefixes_normalized(self):
        cache = _normalize_cache_keys({"www.jeffgeerling.com": "media_review", "m.dealmoon.com": "ugc"})
        assert kind("jeffgeerling.com", cache) == "media_review"
        assert kind("dealmoon.com", cache) == "ugc"

    def test_conflicting_duplicates_rejected(self):
        with pytest.raises(SystemExit):
            _normalize_cache_keys({"www.a.com": "ugc", "a.com": "other"})

    def test_public_suffix_key_rejected(self):
        with pytest.raises(SystemExit):
            _normalize_cache_keys({"com.my": "other"})


class TestInstitutionalSuffix:
    @pytest.mark.parametrize("host", ["nepis.epa.gov", "who.int", "ox.ac.uk", "ditp.go.th", "gov.uk",
                                      "nhs.uk", "gob.mx", "teqsa.gov.au", "publicationsduquebec.gouv.qc.ca"])
    def test_institutional(self, host):
        assert kind(host) == "institutional"

    @pytest.mark.parametrize("host", ["go.com", "edu.google.com", "gov.example.com"])
    def test_not_institutional(self, host):
        assert basis(host) == "unjudged"


class TestMultiTenant:
    def test_platform_root_is_one_site_but_tenants_are_separate(self):
        assert registrable_domain("marcushere.substack.com") == "marcushere.substack.com"
        assert registrable_domain("substack.com") == "substack.com"
        assert registrable_domain("user.github.io") == "user.github.io"
        assert registrable_domain("blog.example.com") == "example.com"
        assert registrable_domain("foo.bar.co.uk") == "bar.co.uk"

    def test_hosting_defaults_to_other(self):
        assert kind("someone.github.io") == "other"
        assert kind("x.workers.dev") == "other"


class TestOfficialRule:
    def test_target_and_competitor_from_objects(self):
        config = {"objects": [{"object_id": "target", "role": "target", "official_domains": ["example-brand.com"]},
                              {"object_id": "c1", "role": "competitor", "official_domains": ["rival-brand.com"]}],
                  "domain_category_cache": {"rival-brand.com": "media_review"}}
        assert classify_source("www.example-brand.com", config)["source_type"] == "brand_official"
        # 官网规则先于域名表：缓存里判成媒体也挡不住竞品官网
        assert classify_source("rival-brand.com", config)["source_type"] == "competitor_official"


class TestOfficialSameCategory:
    """2026-11-24 起只有同类品牌的官网才算「竞品网站」；2026-11-27 起开放品牌没写
    same_category 默认按同类算（词表开放品牌本来就摘自同品类回答），显式 false 的
    别的品类厂商（NVIDIA / CVAT / Microsoft 这类）才交给域名缓存判类。"""

    def _config(self, *objects, cache=None):
        return {"objects": list(objects), "domain_category_cache": cache or {}}

    def test_same_category_open_brand_is_competitor_official(self):
        config = self._config(
            {"object_id": "target", "role": "target", "official_domains": ["brand.com"]},
            {"object_id": "open-01", "role": "open", "same_category": True,
             "official_domains": ["shaip.com"]})
        assert classify_source("shaip.com", config)["source_type"] == "competitor_official"
        assert classify_source("shaip.com", config)["object_id"] == "open-01"

    def test_non_same_category_open_brand_falls_through_to_cache(self):
        config = self._config(
            {"object_id": "target", "role": "target", "official_domains": ["brand.com"]},
            {"object_id": "open-01", "role": "open", "same_category": False,
             "official_domains": ["nvidia.com"]},
            cache={"nvidia.com": "other"})
        result = classify_source("nvidia.com", config)
        assert result["source_type"] == "other"
        assert result["basis"] == "domain_rule"

    def test_non_same_category_open_brand_without_cache_is_unjudged(self):
        config = self._config(
            {"object_id": "target", "role": "target", "official_domains": ["brand.com"]},
            {"object_id": "open-01", "role": "open", "same_category": False,
             "official_domains": ["cvat.ai"]})
        result = classify_source("cvat.ai", config)
        assert result["source_type"] != "competitor_official"
        assert result["basis"] == "unjudged"

    def test_open_brand_without_same_category_is_competitor_official(self):
        # 2026-11-27：词表开放品牌默认按同类竞品算，只有显式 false 才排除
        config = self._config(
            {"object_id": "target", "role": "target", "official_domains": ["brand.com"]},
            {"object_id": "open-01", "role": "open", "official_domains": ["voices.com"]})
        result = classify_source("voices.com", config)
        assert result["source_type"] == "competitor_official"
        assert result["object_id"] == "open-01"

    def test_configured_competitor_unaffected(self):
        # 配置竞品没写 same_category 也仍是竞品网站
        config = self._config(
            {"object_id": "target", "role": "target", "official_domains": ["brand.com"]},
            {"object_id": "competitor-01", "role": "competitor",
             "official_domains": ["appen.com"]},
            cache={"appen.com": "other"})
        assert classify_source("appen.com", config)["source_type"] == "competitor_official"

    def test_target_still_brand_official(self):
        config = self._config(
            {"object_id": "target", "role": "target", "same_category": False,
             "official_domains": ["brand.com"]})
        assert classify_source("brand.com", config)["source_type"] == "brand_official"


class TestLowVolume:
    def test_threshold_scales_with_volume(self):
        assert low_volume_threshold(216) == 5
        assert low_volume_threshold(1000) == 10
        assert low_volume_threshold(14374) == 100

    def test_gate_counts_only_high_volume_unjudged(self):
        rows = [{"host": "big.com", "basis": "unjudged"}] * 20 + \
               [{"host": "tail.com", "basis": "unjudged"}] * 2 + \
               [{"host": "ok.com", "basis": "domain_rule"}] * 478
        cov = unjudged_coverage(rows)
        assert cov["low_volume_threshold"] == 5
        assert cov["unjudged_citations"] == 20
        assert cov["low_volume_citations"] == 2
        assert [c["domain"] for c in cov["candidates"]] == ["big.com"]
