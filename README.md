## Usage

```python
import os, sys
from catchfish import Analysis, RedisStore, Game, Games, Evaluation, StockfishVariant

# read games
path = "tests/test.pgn"
file = os.path.join(os.path.dirname(__file__), path)
games = Games(path=file, limit_games=limit_games, validate_fen=True, debug_level=2)
print("Valid games", games.get_valid_games_count())
print("Invalid games", games.get_invalid_games_count())

# prepare evaluation
evaluation = Evaluation(
    games=games,
    stockfish_versions=[15, 12],
    historical=True,
    debug_level=2,
    threads=128, # num cpu's
    hash=32768,
    depth=20,
    multi_pv=10, # how many multipv lines to render
    num_nodes=[
        "50M"
        "100M",
    ],
    mode="nodes", # stockfish mode: [nodes, depth, time]
    engine_log_file="debug.log",
)

# start evaluation (stockfish starts running)
keys = evaluation.evaluate()

# returns redis keys for evaluated games
print("All done!", evaluation.get_result_keys())

# analyse evaluated games
a = Analysis(evaluation=keys[0], debug_level=debug_level)
result = a.analyse()
print("All done!", result)

```
