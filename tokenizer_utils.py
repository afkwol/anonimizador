import re
from dataclasses import dataclass
from typing import Callable, List, Tuple

# Simple tokenizer wrapper to allow swapping implementations later without changing callers.


@dataclass
class Token:
    text: str
    start: int
    end: int


class TokenizerWrapper:
    def __init__(self, tokenize_fn: Callable[[str], List[Token]]) -> None:
        self._tokenize_fn = tokenize_fn

    def encode_with_spans(self, text: str) -> List[Token]:
        return self._tokenize_fn(text)

    def count_tokens(self, text: str) -> int:
        return len(self._tokenize_fn(text))


def _simple_tokenize(text: str) -> List[Token]:
    pattern = re.compile(r"\S+\s*")
    tokens: List[Token] = []
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            tokens.append(Token(text=text[cursor:match.start()], start=cursor, end=match.start()))
        tokens.append(Token(text=match.group(0), start=match.start(), end=match.end()))
        cursor = match.end()
    if cursor < len(text):
        tokens.append(Token(text=text[cursor:], start=cursor, end=len(text)))
    return tokens


def build_tokenizer(name: str = "simple") -> TokenizerWrapper:
    # Placeholder for more advanced tokenizers (e.g., tiktoken). For now expose a simple one.
    return TokenizerWrapper(_simple_tokenize)


def split_with_overlap(
    text: str,
    tokenizer: TokenizerWrapper,
    max_prompt_tokens: int,
    system_prompt_tokens: int,
    overlap_tokens: int,
    safety_factor: float,
) -> List[Tuple[str, int, int, int, int]]:
    """
    Split text into chunks respecting a token budget with overlap.
    Returns tuples of (chunk_text, char_start, char_end, token_start, token_end).
    """
    spans = tokenizer.encode_with_spans(text)
    total_tokens = len(spans)

    available_tokens = max(1, int((max_prompt_tokens - system_prompt_tokens) * safety_factor))
    chunks: List[Tuple[str, int, int, int, int]] = []
    token_start = 0

    while token_start < total_tokens:
        token_end = min(token_start + available_tokens, total_tokens)
        window = spans[token_start:token_end]
        char_start = window[0].start
        char_end = window[-1].end
        chunk_text = text[char_start:char_end]
        chunks.append((chunk_text, char_start, char_end, token_start, token_end))

        if token_end >= total_tokens:
            break
        # Step back by overlap for the next window to keep context continuity.
        token_start = max(0, token_end - overlap_tokens)

    return chunks
