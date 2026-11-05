# ConoHa VPS への配置手順

## 準備するもの
- ConoHa VPS（Ubuntu 22.04/24.04、メモリ2GB以上。Demucsを使うなら4GB以上推奨）
- ドメイン（例：`gakufu.businessmaker.net`）の Aレコードを VPS のIPに向けておく

## ステップ1：Dockerを入れる
```bash
curl -fsSL https://get.docker.com | sudo sh
```

## ステップ2：ファイルを置いて起動
```bash
# このzipをVPSにアップロードして展開
unzip doremi-gakufu.zip && cd gakufu
echo "DOMAIN=gakufu.businessmaker.net" > .env      # ← 自分のドメインに変更
sudo docker compose up -d --build
```
数分後に `https://（ドメイン）/` を開くと画面が出ます。

## ステップ3：YouTubeから取れるか確認（最重要）
画面でYouTubeリンクを入れて試す。失敗したらログを確認：
```bash
sudo docker compose logs app | grep yt-dlp
```
- `Sign in to confirm you're not a bot` → VPSのIPがYouTubeにブロックされています。
  対策：①yt-dlpを最新にする（`docker compose build --no-cache`）②cookieファイルを使う ③自宅回線など別の回線から取得する仕組みを検討

## ステップ4：メモリ対策（スワップ2GB）
Demucs（音の分離）はメモリを多く使うため、2GBプランではスワップを足しておく：
```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

## 設定
- 1日の無料回数：`.env` に `FREE_PER_DAY=3`
- 採譜する長さの上限（秒）：`.env` に `MAX_SEC=180`
- 音の分離を止める：`.env` に `USE_DEMUCS=0`
- アプリ版（Capacitor）から使う場合：`web/` をアプリに入れ、`index.html` の先頭で
  `window.DOREMI_API = "https://（ドメイン）"` を設定
