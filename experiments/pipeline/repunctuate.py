"""
Re-punctuate raw transcripts — isolates whether messy chunking results come
from the chunking algorithm or from run-on, under-punctuated voice-transcript
text feeding it. Verbatim wording only; adds punctuation/capitalization/
paragraph breaks, nothing else.
"""

from experiments.pipeline.embed import Usage

REPUNCTUATE_PROMPT = (
    "Add proper punctuation, capitalization, and paragraph breaks to this transcript.\n"
    "Do not change, add, remove, reorder, or paraphrase any words — output the exact "
    "same words, only with correct punctuation and sentence/paragraph boundaries.\n\n"
    "Transcript:\n{text}"
)

OPENAI_CHAT_MODEL = "gpt-4o-mini"
OPENAI_CHAT_PRICE_PER_1M = {"input": 0.15, "output": 0.60}


def repunctuate(text: str) -> tuple[str, Usage]:
    from openai import OpenAI

    response = OpenAI().chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[{"role": "user", "content": REPUNCTUATE_PROMPT.format(text=text)}],
        max_tokens=2048,
        temperature=0,
    )
    cleaned = response.choices[0].message.content.strip()
    in_tok, out_tok = response.usage.prompt_tokens, response.usage.completion_tokens
    cost = (in_tok * OPENAI_CHAT_PRICE_PER_1M["input"] + out_tok * OPENAI_CHAT_PRICE_PER_1M["output"]) / 1_000_000
    usage = Usage(provider="openai", model=OPENAI_CHAT_MODEL, input_tokens=in_tok, output_tokens=out_tok, cost_usd=cost)
    return cleaned, usage
