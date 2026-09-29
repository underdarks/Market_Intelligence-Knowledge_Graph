from market_intelligence_knowledge_graph.config.env import require_int


def get_search_top_k() -> int:
    return require_int("SEARCH_TOP_K")


def get_question_max_length() -> int:
    return require_int("ASK_QUESTION_MAX_LENGTH")
