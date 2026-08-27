# How I work on this project — daily guide

Read at session start. Written 2026-07-13. Update only when a rule provably fails.

## Two tracks, both real goals
- **Build**: ship the app I actually use. **Learning**: go deep on concepts (evals, embeddings, retrieval).
- One session = one mode. Name it at the start.
- They feed each other: using the app daily → real queries in `search_log` → realistic eval data → meaningful experiments. Building without using starves the learning track.

## Day shape (10–11 → 17, not strict)
Morning block (~2 hrs): app/build track. Afternoon block (~2 hrs): eval/learning track. Last hour: buffer — overflow, daily capture in the app, wrap artifacts. One block = one mode.

## Build block (~2 hrs)
1. Pick **one** task from this week's list. The list is cut on Sunday and doesn't change midweek.
2. Bigger than one block, or more than 3 open decisions? Half-page spec first: `docs/design/_template.md`.
3. Mid-task ideas → one line in plan.md parking lot. Mid-task learning questions → one line in `docs/learning.md`. Then keep moving.
4. End: commit (ugly is fine) + decisions.md entry if a decision was made. A task isn't done until it's committed.

## Learning session
1. Start from a question in `docs/learning.md` — not from a blank "let me explore."
2. Big picture first (alternatives, tradeoffs, industry use), then *intentionally* choose which detail to go deep on.
3. Prefer a small experiment in `experiments/` over an hour of theory. Explain concepts back in my own words and let Claude poke holes.
4. End with **"wrap"**: Claude writes the artifact to `docs/learning/` (concepts, project relevance, open questions, interview Q&As).
5. A learning session without an artifact didn't happen.

## The on-path question (before starting anything)
Does this serve **(a)** me using the app this week, or **(b)** a learning artifact I could explain in an interview?
Neither → parking lot. Both tracks have a parking lot; nothing is lost, it's just not now.

## Debugging
15 timeboxed minutes with my own hypothesis first — read the log, read the traceback, guess. *Then* ask Claude, leading with my hypothesis.

## Weekly check-in (Sunday, ~20 min — template in plan.md)
The **only** place where milestones get re-cut, tasks get re-planned, and "is this still the right thing?" gets asked. Mid-week doubts get one line in the parking lot and an appointment here.

## Remember
- Clarity beats motivation. Avoidance means the task is too big or has undecided decisions — shrink it or spec it.
- Gaps happen (vacations are real). Restart with the smallest task on the list, not the most interesting one.
