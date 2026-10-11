"""Retrieve demo shop policies from Pinecone; never fall back to local files."""
import config

_TOPICS = {
    'return': ('return_policy.md', '七天无理由退货条件、拆封、完好、配件和期限'),
    'quality': ('quality_issue_policy.md', '商品质量故障和人工审核'),
    'shipping': ('shipping_policy.md', '退货运费由谁承担和物流问题'),
    'refund': ('refund_process.md', '退款流程、工单状态和到账时间'),
    'escalation': ('escalation_policy.md', '转人工处理售后争议的条件'),
}


class PineconePolicyRetriever:
    def __init__(self, store=None):
        self._store = store

    def retrieve(self, topic: str, query: str = '') -> dict:
        result = {'demo': True, 'retrieval_backend': 'pinecone', 'topic': topic,
                  'index': config.AFTERSALES_PINECONE_INDEX, 'passages': []}
        if topic not in _TOPICS:
            return {**result, 'status': 'invalid_request', 'message': '未知政策主题。'}
        source, description = _TOPICS[topic]
        try:
            if self._store is None:
                if not config.PINECONE_API_KEY or not config.SILICONFLOW_API_KEY:
                    return {**result, 'status': 'unavailable', 'message': '政策检索服务未配置，暂时无法核实政策。'}
                from langchain_pinecone import PineconeVectorStore
                from llms import embeddings
                self._store = PineconeVectorStore(
                    index_name=config.AFTERSALES_PINECONE_INDEX, embedding=embeddings,
                    pinecone_api_key=config.PINECONE_API_KEY,
                    namespace=config.AFTERSALES_PINECONE_NAMESPACE,
                )
            matches = self._store.similarity_search_with_score(
                f'{description}\n{query.strip()}', k=config.RETRIEVER_K,
                filter={'source': {'$eq': source}},
            )
            passages = [
                {'source': doc.metadata.get('source'), 'chunk_id': doc.metadata.get('chunk_id'),
                 'score': float(score), 'text': doc.page_content}
                for doc, score in matches if doc.page_content.strip()
            ]
            if not passages:
                return {**result, 'status': 'not_found', 'message': '知识库没有返回该主题的政策，暂时无法核实。'}
            return {**result, 'status': 'ok', 'passages': passages}
        except Exception:
            # SDK errors may contain URLs, request headers or credentials.
            return {**result, 'status': 'unavailable', 'message': '政策检索服务暂时不可用，请稍后重试或联系人工。'}
