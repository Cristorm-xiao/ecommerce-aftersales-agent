import json
from unittest.mock import Mock

from langchain_core.documents import Document

from aftersales import policies
from tools.aftersales import build_aftersales_tools


def test_topic_filter_and_returned_sources():
    store = Mock()
    store.similarity_search_with_score.return_value = [
        (Document(page_content='七天内可申请退货', metadata={'source': 'return_policy.md', 'chunk_id': 2}), 0.81)
    ]
    result = policies.PineconePolicyRetriever(store=store).retrieve('return', '拆封可以退吗')
    assert result['status'] == 'ok'
    assert result['retrieval_backend'] == 'pinecone'
    assert result['passages'][0]['source'] == 'return_policy.md'
    assert result['passages'][0]['text'] == '七天内可申请退货'
    assert store.similarity_search_with_score.call_args.kwargs['filter'] == {'source': {'$eq': 'return_policy.md'}}
    assert '拆封可以退吗' in store.similarity_search_with_score.call_args.args[0]


def test_empty_results_are_not_local_fallback():
    store = Mock()
    store.similarity_search_with_score.return_value = []
    assert policies.PineconePolicyRetriever(store=store).retrieve('shipping')['status'] == 'not_found'


def test_errors_do_not_expose_provider_message():
    store = Mock()
    store.similarity_search_with_score.side_effect = RuntimeError('secret-key-example')
    result = policies.PineconePolicyRetriever(store=store).retrieve('refund')
    assert result['status'] == 'unavailable'
    assert 'secret-key-example' not in json.dumps(result)


def test_invalid_topic_does_not_search():
    store = Mock()
    assert policies.PineconePolicyRetriever(store=store).retrieve('../../.env')['status'] == 'invalid_request'
    store.similarity_search_with_score.assert_not_called()


def test_policy_tool_uses_retriever_instead_of_local_files():
    service = Mock()
    retriever = Mock()
    retriever.retrieve.return_value = {'status': 'ok', 'passages': []}
    tool = next(t for t in build_aftersales_tools(service, policy_retriever=retriever) if t.name == 'lookup_policy')
    tool.invoke({'topic': 'quality', 'query': '鼠标坏了怎么办'})
    retriever.retrieve.assert_called_once_with('quality', '鼠标坏了怎么办')
    service.get_policy.assert_not_called()
