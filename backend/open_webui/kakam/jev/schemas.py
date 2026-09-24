"""Explicit TypeSafe v1 contracts. No Open WebUI dependencies."""

import json
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr, field_validator, model_validator

DEFAULT_BASE_URL = 'https://api.typesafe.ai/v1'
MODEL = 'jev-latest'
Description = str | dict[str, JsonValue] | list[JsonValue]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
Text = Annotated[str, Field(min_length=1, max_length=12000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)


def normalize_base_url(value: str) -> str:
    value = value.strip().rstrip('/')
    parts = urlsplit(value)
    if (
        parts.scheme not in ('http', 'https')
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise ValueError('请输入不含账号、查询参数或片段的 HTTP(S) Base URL')
    try:
        parts.port
    except ValueError:
        raise ValueError('Base URL 端口无效') from None
    path = parts.path.removesuffix('/systemone').rstrip('/')
    if not path.endswith('/v1'):
        path += '/v1'
    return urlunsplit((parts.scheme, parts.netloc, path, '', ''))


class ConnectionInput(Contract):
    base_url: str = Field(default=DEFAULT_BASE_URL, max_length=2048)
    api_key: SecretStr | None = None  # None preserves the saved key; never sent back.
    clear_api_key: bool = False

    _url = field_validator('base_url')(normalize_base_url)

    @field_validator('api_key')
    @classmethod
    def valid_key(cls, value):
        if value is not None:
            key = value.get_secret_value().strip()
            if not key or len(key) > 4096 or any(c.isspace() or ord(c) < 32 for c in key):
                raise ValueError('API Key 不能为空或含空白字符')
            return SecretStr(key)
        return value

    @model_validator(mode='after')
    def clear_or_set(self):
        if self.clear_api_key and self.api_key is not None:
            raise ValueError('不能同时设置和清除 API Key')
        return self


class ConnectionView(Contract):
    base_url: str
    has_api_key: bool
    model: str = MODEL


class ConnectionStatus(Contract):
    configured: bool
    connected: bool
    model: str = MODEL
    checked_at: float
    latency_ms: int | None = None
    message: str


class QuestionBase(Contract):
    instructions: Description

    @field_validator('instructions')
    @classmethod
    def nonempty(cls, value):
        if not value or (isinstance(value, str) and not value.strip()):
            raise ValueError('Question instructions must not be empty')
        return value


class NoulQuestion(QuestionBase):
    type: Literal['noul']
    criteria: dict[Literal['true', 'false'], Description] | None = None


class ChoiceQuestion(QuestionBase):
    type: Literal['choice']
    criteria: dict[str, Description | None] = Field(min_length=2, max_length=255)

    @field_validator('criteria')
    @classmethod
    def option_names(cls, value):
        if any(not key.strip() or len(key) > 200 for key in value):
            raise ValueError('Choice option names must be nonempty and at most 200 characters')
        return value


class ScoreQuestion(QuestionBase):
    type: Literal['score']
    criteria: list[Description] = Field(min_length=2, max_length=10)


Question = Annotated[NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator='type')]


class EvaluationRequest(Contract):
    state: Description
    model: Literal['jev-latest'] = MODEL
    questions: dict[str, Question] = Field(min_length=1, max_length=12)

    @model_validator(mode='after')
    def bounded(self):
        if not self.state:
            raise ValueError('State must not be empty')
        if any(not key.strip() or len(key) > 100 for key in self.questions):
            raise ValueError('Invalid question ID')
        if len(self.model_dump_json().encode()) > 96000:
            raise ValueError('Evaluation exceeds the 96 KB input limit')
        return self


class NoulAnswer(Contract):
    type: Literal['noul']
    noul: Probability


class Distribution(Contract):
    probabilities: dict[str, Probability] = Field(min_length=2, max_length=255)
    confidence: Probability | None = None

    @field_validator('probabilities')
    @classmethod
    def sum_to_one(cls, value):
        if abs(sum(value.values()) - 1) > 0.02:
            raise ValueError('Invalid probability distribution')
        return value


class ChoiceAnswer(Distribution):
    type: Literal['choice']
    choice: str


class ScoreAnswer(Distribution):
    type: Literal['score']
    score: float = Field(ge=0, le=9, allow_inf_nan=False, strict=True)
    legend: dict[str, str]


Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator='type')]


class Usage(Contract):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class EvaluationResponse(Contract):
    model: str
    answers: dict[str, Answer]
    usage: Usage

    def validate_for(self, request: EvaluationRequest):
        if self.answers.keys() != request.questions.keys():
            raise ValueError('Answer IDs do not match questions')
        for key, question in request.questions.items():
            answer = self.answers[key]
            if answer.type != question.type:
                raise ValueError('Answer type does not match question')
            if isinstance(question, ChoiceQuestion):
                if answer.probabilities.keys() != question.criteria.keys() or answer.choice not in question.criteria:
                    raise ValueError('Choice options do not match criteria')
            elif isinstance(question, ScoreQuestion):
                levels = {str(i) for i in range(len(question.criteria))}
                if answer.probabilities.keys() != levels or answer.legend.keys() != levels:
                    raise ValueError('Score levels do not match criteria')
                if answer.score > len(question.criteria) - 1:
                    raise ValueError('Score is outside its scale')
        return self


class QuestionDisplay(Contract):
    title: str = Field(min_length=1, max_length=1000)
    options: dict[str, str] = Field(default_factory=dict, max_length=255)

    @field_validator('options')
    @classmethod
    def labels(cls, value):
        if any(not label.strip() or len(label) > 2000 for label in value.values()):
            raise ValueError('Invalid display label')
        return value


class EvaluationPlan(Contract):
    kind: Literal['evaluation']
    state: Description
    questions: dict[str, Question]
    display: dict[str, QuestionDisplay]

    def evaluation(self) -> EvaluationRequest:
        return EvaluationRequest(state=self.state, questions=self.questions)

    @model_validator(mode='after')
    def matching_labels(self):
        request = self.evaluation()
        if self.display.keys() != request.questions.keys():
            raise ValueError('Every question needs a localized title')
        for key, question in request.questions.items():
            expected = (
                set(question.criteria)
                if isinstance(question, ChoiceQuestion)
                else {str(i) for i in range(len(question.criteria))}
                if isinstance(question, ScoreQuestion)
                else {'true', 'false'}
            )
            if set(self.display[key].options) != expected:
                raise ValueError('Display options must match every criterion')
        return self


class Clarification(Contract):
    kind: Literal['clarification']
    message: str = Field(min_length=1, max_length=4000)


Plan = Annotated[EvaluationPlan | Clarification, Field(discriminator='kind')]


class Message(Contract):
    role: Literal['user', 'assistant']
    content: Text


class TurnRequest(Contract):
    model_id: str = Field(min_length=1, max_length=256)
    messages: list[Message] = Field(min_length=1, max_length=40)

    @model_validator(mode='after')
    def conversation(self):
        if self.messages[-1].role != 'user' or not self.messages[-1].content.strip():
            raise ValueError('最后一条消息必须是非空的用户输入')
        if sum(len(m.content) for m in self.messages) > 24000:
            raise ValueError('当前对话超过 24,000 字符，请开始新对话')
        return self


class PolishedText(Contract):
    summary: str = Field(min_length=1, max_length=6000)


def json_data(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)
