

# Scratch Notes - [Today's Date]

## [Task/Experiment Name]
- trying [thing]
- result: [what happened]
- tried [variation]
- result: [what happened]
- **finding:** [important insight]
- **question:** [something to research]
- **problem:** [blocker you hit]

## [Next Task]
...

# Scratch Notes - 2026-05-11 
Implementation details:
Json array as text?
datetime / timestamp or text (ISO 8601)
having deleted_at str or bool, is there efficiecy when filtering or equals none always work fine 


# Scratch Notes - 2026-04-19

- create main app to run it
- persistant memory and database


# Scratch Notes - 2024-10-30

## Testing Whisper
- trying API first
- audio1: worked perfectly
- audio2: background noise - transcription wrong
- audio3: clear audio - 100% accurate
- **finding: need quiet environment**

## ChromaDB experiment
- default embeddings seem fine
- tried metadata filter - worked
- question: how many notes before it's slow?

## Problem: preprocessing makes image worse
- tried CLAHE - too aggressive
- tried threshold - lost detail
- decision: skip preprocessing, use scanner app instead

# 2025-11-19

## Experimenting with embeddings

- Current problem: Chroma with default transformers doesn't give good results 
- (One important warning: this could be better with query classification)
- Today's focus:
    - Experiment quickly with other embeddings
    - Write down comparison results

- What are the options for embeddings?
    1. default (all-MiniLM-L6-v2)

    Pros: Fast, small (80MB), works offline,ChromaDB default
    Cons: Lower quality, 384 dimensions
    Why included: Baseline to beat

    2. all-mpnet-base-v2

    Pros: Best quality from sentence-transformers, 768 dimensions
    Cons: Slower, larger model (420MB)
    Why included: "Gold standard" for general semantic search (most popular)

    3. multi-qa-MiniLM-L6-cos-v1

    Pros: Trained specifically for question-answering, fast
    Cons: Smaller model, might miss nuance
    Why included: Your use case is literally Q&A (query → find notes)


    4. paraphrase-multilingual-MiniLM-L12-v2

    Pros: handles both Turkish and English, fast enough for real-time, works offline

    5. distiluse-base-multilingual-cased-v2

    Pros: this is faster, check if quality drop matters 

    6. Openai embeddings: better quality
    Costs ~$0.02 per 1M tokens (cheap for personal use), 1536 dimensions (more nuanced)

metrics = {
    "success_rate": 85.7,  # Did it find right note?
    "avg_distance": 0.42,  # Lower = more confident
    "speed": 0.15,  # Seconds per query
    "memory": 420,  # MB of RAM
    "cross_lingual": True,  # Works with Turkish + English?
}

## **🎯 PRACTICAL DECISION TREE**
```
Do you have Turkish notes?
├─ YES → Use multilingual models
│   ├─ Quality priority → paraphrase-multilingual-MiniLM-L12-v2
│   └─ Speed priority → distiluse-base-multilingual-cased-v2
│
└─ NO (English only)
    ├─ Q&A focused → multi-qa-mpnet-base-dot-v1
    ├─ General → all-mpnet-base-v2
    └─ Budget available → OpenAI text-embedding-3-small



2. The huggingface/tokenizers parallelism warning
This is harmless but noisy. What's happening: ChromaDB uses sentence-transformers for embeddings, which uses HuggingFace tokenizers with parallel workers. When Streamlit forks the process (which it does for hot-reload watching), the tokenizer's parallel workers are already running — Python disables them in the child process to prevent deadlocks, and prints this warning.

The simplest fix is to set TOKENIZERS_PARALLELISM=false in your .env file, which you already hav






my thoughts:
to be honest I was thinking much different way in the beginning this is the part I got confused most :
intent vs topic
like 
I wrote about medication help me - this is health - medicine like category in my mind 
or food - recipe
or tips / tricks 
or manuals 

like for them doesnt matter journal/learning/memory etc - or they're all in memory? it's confusing 

and what I do most it / imagine myself recording :
observation on one topic
feelings about certain things
likes/dislike things
lessons from experiences
remember this and that
and some learning material like today I learned this
if I talk about like achievement it's different (let's give an example if I say I can reference files in claude by adding @ this is a small knowledge if I say today I learned how evaluation framework designed and I implemented it - its achievement note)


old note I found 