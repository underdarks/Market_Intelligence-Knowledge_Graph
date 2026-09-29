"""
filing_text 컬렉션에 방금 적재된 44건의 텍스트 길이를 회사×섹션별로 확인.
특히 지난번 실패했던 SK하이닉스/한미반도체의 risk_factors가
비정상적으로 짧게 잘린 건 아닌지 확인하는 게 목적.
"""

from market_intelligence_knowledge_graph.config.mongo_db import get_mongodb

db = get_mongodb()
collection = db["filing_text"]

docs = list(collection.find({}, {"entity_id": 1, "source": 1, "section_id": 1, "section_title": 1, "text": 1}))

print(f"{'entity_id':<20} {'section_id':<25} {'section_title':<30} {'길이':>8}")
print("-" * 90)

for doc in sorted(docs, key=lambda d: (d["entity_id"], d["section_id"])):
    text_len = len(doc.get("text", ""))
    title = doc.get("section_title", "")[:28]
    print(f"{doc['entity_id']:<20} {doc['section_id']:<25} {title:<30} {text_len:>8}")


doc = collection.find_one({"entity_id": "dart:00161383", "section_id": "business"})
text = doc["text"]
print("=== 앞부분 ===")
print(text[:300])
print("\n=== 끝부분 ===")
print(text[-300:])
