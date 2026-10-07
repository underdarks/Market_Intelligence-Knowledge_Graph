from market_intelligence_knowledge_graph.rag.retrieve.supply_chain_impact_mapping import (
    ProcessImpactRow,
    SupplyImpactRow,
    process_row_to_item,
    supply_row_to_item,
    weakest_link_score,
)


# ---------------------------------------------------------------- 헬퍼
def process_row(**overrides) -> ProcessImpactRow:
    """경로 A 기본 행 + 필요한 필드만 덮어쓰기.
    {**base, **overrides}: 두 dict를 합치되 같은 키는 뒤쪽(overrides) 값이 이김"""
    base = dict(
        source_name="TSMC",
        affected_entity_id="cik:0001045810",
        affected_name="NVIDIA",
        affected_relations=["DESIGNS"],
        process_id="process:3nm",
        product_id="product:ai_gpu",
        process_name="3nm 제조",
        product_name="AI GPU",
        hops=3,
        confidences=["stated", "disclosed", "disclosed"],
    )
    return ProcessImpactRow(**{**base, **overrides})


def supply_row(**overrides) -> SupplyImpactRow:
    """경로 B 기본 행 + 필요한 필드만 덮어쓰기."""
    base = dict(
        source_name="TSMC",
        relation_id="r1",
        affected_entity_id="cik:0001730168",
        affected_name="Broadcom",
        process_type="wafer_fabrication",
        dependency_pct=0.95,
        confidence="disclosed",
        as_of_date="2025-12-18",
    )
    return SupplyImpactRow(**{**base, **overrides})


# ---------------------------------------------------------------- 점수 (가장 약한 고리)
def test_weakest_link_is_min() -> None:
    assert weakest_link_score(["stated", "inferred"]) == 0.5


def test_null_confidence_scores_zero() -> None:
    # 근거 등급이 없는 관계가 섞이면 경로 전체를 최저점으로
    assert weakest_link_score(["stated", None]) == 0.0


def test_empty_confidences_zero() -> None:
    assert weakest_link_score([]) == 0.0


# ---------------------------------------------------------------- 경로 A (공정 경유)
def test_process_sentence_uses_relation_label() -> None:
    item = process_row_to_item(process_row())
    assert "NVIDIA가 설계함" in item.content  # DESIGNS -> 설계
    assert item.source_type == "graph_traversal"


def test_process_both_relations_in_one_sentence() -> None:
    # SELLS·DESIGNS가 같이 오면 한 문장으로, 순서는 입력 순서와 무관하게 고정 (판매 -> 설계)
    item = process_row_to_item(process_row(affected_relations=["DESIGNS", "SELLS"]))
    assert "NVIDIA가 판매·설계함" in item.content


def test_process_null_confidence_shown_as_unknown() -> None:
    item = process_row_to_item(process_row(confidences=[None, "stated", "disclosed"]))
    assert "미상 → stated → disclosed" in item.content
    assert item.score == 0.0


def test_process_quote_and_url() -> None:
    item = process_row_to_item(process_row(evidence_quote="AI GPU requires 3nm", evidence_url="https://ir.example"))
    assert '근거: "AI GPU requires 3nm"' in item.content
    assert item.source_url == "https://ir.example"


def test_process_doc_id_uses_domain_ids() -> None:
    # 이름이 아니라 도메인 ID로: 표기가 바뀌어도 doc_id 유지. 관계 유형은 행이 묶여서 빠짐
    item = process_row_to_item(process_row())
    assert item.doc_id == "supply_chain:process:cik:0001045810:process:3nm:product:ai_gpu"


# ---------------------------------------------------------------- 경로 B (위탁 관계)
def test_supply_ratio_formatted_as_percent() -> None:
    assert "의존도 95%" in supply_row_to_item(supply_row()).content  # 0.95 -> 95%


def test_supply_full_dependency() -> None:
    assert "의존도 100%" in supply_row_to_item(supply_row(dependency_pct=1.0)).content


def test_supply_null_dependency_undisclosed() -> None:
    # stated(수치 없음)면 의존도는 None -> "미공개"
    item = supply_row_to_item(supply_row(dependency_pct=None, confidence="stated"))
    assert "의존도 미공개" in item.content


def test_supply_doc_id_from_relation_id() -> None:
    assert supply_row_to_item(supply_row()).doc_id == "supply_chain:supply:r1"
