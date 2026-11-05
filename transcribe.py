"""音源（YouTube URL / 音声ファイル）→ メロディ抽出 → ドレミ付き音符データ(JSON)

使い方:
  python3 transcribe.py <YouTube URL または 音声ファイル> -o out.json [--simplify]
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np, librosa

SR = 22050
HOP = 256
DOREMI = ["ド", "ド#", "レ", "レ#", "ミ", "ファ", "ファ#", "ソ", "ソ#", "ラ", "ラ#", "シ"]
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])


# ---------- 1. 入力 ----------
def fetch_audio(src, workdir):
    """URLならyt-dlpで音声だけ取得してwavに。ファイルならそのまま。"""
    if src.startswith("http"):
        out = os.path.join(workdir, "in.%(ext)s")
        cmd = ["yt-dlp", "-x", "--audio-format", "wav", "--no-playlist",
               "--match-filter", "duration < 600", "-o", out, src]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("yt-dlp error:", r.stderr[-500:], file=sys.stderr)   # 詳細はサーバーログへ
            if "duration" in r.stderr or "does not pass filter" in r.stderr:
                raise RuntimeError("10分を超える動画は使えません")
            raise RuntimeError("YouTubeから音声を取得できませんでした。時間をおくか、ファイルで試してください")
        return os.path.join(workdir, "in.wav")
    if not src.lower().endswith(".wav"):
        # mp3 / m4a / マイク録音(webm) などは ffmpeg で wav に変換
        out = os.path.join(workdir, "conv.wav")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-t", "600",
                            "-ac", "1", "-ar", str(SR), out], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("音声ファイルを読み込めませんでした")
        return out
    return src


def separate_vocals(path, workdir):
    """Demucsが入っていればボーカルだけ抜き出す（本番用）。無ければ原音のまま。"""
    try:
        import demucs  # noqa
    except ImportError:
        return path
    subprocess.run([sys.executable, "-m", "demucs", "--two-stems", "vocals", "-o", workdir, path], check=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    return os.path.join(workdir, "htdemucs", stem, "vocals.wav")


# ---------- 2. 音程検出 → 音符化 ----------
def extract_notes(y):
    f0, voiced, _ = librosa.pyin(y, fmin=librosa.note_to_hz("C3"), fmax=librosa.note_to_hz("C6"),
                                 sr=SR, hop_length=HOP)
    from scipy.signal import medfilt
    raw = librosa.hz_to_midi(np.nan_to_num(f0, nan=1.0))
    raw[~voiced] = np.nan
    # ビブラート対策：約0.2秒の移動中央値でならしてから半音に丸める
    filled = np.where(voiced, raw, 0.0)
    smooth = medfilt(filled, 17)
    midi = np.where(voiced & (smooth > 0), np.round(smooth), -1).astype(int)
    t = librosa.frames_to_time(np.arange(len(midi)), sr=SR, hop_length=HOP)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0][:len(midi)]

    # ① 音の高さが変わったところで区切る
    segs, cur, start = [], -1, 0
    for i, m in enumerate(list(midi) + [-1]):
        if m != cur:
            if cur >= 0 and i - start >= 6:   # 約70ms未満の揺れは捨てる
                segs.append((start, i))
            cur, start = m, i

    # ② 同じ高さが続く区間は、音量の「くぼみ」（＝弾き直し）で分ける
    def split_by_dips(s, e):
        cuts, W = [], 12
        for i in range(s + 8, e - 8):
            lo, hi = max(s, i - W), min(e, i + W)
            if rms[i] == rms[lo:hi].min() and rms[i] < 0.7 * min(rms[lo:i].max(), rms[i:hi].max()):
                if not cuts or i - cuts[-1] > 8:
                    cuts.append(i)
        b = [s] + cuts + [e]
        return list(zip(b[:-1], b[1:]))

    # ③ オクターブ補正：伴奏の低音につられて下の音を選ぶ誤りを、
    #    候補（そのまま/1オクターブ上/1オクターブ半上/2オクターブ上）の中で
    #    一番強く鳴っている高さに直す
    C_LOW = 36  # CQTの最低音 C2
    cqt = np.abs(librosa.cqt(y, sr=SR, hop_length=HOP, fmin=librosa.midi_to_hz(C_LOW),
                             n_bins=12 * 6, bins_per_octave=12))[:, :len(midi)]

    def fix_octave(m, s, e):
        best, best_e = m, -1
        for c in (m, m + 12, m + 19, m + 24):
            b = c - C_LOW
            if 0 <= b < cqt.shape[0]:
                en = cqt[b, s:e].mean()
                if en > best_e * 1.05:
                    best, best_e = c, en
        return best

    notes = []
    for s0, e0 in segs:
        for s, e in split_by_dips(s0, e0):
            m = int(np.round(np.nanmedian(raw[s:e])))
            m = fix_octave(m, s, e)
            notes.append({"midi": m, "start": float(t[s]), "end": float(t[min(e, len(t)-1)])})
    return notes


def extract_notes_bp(path):
    """Basic Pitch（ONNX）で全部の音を取り、一番上の音＝メロディを選ぶ（ピアノ・楽器向け）"""
    import logging; logging.disable(logging.WARNING)
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict
    _, _, events = predict(path, ICASSP_2022_MODEL_PATH, onset_threshold=0.5, frame_threshold=0.3,
                           minimum_note_length=80, minimum_frequency=110, maximum_frequency=1400)
    logging.disable(logging.NOTSET)
    ev = [(float(s), float(e), int(p), float(a)) for s, e, p, a, *_ in events]
    if not ev:
        return []
    amax = max(a for *_, a in ev)
    ev = sorted([x for x in ev if x[3] >= 0.45 * amax], key=lambda x: x[0])
    # ① ほぼ同時に鳴った音（和音）は一番上の音だけ残す
    groups = []
    for x in ev:
        if groups and x[0] - groups[-1][0][0] < 0.06:
            groups[-1].append(x)
        else:
            groups.append([x])
    def real_top(g):
        # 倍音（下の音の1オクターブ上・1オクターブ半上で、ずっと弱い音）は除く
        cand = [x for x in g if not any(y[2] in (x[2]-12, x[2]-19, x[2]-24) and x[3] < 0.7 * y[3] for y in g)]
        return max(cand or g, key=lambda x: x[2])
    tops = [real_top(g) for g in groups]
    # ② 前の音がまだ鳴っている間に始まった、それより低い音（伴奏）は捨てる
    mel = []
    for x in tops:
        if mel and x[2] < mel[-1][2] - 2 and x[0] < mel[-1][1] - 0.05 and x[0] - mel[-1][0] < 0.35:
            continue
        mel.append(x)
    # ③ 周りのメロディより大きく下にある音（左手の伴奏）を捨てる
    ps = np.array([x[2] for x in mel])
    keep = []
    for i, x in enumerate(mel):
        local = np.median(ps[max(0, i-4):i+5])
        if x[2] >= local - 9:
            keep.append(x)
    # ④ 同じ高さの音が続く場合、その音の響きが本当に強くなっていなければ（ドラム等で切れただけなら）1音にまとめる
    if keep:
        y, _ = librosa.load(path, sr=SR, mono=True)
        C0 = 36
        cqt = np.abs(librosa.cqt(y, sr=SR, hop_length=HOP, fmin=librosa.midi_to_hz(C0), n_bins=72))
        fr = lambda t: int(t * SR / HOP)
        def energy(p, a, b):
            seg = cqt[p - C0, max(0, fr(a)):max(fr(a) + 1, fr(b))]
            return float(seg.mean()) if seg.size else 0.0
        merged = [list(keep[0])]
        for s_, e_, p_, a_ in keep[1:]:
            ps_, pe_, pp_, pa_ = merged[-1]
            if p_ == pp_ and s_ - pe_ < 0.08:
                before = energy(p_, s_ - 0.07, s_ - 0.01)
                after = energy(p_, s_ + 0.01, s_ + 0.06)
                if after < before * 1.3:
                    merged[-1][1] = e_
                    continue
            merged.append([s_, e_, p_, a_])
        keep = [tuple(m) for m in merged]
    return [{"midi": p, "start": s, "end": e} for s, e, p, a in keep]


def quantize(notes, y):
    # テンポ：音の間隔の中で一番多い長さを「1拍」とみなす（伴奏が無くても動く）
    iois = np.diff([n["start"] for n in notes])
    iois = iois[(iois > 0.25) & (iois < 1.5)]
    if len(iois):
        hist, edges = np.histogram(iois, bins=40)
        beat_est = float(np.median(iois[(iois >= edges[hist.argmax()]) & (iois <= edges[hist.argmax()+1])]))
        bpm = 60 / beat_est
    else:
        bpm = 100.0
    while bpm < 60: bpm *= 2
    while bpm > 160: bpm /= 2
    beat = 60 / bpm
    for i, n in enumerate(notes):
        nxt = notes[i+1]["start"] if i + 1 < len(notes) else n["end"]
        span = max(n["end"], nxt) - n["start"] if nxt - n["end"] < beat * 0.5 else n["end"] - n["start"]
        n["beats"] = max(0.5, round(span / beat * 2) / 2)   # 8分音符単位に丸める
    return round(bpm), notes


# ---------- 3. かんたん化（キー推定 → ハ長調へ移調） ----------
def estimate_key(notes):
    hist = np.zeros(12)
    for n in notes:
        hist[n["midi"] % 12] += n["beats"]
    scores = [np.corrcoef(np.roll(MAJOR_PROFILE, k), hist)[0, 1] for k in range(12)]
    return int(np.argmax(scores))  # 0=C, 2=D ...


def simplify(notes):
    key = estimate_key(notes)
    shift = -key if key <= 6 else 12 - key
    for n in notes:
        n["midi"] += shift
    # 音域を C4〜C6 付近に寄せる
    avg = np.mean([n["midi"] for n in notes])
    octv = int(round((67 - avg) / 12)) * 12
    for n in notes:
        n["midi"] += octv
    return key, shift + octv


def label(notes):
    for n in notes:
        n["doremi"] = DOREMI[n["midi"] % 12]
        n["name"] = librosa.midi_to_note(n["midi"], unicode=False)
    return notes


def run(src, simplify_key=False, mode="inst"):
    with tempfile.TemporaryDirectory() as wd:   # 取得した音声は処理後に自動削除
        path = fetch_audio(src, wd)
        path = separate_vocals(path, wd)
        y, _ = librosa.load(path, sr=SR, mono=True)
        notes = None
        if mode == "inst":                     # ピアノ・楽器：Basic Pitch
            try:
                notes = extract_notes_bp(path)
            except ImportError:
                pass
        if notes is None:                      # 歌・鼻歌：pYIN
            notes = extract_notes(y)
    bpm, notes = quantize(notes, y)
    info = {"bpm": bpm, "transposed": 0}
    if simplify_key:
        key, sh = simplify(notes)
        info.update(original_key=DOREMI[key], transposed=sh)
    info["notes"] = [{k: v for k, v in n.items() if k != "end"} for n in label(notes)]
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("-o", "--out", default="out.json")
    ap.add_argument("--simplify", action="store_true", help="ハ長調に移調して読みやすくする")
    ap.add_argument("--mode", default="inst", choices=["inst", "voice"], help="inst=ピアノ・楽器 / voice=歌・鼻歌")
    a = ap.parse_args()
    res = run(a.src, a.simplify, a.mode)
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"BPM {res['bpm']} / {len(res['notes'])}音 → {a.out}")
    print(" ".join(n["doremi"] for n in res["notes"]))
