"""正解(truth.json)と結果を比べて、音の高さ・長さの一致率を出す（順番合わせはDP）。"""
import json, sys

def align(a, b):
    n, m = len(a), len(b)
    D = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): D[i][0] = i
    for j in range(m+1): D[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            D[i][j] = min(D[i-1][j]+1, D[i][j-1]+1, D[i-1][j-1] + (a[i-1] != b[j-1]))
    return D[n][m]

truth = json.load(open(sys.argv[1]))["notes"]
res = json.load(open(sys.argv[2]))["notes"]
tp = [n["midi"] for n in truth]; rp = [n["midi"] for n in res]
dist = align(tp, rp)
pitch_acc = max(0, 1 - dist / len(tp))
same_len = len(tp) == len(rp)
dur_acc = (sum(abs(a["beats"] - b["beats"]) < 0.01 for a, b in zip(truth, res)) / len(tp)) if same_len else None
print(f"正解 {len(tp)}音 / 検出 {len(rp)}音")
print(f"音の高さ一致率: {pitch_acc*100:.0f}%")
print("音の長さ一致率: " + (f"{dur_acc*100:.0f}%" if dur_acc is not None else "（音数がずれたため算出せず）"))
