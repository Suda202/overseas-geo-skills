def main(raw_text):
    import json, re

    if not isinstance(raw_text, str):
        raw_text = str(raw_text) if raw_text is not None else ""

    # ── 1. 剥掉 markdown 代码块 ──
    m = re.search(r'```(?:json)?\s*\n?(.*?)```', raw_text, re.S)
    if m:
        raw_text = m.group(1)

    raw_text = raw_text.strip()

    # ── 2. 尝试解析 JSON ──
    try:
        obj = json.loads(raw_text)
    except Exception as e:
        return {
            "result": {
                "case_path": "",
                "bank_path": "",
                "validate": {"valid": False, "errors": [f"LLM 输出不是合法 JSON: {e}"], "warnings": []}
            },
            "parse_error": str(e)
        }

    # ── 3. 处理数组/对象/result 三种形态 ──
    if isinstance(obj, list):
        obj = obj[0] if obj else {}
    if not isinstance(obj, dict):
        obj = {}
    if "result" in obj and isinstance(obj["result"], dict):
        obj = obj["result"]

    # ── 4. 补齐缺失字段 ──
    return {
        "result": {
            "case_path": str(obj.get("case_path") or ""),
            "bank_path": str(obj.get("bank_path") or ""),
            "validate": obj.get("validate") if isinstance(obj.get("validate"), dict) else {"valid": False, "errors": [], "warnings": []}
        },
        "parse_error": ""
    }
