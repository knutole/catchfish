from catchfish import Catchfish, Analysis
import json

log_level = "none"
catchfish = Catchfish(log_level=log_level)

game = {
    "description": "Le, Quang Liem vs Carlsen, Magnus 2022.08.18 1/2-1/2 FTX Crypto Cup 2022",
    "key": "game:f964dc71653044e7408a9f68da0b7403",
}

evaluation = catchfish.get_evaluation_by_key(game["key"])

a = Analysis(evaluation=json.loads(evaluation), log_level=log_level)
result = a.analyse(return_move_data=True)
print(result)
