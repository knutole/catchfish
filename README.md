## Usage

```python
import os, sys
from catchfish import Catchfish

# create instance
catchfish = Catchfish(
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

# load PGN
catchfish.load_games("tests/FTXCryptoCup2022.pgn")

# run engine evaluation
catchfish.evaluate()

# create analysis of raw evaluation
result = catchfish.analyse()

print("All done!", result)

```
