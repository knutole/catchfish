# Catchfish 🐳
A Python library that analyzes chess games utilizing the Stockfish engine, which could potentially detect circumstantial evidence of cheating. 

## Usage

```python
from catchfish import Catchfish

# create instance
fish = Catchfish(
    # defaults
    limit_games=0,
    stockfish_versions=[15],
    historical=True,
    log_level="info",
    threads=32,
    hash=1024,
    depth=20,
    multi_pv=3,
    num_nodes=["3M"],
    mode="nodes",
    engine_log_file="debug.log",
)

# load PGN with multiple games
fish.load_games("tests/FTXCryptoCup2022.pgn")

# run engine evaluation
fish.evaluate()

# create analysis of raw evaluation
analysis = fish.analyse()

# use in ObservableHQ.com 🐳
print(analysis)

```
