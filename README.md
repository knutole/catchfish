# Catchfish 🐳
A Python library that analyzes chess games utilizing the Stockfish engine, which could potentially detect circumstantial evidence of cheating. 

## Usage

### Setup ehemeral storage
The `Evaluation` class uses [Redis]([url](https://hub.docker.com/_/redis)) for storage of results, connecting to `localhost:6379` by default. Start Redis prior to  using `Catchfish`:
```bash
docker run --name some-redis -p 6379:6379 -d redis
```

### Run
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
