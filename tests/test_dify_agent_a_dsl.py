import ast
import copy
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dify-agent-a-v2"))

import generate_dsl  # noqa: E402


DSL_PATH = ROOT / "dify-agent-a-v2" / "workflow.dsl.yaml"


class DifyAgentADslAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = yaml.safe_load(DSL_PATH.read_text(encoding="utf-8"))
        cls.dsl = generate_dsl.apply_deployment_updates(copy.deepcopy(cls.original))
        cls.nodes = cls.dsl["workflow"]["graph"]["nodes"]

    def test_all_requests_include_bearer_authorization(self):
        request_nodes = [
            node for node in self.nodes
            if "requests.post" in node["data"].get("code", "")
        ]
        self.assertEqual(11, len(request_nodes))
        for node in request_nodes:
            code = node["data"]["code"]
            with self.subTest(node=node["data"]["title"]):
                self.assertIn("def main(", code)
                self.assertIn("geo_api_token", code.split("def main(", 1)[1].split("):", 1)[0])
                self.assertIn('headers = {"Authorization": f"Bearer {geo_api_token}"}', code)
                self.assertIn("headers=headers", code)
                tree = ast.parse(code)
                calls = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "requests"
                    and node.func.attr == "post"
                ]
                self.assertTrue(calls)
                for call in calls:
                    keywords = {keyword.arg for keyword in call.keywords if keyword.arg}
                    self.assertIn("headers", keywords)

    def test_every_request_node_receives_token_from_config_node(self):
        for node in self.nodes:
            if "requests.post" not in node["data"].get("code", ""):
                continue
            selectors = [
                variable.get("value_selector")
                for variable in node["data"]["variables"]
                if variable.get("variable") == "geo_api_token"
            ]
            with self.subTest(node=node["data"]["title"]):
                self.assertEqual([["1729000000015", "geo_api_token"]], selectors)

    def test_config_node_passes_token_from_environment(self):
        config = next(node for node in self.nodes if node["id"] == "1729000000015")["data"]
        self.assertIn("geo_api_token", config["outputs"])
        self.assertIn(["env", "geo_api_token"], [
            variable["value_selector"] for variable in config["variables"]
        ])

    def test_environment_uses_public_origin_and_token_placeholder(self):
        env = {item["name"]: item for item in self.dsl["workflow"]["environment_variables"]}
        self.assertEqual("http://123.57.162.4", env["biz_api_base"]["value"])
        self.assertEqual("http://123.57.162.4", env["search_api_base"]["value"])
        self.assertEqual("CHANGE_ME_GEO_ACCESS_TOKEN", env["geo_api_token"]["value"])

    def test_generated_python_code_is_valid(self):
        for node in self.nodes:
            code = node["data"].get("code", "")
            with self.subTest(node=node["data"]["title"]):
                compile(code, f"<{node['data']['title']}>", "exec")

    def test_deployment_updates_are_idempotent(self):
        self.assertEqual(self.dsl, generate_dsl.apply_deployment_updates(self.dsl))
