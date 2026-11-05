"""テスト音源の合成：ベートーヴェン「歓喜の歌」（パブリックドメイン）
メロディ＋伴奏（和音）＋ビブラート付きで、正解データ(JSON)も書き出す。"""
import json, sys
import numpy as np, soundfile as sf

SR = 22050
BPM = 100
BEAT = 60 / BPM
# (MIDI番号, 拍数)  C4=60  ハ長調
MELODY = [
    (64,1),(64,1),(65,1),(67,1),(67,1),(65,1),(64,1),(62,1),
    (60,1),(60,1),(62,1),(64,1),(64,1.5),(62,0.5),(62,2),
    (64,1),(64,1),(65,1),(67,1),(67,1),(65,1),(64,1),(62,1),
    (60,1),(60,1),(62,1),(64,1),(62,1.5),(60,0.5),(60,2),
]
# 1小節(4拍)ごとの伴奏和音
CHORDS = [[48,52,55],[43,47,50],[48,52,55],[43,47,50],
          [48,52,55],[43,47,50],[48,52,55],[43,48,52]]

def hz(m): return 440 * 2 ** ((m - 69) / 12)

def tone(f, dur, amp, vib=0.0, harmonics=(1, .5, .3, .15)):
    t = np.arange(int(dur * SR)) / SR
    ph = 2*np.pi*f*t + (vib * np.sin(2*np.pi*5.5*t) / 5.5 if vib else 0)
    w = sum(a*np.sin(k*ph) for k, a in enumerate(harmonics, 1))
    env = np.minimum(1, t/0.02) * np.minimum(1, (dur - t)/0.05)
    return amp * w * env

def build(with_accomp=True):
    total = sum(b for _, b in MELODY) * BEAT + 1
    out = np.zeros(int(total * SR))
    truth, pos = [], 0.5
    for m, b in MELODY:
        d = b * BEAT
        s = int(pos*SR); seg = tone(hz(m), d*0.95, 0.5, vib=hz(m)*0.018)  # ±約0.3半音のビブラート
        out[s:s+len(seg)] += seg
        truth.append({"midi": m, "start": round(pos, 3), "beats": b})
        pos += d
    if with_accomp:
        for i, ch in enumerate(CHORDS):
            s0 = 0.5 + i * 4 * BEAT
            for k in range(4):
                for m in ch:
                    seg = tone(hz(m), BEAT*0.9, 0.12, harmonics=(1, .3))
                    s = int((s0 + k*BEAT)*SR); out[s:s+len(seg)] += seg
    out /= np.abs(out).max() * 1.1
    return out, truth

if __name__ == "__main__":
    outdir = sys.argv[1]
    for name, acc in [("test_melody_only", False), ("test_with_accomp", True)]:
        a, truth = build(acc)
        sf.write(f"{outdir}/{name}.wav", a, SR)
    json.dump({"bpm": BPM, "notes": truth}, open(f"{outdir}/truth.json", "w"), ensure_ascii=False)
    print("written")
