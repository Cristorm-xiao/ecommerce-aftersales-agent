from pathlib import Path

import ingest_docs


def test_aftersales_loader_reads_only_policy_markdown(tmp_path):
    (tmp_path / 'return_policy.md').write_text('七天退货政策', encoding='utf-8')
    (tmp_path / 'old.txt').write_text('旧知识库', encoding='utf-8')
    docs = ingest_docs.load_documents(tmp_path, '*.md')
    assert len(docs) == 1
    assert docs[0].page_content == '七天退货政策'
    assert docs[0].metadata['source'] == 'return_policy.md'


def test_actual_policies_preserve_sources_after_splitting():
    folder = Path(__file__).resolve().parents[1] / 'sample_docs' / 'aftersales'
    docs = ingest_docs.load_documents(folder, '*.md')
    chunks = ingest_docs.split_documents(docs)
    assert len(docs) == 5
    assert {c.metadata['source'] for c in chunks} == {d.metadata['source'] for d in docs}
    assert all(c.page_content.strip() for c in chunks)
