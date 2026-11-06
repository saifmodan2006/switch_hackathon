import asyncio
import io
import math
import re
import zipfile
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select, text as sql_text
from app.models.domain import Knowledge, Chunk
from app.core.config import settings


def extract(filename: str, data: bytes):
    suffix = Path(filename).suffix.lower()
    if suffix not in {'.txt', '.md', '.pdf', '.docx'}:
        raise HTTPException(415, 'Upload PDF, DOCX, TXT or Markdown')
    if len(data) > settings().upload_max_bytes:
        raise HTTPException(413, 'File exceeds 10 MB limit')
    try:
        if suffix in {'.txt', '.md'}:
            text = data.decode('utf-8-sig')
        elif suffix == '.pdf':
            if not data.startswith(b'%PDF'):
                raise ValueError('Invalid PDF signature')
            from pypdf import PdfReader
            pdf = PdfReader(io.BytesIO(data))
            if len(pdf.pages) > 200:
                raise HTTPException(413, 'PDF exceeds 200 pages')
            text = '\n'.join(f'[Page {i+1}]\n{page.extract_text() or ""}' for i, page in enumerate(pdf.pages))
        else:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(x.file_size for x in archive.infolist()) > 30 * 1024 * 1024:
                    raise HTTPException(413, 'DOCX expands beyond safe processing limit')
            from docx import Document
            text = '\n'.join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, 'Document could not be safely extracted') from exc
    if len(text.strip()) < 20:
        raise HTTPException(422, 'No usable text. Scanned PDFs require a separately configured OCR service.')
    return text[:2_000_000]


_embedder = None


def embed(texts):
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(settings().embedding_model)
    return _embedder.encode(texts, normalize_embeddings=True).tolist()


async def index_document(db, document):
    texts = [document.text[i:i+1200] for i in range(0, len(document.text), 1000)]
    vectors = await asyncio.to_thread(embed, texts) if settings().embeddings_enabled else [None] * len(texts)
    for i, (text, vector) in enumerate(zip(texts, vectors)):
        chunk=Chunk(org_id=document.org_id, document_id=document.id, position=i, content=text, embedding=vector)
        db.add(chunk)
        if vector is not None and db.bind.dialect.name=='postgresql':
            if len(vector)!=384:
                raise HTTPException(422,'PostgreSQL vector index requires 384-dimensional embeddings; use the documented default model')
            await db.flush()
            import json
            await db.execute(sql_text('UPDATE document_chunks SET vector_embedding=CAST(:vector AS vector) WHERE id=:id AND org_id=:org'),
                             {'vector':json.dumps(vector),'id':chunk.id,'org':document.org_id})


async def search(db, org_id, query, limit=8):
    if settings().embeddings_enabled and db.bind.dialect.name=='postgresql':
        import json
        vector=(await asyncio.to_thread(embed,[query]))[0]
        result=await db.execute(sql_text('''SELECT c.document_id,k.title,c.content,c.position,
            1-(c.vector_embedding <=> CAST(:vector AS vector)) AS score
            FROM document_chunks c JOIN knowledge_documents k ON k.id=c.document_id
            WHERE c.org_id=:org AND k.org_id=:org AND c.vector_embedding IS NOT NULL
            ORDER BY c.vector_embedding <=> CAST(:vector AS vector) LIMIT :limit'''),
            {'vector':json.dumps(vector),'org':org_id,'limit':limit})
        found=[{'document_id':r.document_id,'title':r.title,'snippet':r.content,'location':f'chunk {r.position+1}',
                'score':round(float(r.score),4),'method':'semantic-pgvector'} for r in result]
        if found:return found
    rows = (await db.execute(select(Chunk, Knowledge.title).join(Knowledge, Chunk.document_id == Knowledge.id)
                            .where(Chunk.org_id == org_id, Knowledge.org_id == org_id).limit(10000))).all()
    words = set(re.findall(r'\w+', query.lower()))
    vector = (await asyncio.to_thread(embed, [query]))[0] if settings().embeddings_enabled else None
    found = []
    for chunk, title in rows:
        if vector is not None and chunk.embedding:
            score = sum(a*b for a,b in zip(vector, chunk.embedding))
            method = 'semantic'
        else:
            score = len(words & set(re.findall(r'\w+', chunk.content.lower()))) / max(len(words), 1)
            method = 'keyword'
        if score > 0:
            found.append({'document_id': chunk.document_id, 'title': title, 'snippet': chunk.content,
                          'location': f'chunk {chunk.position + 1}', 'score': round(score, 4), 'method': method})
    return sorted(found, key=lambda x: x['score'], reverse=True)[:limit]
