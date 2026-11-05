"""ドレミ楽譜 API サーバー
  POST /api/jobs        (form: url または file, agree=1, simplify=1) → {"id": ...}
  GET  /api/jobs/{id}   → {"status": "queued|running|done|error", "result": {...}, "error": "..."}
  GET  /                → 画面 (web/index.html)
起動: uvicorn server.app:app --host 0.0.0.0 --port 8000
"""
import os, sys, time, uuid, shutil, tempfile, threading, queue, datetime, re
from fastapi import FastAPI, Form, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import transcribe  # noqa: E402

FREE_PER_DAY = int(os.environ.get("FREE_PER_DAY", "3"))   # 1日の無料回数（IPごと）
MAX_UPLOAD_MB = 30
YT_RE = re.compile(r"^https://(www\.|m\.|music\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w\-]{6,}")

app = FastAPI(title="ドレミ楽譜 API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # Capacitorアプリから呼ぶため

jobs: dict = {}
usage: dict = {}          # (ip, 日付) -> 回数
work_q: "queue.Queue" = queue.Queue()
lock = threading.Lock()


def worker():
    while True:
        jid, src, simplify, tmpdir, mode, sep = work_q.get()
        jobs[jid]["status"] = "running"
        try:
            jobs[jid]["result"] = transcribe.run(src, simplify, mode, sep)
            jobs[jid]["status"] = "done"
        except Exception as e:  # noqa
            jobs[jid].update(status="error", error=str(e)[:200])
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)   # アップロード音声は処理後すぐ削除
        # 古いジョブ（1時間以上前）を掃除
        now = time.time()
        for k in [k for k, v in jobs.items() if now - v["created"] > 3600]:
            jobs.pop(k, None)


threading.Thread(target=worker, daemon=True).start()   # CPU負荷が高いので1件ずつ順番に処理


def count_usage(ip):
    key = (ip, datetime.date.today().isoformat())
    with lock:
        if usage.get(key, 0) >= FREE_PER_DAY:
            raise HTTPException(429, f"無料で使えるのは1日{FREE_PER_DAY}曲までです")
        usage[key] = usage.get(key, 0) + 1


@app.post("/api/jobs")
async def create_job(request: Request, url: str = Form(""), agree: str = Form(""),
                     simplify: str = Form("1"), mode: str = Form("inst"), sep: str = Form(""), file: UploadFile | None = File(None)):
    if agree != "1":
        raise HTTPException(400, "音源の利用権限の確認にチェックしてください")
    tmpdir = None
    if file is not None and file.filename:
        ext = os.path.splitext(file.filename)[1].lower() or ".webm"
        if ext not in (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".webm", ".flac", ".mp4"):
            raise HTTPException(400, "対応していないファイル形式です")
        tmpdir = tempfile.mkdtemp()
        src = os.path.join(tmpdir, "upload" + ext)
        size = 0
        with open(src, "wb") as f:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD_MB << 20:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    raise HTTPException(400, f"ファイルは{MAX_UPLOAD_MB}MBまでです")
                f.write(chunk)
    elif url:
        if not YT_RE.match(url.strip()):
            raise HTTPException(400, "YouTubeのURLを入力してください")
        src = url.strip()
    else:
        raise HTTPException(400, "URLかファイルを指定してください")

    count_usage(request.client.host if request.client else "?")
    jid = uuid.uuid4().hex[:12]
    jobs[jid] = {"status": "queued", "created": time.time()}
    work_q.put((jid, src, simplify == "1", tmpdir, "voice" if mode == "voice" else "inst", {"1": True, "0": False}.get(sep)))
    return {"id": jid, "position": work_q.qsize()}


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    j = jobs.get(jid)
    if not j:
        raise HTTPException(404, "見つかりません（1時間で消えます）")
    return {k: v for k, v in j.items() if k != "created"}


@app.get("/api/health")
def health():
    return {"ok": True, "queue": work_q.qsize()}


app.mount("/", StaticFiles(directory=os.path.join(ROOT, "web"), html=True), name="web")
