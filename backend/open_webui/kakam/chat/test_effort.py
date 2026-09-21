import ast
from pathlib import Path
import unittest

from .effort import apply_effort_override, convert_effort_to_responses


class EffortOverrideTest(unittest.TestCase):
    def test_requests_without_ui_override_are_unchanged(self):
        payload = {'reasoning_effort': 'medium', 'model': 'custom'}
        apply_effort_override(payload)
        self.assertEqual(payload, {'reasoning_effort': 'medium', 'model': 'custom'})

    def test_unsupported_removes_defaults_and_responses_effort(self):
        payload = {'_kakam_reasoning_effort': None, 'reasoning_effort': 'high',
                   'reasoning': {'effort': 'high', 'summary': 'auto'}, 'temperature': 0.7}
        apply_effort_override(payload)
        self.assertEqual(payload, {'reasoning': {'summary': 'auto'}, 'temperature': 0.7})

    def test_valid_choice_overrides_model_default_and_removes_marker(self):
        for value in ['none', 'low', 'medium', 'high', 'xhigh', 'max']:
            with self.subTest(value=value):
                payload = {'_kakam_reasoning_effort': value, 'reasoning_effort': 'medium'}
                apply_effort_override(payload)
                self.assertEqual(payload, {'reasoning_effort': value})

    def test_invalid_values_never_reach_provider(self):
        for value in ['extra high', 'ultra', {}, [], 1]:
            with self.subTest(value=value):
                payload = {'_kakam_reasoning_effort': value, 'reasoning': {'effort': 'high'}}
                apply_effort_override(payload)
                self.assertEqual(payload, {})

    def test_responses_maps_effort_and_preserves_summary(self):
        payload = {'_kakam_reasoning_effort': 'xhigh',
                   'reasoning': {'effort': 'low', 'summary': 'auto'}}
        apply_effort_override(payload)
        convert_effort_to_responses(payload)
        self.assertEqual(payload, {'reasoning': {'effort': 'xhigh', 'summary': 'auto'}})

    def test_responses_unsupported_does_not_restore_effort(self):
        payload = {'_kakam_reasoning_effort': None, 'reasoning_effort': 'high'}
        apply_effort_override(payload)
        convert_effort_to_responses(payload)
        self.assertEqual(payload, {})

    def test_deepseek_max_survives_both_protocols(self):
        payload = {'_kakam_reasoning_effort': 'max', 'reasoning_effort': 'high'}
        apply_effort_override(payload)
        self.assertEqual(payload, {'reasoning_effort': 'max'})
        convert_effort_to_responses(payload)
        self.assertEqual(payload, {'reasoning': {'effort': 'max'}})

    def test_upstream_responses_conversion_integrates_effort(self):
        # Exercise the real upstream converter without importing the full server
        # (database, authentication, and inference dependencies are not needed).
        source = Path(__file__).resolve().parents[2] / 'routers' / 'openai.py'
        tree = ast.parse(source.read_text())
        converter = next(node for node in tree.body
                         if isinstance(node, ast.FunctionDef)
                         and node.name == 'convert_to_responses_payload')
        namespace = {'convert_effort_to_responses': convert_effort_to_responses}
        exec(compile(ast.Module(body=[converter], type_ignores=[]), str(source), 'exec'), namespace)
        payload = {'model': 'gpt-6-astra', 'messages': [{'role': 'user', 'content': 'Hello'}],
                   '_kakam_reasoning_effort': 'xhigh', 'reasoning_effort': 'low'}
        apply_effort_override(payload)
        result = namespace['convert_to_responses_payload'](payload)
        self.assertEqual(result['reasoning'], {'effort': 'xhigh'})
        self.assertNotIn('reasoning_effort', result)
        self.assertNotIn('_kakam_reasoning_effort', result)
        self.assertEqual(result['input'][0]['content'][0]['text'], 'Hello')


if __name__ == '__main__':
    unittest.main()
