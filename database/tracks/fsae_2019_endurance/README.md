# 2019 Endurance

OpenTRACK Shape workbook for the FSAE Michigan 2019 endurance layout.

| | |
|---|---|
| Name | 2019 Endurance |
| Site | USA / Detroit (workbook Info sheet) |
| Type | Closed |
| Length | 1823.31 m (sum of Shape `Section Length`) |
| Segments | 131 (23 straights, 51 left, 57 right) |

Source file: `2019_Endurance.xlsx` from the public OpenLAP forks
[brownfsae/OpenLAP-Lap-Time-Simulator](https://github.com/brownfsae/OpenLAP-Lap-Time-Simulator)
and [caltech-fsae/OpenLap](https://github.com/caltech-fsae/OpenLap) (identical bytes).

Convert and run:

```bash
python3 examples/python/fsae/xlsx_to_track.py \
    database/tracks/fsae_2019_endurance/2019_endurance.xlsx \
    -o database/tracks/fsae_2019_endurance/2019_endurance.xml

python3 examples/python/fsae/run_qss.py \
    --track-xlsx database/tracks/fsae_2019_endurance/2019_endurance.xlsx \
    -o qss_out
```
