from catchfish import Catchfish

catchfish = Catchfish(log_level="none")

game_key = "game:4402f8f49e699d8208ea6e7252e8d7f6"
evaluation = catchfish.get_evaluation_by_key(game_key)
print(evaluation)

# # test

# catchfish = Catchfish(
#     # defaults
#     limit_games=0,
#     stockfish_versions=[15],
#     # historical=True,
#     log_level="info",
#     threads=128,
#     hash_size=131072,
#     depth=20,
#     multi_pv=5,
#     num_nodes=["200M"],
#     mode="nodes",
#     engine_log_file="debug.log",
#     raw_output=True,
#     # cache=True,
# )

# print(catchfish.get_evaluation_by_key("game:5f7ddd291d6ae96ae6301287a6087832"))
