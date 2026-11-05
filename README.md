# ドレミ楽譜 — 技術テスト版

YouTubeリンク／音声ファイル → メロディ抽出 → ドレミ付きかんたん楽譜

## ファイル
| ファイル | 役割 |
|---|---|
| transcribe.py | 採譜の本体（URL/ファイル → 音符JSON）。`--simplify` でハ長調に移調 |
| render_html.py | JSON → ドレミ楽譜ページ（再生・速度変更・鍵盤ガイド付き） |
| make_test_audio.py | テスト音源（歓喜の歌・パブリックドメイン）と正解データを作る |
| evaluate.py | 正解との一致率を計測 |

## テスト結果（作業環境で実施）
| テスト | 音の高さ | 音の長さ |
|---|---|---|
| メロディのみ | 100% | 100% |
| メロディ＋伴奏 | 100% | 100% |
| ニ長調 → ハ長調へ移調 | 100% | 100% |
| YouTube取得 | 未確認（作業環境のネット制限で接続不可。VPSで要確認） | |

※合成音源での結果です。実際の歌声（息・子音・ビブラート）では精度が下がるので、次はVPSで実曲テストが必要です。

## ConoHa VPSでの確認手順（Ubuntu想定）
```bash
sudo apt update && sudo apt install -y python3-pip ffmpeg
pip3 install --break-system-packages librosa soundfile scipy yt-dlp
# 実曲のボーカル分離を使う場合（CPUでも動くが1曲1〜3分かかる）
pip3 install --break-system-packages demucs

# ① YouTubeから取得できるか
yt-dlp -x --audio-format wav -o test.%\(ext\)s "YouTubeのURL"

# ② 採譜 → 楽譜ページ
python3 transcribe.py "YouTubeのURL" -o out.json --simplify
python3 render_html.py out.json -o score.html --title "曲名"
```
①で `Sign in to confirm you're not a bot` などが出たら、VPSのIPがYouTubeにブロックされています（その場合は cookie 指定や別回線の検討が必要）。

## 仕組み
1. 取得：yt-dlpで音声のみ取得（10分以内）→ 処理後すぐ削除（ユーザーに音声は渡さない）
2. 分離：Demucsがあればボーカルだけ抽出
3. 音程：pYINで音の高さを検出 → 中央値フィルタでビブラートを吸収
4. 区切り：高さの変化＋音量のくぼみ（同じ音の弾き直し）で1音ずつに分割
5. オクターブ補正：伴奏の低音につられた誤判定をCQTで修正
6. リズム：音の間隔からテンポ推定 → 8分音符単位に丸める
7. かんたん化：キー推定 → ハ長調に移調、音域をド〜高いドに寄せる

## Webアプリ版（MVP）
- `server/app.py`：API（YouTube URL・ファイル・録音を受付 → 順番に採譜 → 結果を返す。権利確認必須、1日3曲まで無料、音声は処理後すぐ削除）
- `web/index.html` + `web/score.js`：画面（YouTube / ファイル / 録音・鼻歌 → ドレミ楽譜・再生・速度変更・鍵盤ガイド）。Capacitorでそのままアプリ化できる構成
- ローカル起動：`pip install -r requirements.txt && uvicorn server.app:app --port 8000` → http://localhost:8000
- VPSへの配置：DEPLOY.md
