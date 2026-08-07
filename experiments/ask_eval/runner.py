import asyncio

from experiments.ask_eval.collector import collect
from experiments.ask_eval.grader import grade


def run():
    path = collect()
    asyncio.run(grade(path))


if __name__ == "__main__":
    run()