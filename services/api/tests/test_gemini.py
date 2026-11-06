import json
import httpx
import pytest
from app.integrations.model import ModelAdapter, ModelError


async def test_gemini_structured_wire_format_retry_and_usage(monkeypatch):
    real_client = httpx.AsyncClient
    requests = []
    def transport(request):
        requests.append(request)
        assert request.headers['x-goog-api-key'] == 'fixture-secret'
        assert 'fixture-secret' not in str(request.url)
        payload = json.loads(request.content)
        assert payload['generationConfig']['responseMimeType'] == 'application/json'
        assert 'responseJsonSchema' in payload['generationConfig']
        assert request.url.path.endswith('/models/test-model:generateContent')
        if len(requests) == 1:
            return httpx.Response(503, json={'error': {'message': 'temporarily busy'}})
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [
            {'thought': True, 'text': 'private reasoning'},
            {'text': json.dumps({'summary': 'Supported result', 'confidence': .8})}]}}],
            'usageMetadata': {'promptTokenCount': 42, 'candidatesTokenCount': 9}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs))
    adapter = ModelAdapter({'provider': 'gemini', 'base_url': 'https://provider.example/v1beta',
        'model': 'test-model', 'allow_external_private_data': True}, 'fixture-secret')
    output, usage = await adapter.generate('Use only facts', {'source': 'fictional'})
    assert output.summary == 'Supported result'
    assert usage['input_tokens'] == 42 and usage['output_tokens'] == 9
    assert len(requests) == 2


async def test_external_gemini_requires_explicit_data_consent():
    adapter = ModelAdapter({'provider': 'gemini', 'base_url': 'https://provider.example',
        'allow_external_private_data': False}, 'fixture-secret')
    with pytest.raises(ModelError, match='not authorized'):
        await adapter.generate('system', {'private': 'record'})
