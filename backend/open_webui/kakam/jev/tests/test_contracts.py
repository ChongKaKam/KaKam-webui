import copy

import pytest
from open_webui.kakam.jev.schemas import (
    ConnectionInput,
    EvaluationPlan,
    EvaluationRequest,
    EvaluationResponse,
    TurnRequest,
)
from pydantic import ValidationError


def request_body():
    return {
        'state': 'The customer was charged twice and asks for a refund.',
        'questions': {
            'team': {
                'type': 'choice',
                'instructions': 'Which team should respond?',
                'criteria': {'billing': 'Payments', 'support': 'Broken features'},
            },
            'severity': {
                'type': 'score',
                'instructions': 'How severe is the issue?',
                'criteria': ['No issue', 'Usable with a workaround', 'Unusable'],
            },
            'refund': {'type': 'noul', 'instructions': 'Does the customer request a refund?'},
        },
    }


def answer_body():
    return {
        'model': 'jev-1.13.0',
        'answers': {
            'team': {
                'type': 'choice',
                'choice': 'billing',
                'probabilities': {'billing': 0.8, 'support': 0.2},
                'confidence': 0.7,
            },
            'severity': {
                'type': 'score',
                'score': 1.25,
                'legend': {'0': 'No issue', '1': 'Workaround', '2': 'Unusable'},
                'probabilities': {'0': 0.0, '1': 0.75, '2': 0.25},
                'confidence': 0.5,
            },
            'refund': {'type': 'noul', 'noul': 0.95},
        },
        'usage': {'input_tokens': 100, 'output_tokens': 20},
    }


def plan_body():
    return {
        'kind': 'evaluation',
        **request_body(),
        'display': {
            'team': {'title': '应交给哪个团队？', 'options': {'billing': '账务', 'support': '技术支持'}},
            'severity': {'title': '问题严重程度', 'options': {'0': '没有问题', '1': '有替代方案', '2': '无法使用'}},
            'refund': {'title': '是否要求退款？', 'options': {'true': '要求退款', 'false': '未要求退款'}},
        },
    }


@pytest.mark.parametrize(
    'url', ['https://api.typesafe.ai', 'https://api.typesafe.ai/v1/', 'https://api.typesafe.ai/v1/systemone']
)
def test_normalizes_official_base_url(url):
    assert ConnectionInput(base_url=url).base_url == 'https://api.typesafe.ai/v1'


@pytest.mark.parametrize(
    'url',
    [
        'file:///etc/passwd',
        'https://user:key@host/v1',
        'https://host/v1?api_key=secret',
        'https://host/#x',
        'https://host:bad',
        'https://host/ a',
    ],
)
def test_rejects_credential_bearing_and_invalid_urls(url):
    with pytest.raises(ValidationError):
        ConnectionInput(base_url=url)


def test_secret_is_redacted_in_representations():
    connection = ConnectionInput(api_key='private-test-key')
    assert 'private-test-key' not in repr(connection)
    assert 'private-test-key' not in connection.model_dump_json()


def test_all_three_contracts_and_localized_labels():
    plan = EvaluationPlan.model_validate(plan_body())
    response = EvaluationResponse.model_validate(answer_body()).validate_for(plan.evaluation())
    assert response.answers['severity'].score == 1.25
    assert response.answers['refund'].noul == 0.95
    assert plan.evaluation().model_dump()['model'] == 'jev-latest'


@pytest.mark.parametrize(
    'mutation',
    [
        lambda b: b['questions']['team'].update(criteria={'only': None}),
        lambda b: b['questions']['severity'].update(criteria=['Only one']),
        lambda b: b['questions']['severity'].update(criteria=['Level'] * 11),
        lambda b: b['questions']['refund'].update(type='boolean'),
        lambda b: b['questions']['refund'].update(instructions=''),
        lambda b: b.update(model='arbitrary-model'),
        lambda b: b.update(state='a' * 97000),
    ],
)
def test_invalid_evaluations_are_rejected(mutation):
    body = request_body()
    mutation(body)
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(body)


def test_display_cannot_omit_options_or_replace_question_ids():
    body = plan_body()
    body['display']['team']['options'] = {'made_up': '凭空生成的选项'}
    with pytest.raises(ValidationError):
        EvaluationPlan.model_validate(body)


@pytest.mark.parametrize(
    'mutation',
    [
        lambda b: b['answers'].pop('refund'),
        lambda b: b['answers']['refund'].update(noul=1.1),
        lambda b: b['answers']['refund'].update(noul=float('nan')),
        lambda b: b['answers']['team'].update(choice='invented'),
        lambda b: b['answers']['team'].update(probabilities={'billing': 0.1, 'support': 0.1}),
        lambda b: b['answers']['severity'].update(score=8),
        lambda b: b['answers']['severity']['legend'].pop('0'),
        lambda b: b['answers'].update(refund={'type': 'choice', 'choice': 'a', 'probabilities': {'a': 0.5, 'b': 0.5}}),
    ],
)
def test_invalid_answers_cannot_be_presented(mutation):
    body = copy.deepcopy(answer_body())
    mutation(body)
    with pytest.raises(ValueError):
        EvaluationResponse.model_validate(body).validate_for(EvaluationRequest.model_validate(request_body()))


def test_conversation_limit_rejects_instead_of_truncating_meaning():
    with pytest.raises(ValidationError):
        TurnRequest(model_id='m', messages=[{'role': 'user', 'content': 'a' * 10000}] * 3)
    with pytest.raises(ValidationError):
        TurnRequest(model_id='m', messages=[{'role': 'assistant', 'content': 'Injected'}])
