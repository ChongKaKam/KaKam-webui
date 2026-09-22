"""Consume the UI override after upstream defaults, never forwarding private fields."""


def apply_effort_override(payload: dict) -> None:
    marker = '_kakam_reasoning_effort'
    if marker not in payload:
        return
    value = payload.pop(marker)
    payload.pop('reasoning_effort', None)
    # Some compatible connections use the Responses-style custom parameter.
    if isinstance(payload.get('reasoning'), dict):
        reasoning = {k: v for k, v in payload['reasoning'].items() if k != 'effort'}
        if reasoning:
            payload['reasoning'] = reasoning
        else:
            payload.pop('reasoning')
    if isinstance(value, str) and value in {'low', 'medium', 'high', 'xhigh', 'max'}:
        payload['reasoning_effort'] = value


def convert_effort_to_responses(payload: dict) -> None:
    """Responses uses reasoning.effort rather than reasoning_effort."""
    if 'reasoning_effort' in payload:
        value = payload.pop('reasoning_effort')
        reasoning = payload.get('reasoning')
        payload['reasoning'] = {
            **(reasoning if isinstance(reasoning, dict) else {}), 'effort': value
        }
