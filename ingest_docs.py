from pathlib import Path
from hashlib import sha256
import argparse

from langchain_core import documents

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

import config
from llms import embeddings

DOCS_DIR = Path(__file__).resolve().parent / "sample_docs"

def load_documents(docs_dir: Path = DOCS_DIR, pattern: str = "*.txt") -> list[Document]:

    documents = []

    for path in sorted(docs_dir.glob(pattern)):
        text = path.read_text(encoding="utf-8").strip()

        if not text:
            print(f"跳过空文件：{path.name}")
            continue

        documents.append(
            Document(
                page_content = text,
                metadata = {"source" : path.name},
            )
        )
        print(f"读取：{path.name},{len(text)}个字符")

    if not documents:
        print("没有读取到任何文档")
        raise ValueError("没有读取到任何文档")

    return documents

def split_documents(documents: list[Document]) -> list[Document]:
    """Split documents into chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size = 500,
        chunk_overlap = 80,
        length_function = len,
        separators = ["\n\n", "\n","。","!","?",";", " ",""],
    )

    chunks = splitter.split_documents(documents)

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i

    return chunks

def main():
    parser = argparse.ArgumentParser(description="将本地文档分块并导入已存在的 Pinecone 索引")
    parser.add_argument("--aftersales", action="store_true", help="只导入 sample_docs/aftersales 下的 Markdown 政策")
    args = parser.parse_args()
    if not config.PINECONE_API_KEY:
        raise ValueError("请设置 PINECONE_API_KEY")
    if not config.SILICONFLOW_API_KEY:
        raise ValueError("请设置 SILICONFLOW_API_KEY")

    documents = load_documents(DOCS_DIR / "aftersales", "*.md") if args.aftersales else load_documents()
    chunks = split_documents(documents)

    print(f"\n共读取 {len(documents)} 个文件")
    print(f"切分得到 {len(chunks)} 个片段")
    print("\n第一个片段：")
    print(chunks[0].page_content)
    print("元数据：", chunks[0].metadata)

    #连接到索引
    vector_store = PineconeVectorStore(
        index_name = config.PINECONE_INDEX,
        embedding = embeddings,
        pinecone_api_key=config.PINECONE_API_KEY,
    )

    ids = [
        sha256(
            (
                f"{chunk.metadata['source']}\n"
                f"{chunk.metadata['chunk_id']}\n"
                f"{chunk.page_content}"
            ).encode("utf-8")
        ).hexdigest()
        for chunk in chunks
    ]

    vector_store.add_documents(documents=chunks, ids=ids)

    print(f"已将 {len(chunks)} 个片段添加到索引 {config.PINECONE_INDEX}")
    print("导入完成；重复导入相同内容会覆盖相同 ID 的片段。")

if __name__ == "__main__":
    main()
