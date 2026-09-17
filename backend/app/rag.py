import math
import re
from collections import Counter
from typing import Optional


_RAG_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "of", "in", "on", "at", "to", "for", "with", "as", "by",
    "and", "or", "but", "not",
    "that", "this", "it", "its", "from", "he", "she", "they", "we", "you", "i",
    "his", "her", "their", "our", "your",
    "no", "do", "does", "did",
    "have", "has", "had",
    "there", "either", "already", "will", "currently", "get", "like",
    "one", "those", "about", "follow", "if", "then", "because",
    "so", "must", "still", "very", "also", "only", "which",
    "under", "up", "down",
}


def _rag_tokenize(text: str) -> list:
    words = re.findall(r"[^\W\d_]+", (text or "").lower(), flags=re.UNICODE)
    return [w for w in words if len(w) > 1 and w not in _RAG_STOPWORDS]


def _rag_cosine_score(card_text: str, context_counter: Counter, idf: dict = None) -> float:
    card_counter = Counter(_rag_tokenize(card_text))
    if not card_counter or not context_counter:
        return 0.0
    common = set(card_counter) & set(context_counter)
    dot = 0.0
    for w in common:
        w_idf = idf.get(w, 1.0) if idf else 1.0
        dot += (card_counter[w] * w_idf) * (context_counter[w] * w_idf)
    if dot == 0:
        return 0.0
    card_norm_sq = sum((v * (idf.get(w, 1.0) if idf else 1.0))**2 for w, v in card_counter.items())
    ctx_norm_sq = sum((v * (idf.get(w, 1.0) if idf else 1.0))**2 for w, v in context_counter.items())
    if card_norm_sq == 0 or ctx_norm_sq == 0:
        return 0.0
    return dot / (math.sqrt(card_norm_sq) * math.sqrt(ctx_norm_sq))


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def select_relevant_lore_cards(lore_cards: list, context_text: str,
                                max_tokens: Optional[int]) -> list:
    pinned_cards = [c for c in lore_cards if c.get("is_pinned")]
    unpinned_cards = [c for c in lore_cards if not c.get("is_pinned")]

    total_lore_tokens = sum(estimate_tokens(c.get("content", "") + " " + c.get("name", "")) for c in lore_cards)

    if max_tokens is None or total_lore_tokens <= max_tokens:
        return lore_cards

    context_counter = Counter(_rag_tokenize(context_text))
    if not context_counter:
        result = list(pinned_cards)
        current_tokens = sum(estimate_tokens(c.get("content", "") + " " + c.get("name", "")) for c in result)
        for c in unpinned_cards:
            c_toks = estimate_tokens(c.get("content", "") + " " + c.get("name", ""))
            if current_tokens + c_toks > max_tokens and current_tokens > 0:
                break
            result.append(c)
            current_tokens += c_toks
        return result

    df = Counter()
    for c in lore_cards:
        unique_words = set(_rag_tokenize(c.get("content", "") + " " + c.get("name", "")))
        for w in unique_words:
            df[w] += 1

    total_docs = len(lore_cards)
    idf = {w: math.log(total_docs / (1 + count)) for w, count in df.items()}

    scored = [
        (_rag_cosine_score(c.get("content", "") + " " + c.get("name", ""), context_counter, idf), idx, c)
        for idx, c in enumerate(unpinned_cards)
    ]
    scored.sort(key=lambda t: (-t[0], t[1]))

    result = list(pinned_cards)
    current_tokens = sum(estimate_tokens(c.get("content", "") + " " + c.get("name", "")) for c in result)

    keep_unpinned_ids = set()
    for score, idx, c in scored:
        c_toks = estimate_tokens(c.get("content", "") + " " + c.get("name", ""))
        if current_tokens + c_toks > max_tokens and current_tokens > 0:
            break
        keep_unpinned_ids.add(c["id"])
        current_tokens += c_toks

    return [c for c in lore_cards if c.get("is_pinned") or c["id"] in keep_unpinned_ids]


def build_rag_context_text(recent_chapters: list, user_input: str, running_summary: str = "") -> str:
    parts = [running_summary] if running_summary else []
    parts += [ch.get("chapter_text", "") for ch in recent_chapters]
    parts.append(user_input or "")
    return " ".join(parts)
