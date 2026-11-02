#!/usr/bin/env python3
"""
Movie_editing 自動剪片。

用法：
  python tools/cut.py --body body.md --out .            # 完整流程
  python tools/cut.py --body body.md --out . --dry-run  # 只出 EDL，唔渲染

流程：
  1. 由委託單解析四個欄位
  2. 下載 Drive 素材（gdown，需要公開連結）
  3. ffprobe / silencedetect / scdet 分析
  4. （可選）whisper 轉錄，切點會貼句尾
  5. 產生 EDL：有 LLM key 就交模型編排，否則用規則式編排器
  6. ffmpeg 照 EDL 渲染、配樂 ducking、燒字幕
  7. 更新 assets/data/edits.json、出封面、寫 result.json
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------- helpers
def run(cmd, check=True, capture=True):
    p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=capture,
                       text=True, errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {cmd}\n{(p.stderr or '')[-1500:]}")
    return p


def log(msg):
    print(f"[cut] {msg}", file=sys.stderr, flush=True)


def mmss(sec):
    sec = max(0, int(round(sec)))
    return f"{sec // 60}:{sec % 60:02d}"


# ---------------------------------------------------------------- 委託單
def parse_body(text):
    """由 GitHub issue body（或純文字委託單）抽出四個欄位。"""
    out = {"duration": None, "drive": None, "music": None, "email": None, "notes": ""}

    def grab(*patterns):
        for pat in patterns:
            m = re.search(pat, text, re.I | re.M)
            if m:
                return m.group(1).strip().strip("|").strip()
        return None

    dur = grab(r"\|\s*片長\s*\|\s*\**\s*([0-9:.\s]+?)\s*\**\s*\|", r"片長[：:]\s*([0-9:.\s]+)")
    drive = grab(r"\|\s*素材[^|]*\|\s*(https?://[^\s|]+)", r"素材[^：:]*[：:]\s*(https?://\S+)")
    music = grab(r"\|\s*背景音樂[^|]*\|\s*(https?://[^\s|]+)", r"背景音樂[^：:]*[：:]\s*(https?://\S+)")
    email = grab(r"\|\s*通知 Email\s*\|\s*([^\s|]+@[^\s|]+)", r"Email[：:]\s*([^\s]+@[^\s]+)")
    notes = grab(r"\*\*其他要求\*\*\s*\n+\s*(.+?)(?:\n\s*\n|\n---|$)", r"其他要求[：:]\s*(.+)")

    out.update(duration=dur, drive=drive, music=music, email=email, notes=notes or "")
    if out["music"] and re.search(r"無，由|^無$|^\s*$", out["music"]):
        out["music"] = None
    return out


def parse_duration(raw):
    if not raw:
        return None
    v = raw.strip().lower().replace(" ", "")
    m = re.match(r"^(\d{1,2}):([0-5]\d)$", v)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r"^(\d{1,2})分(?:(\d{1,2})秒?)?$", v)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2) or 0)
    m = re.match(r"^(\d{1,4})(s|sec|秒)$", v)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d{1,3})$", v)
    if m:
        return int(m.group(1)) * 60
    return None


# ---------------------------------------------------------------- 下載
def download_drive(url, workdir):
    """gdown 支援資料夾同單檔，需要「知道連結的人可檢視」。"""
    if not shutil.which("gdown"):
        run([sys.executable, "-m", "pip", "install", "-q", "gdown"])
    dest = Path(workdir) / "src"
    dest.mkdir(parents=True, exist_ok=True)
    log(f"下載 Drive：{url}")
    if "/folders/" in url:
        run([sys.executable, "-m", "gdown", "--folder", "--remaining-ok", url, "-O", str(dest)], check=False)
    else:
        run([sys.executable, "-m", "gdown", url, "-O", str(dest), "--fuzzy"], check=False)

    files = [p for p in Path(workdir).rglob("*") if p.is_file() and p.suffix.lower() not in
             {".txt", ".md", ".json", ".html"}]
    if not files:
        raise SystemExit("Drive 下載失敗：請確認連結已設為「知道連結的人可檢視」，或者改用資料夾連結。")
    return sorted(files)


def download_music(url, workdir):
    """YouTube 音樂。失敗就當冇音樂，唔好拖死成條片。"""
    if not url:
        return None
    if not shutil.which("yt-dlp"):
        run([sys.executable, "-m", "pip", "install", "-q", "yt-dlp"], check=False)
    out = Path(workdir) / "music.m4a"
    p = run([shutil.which("yt-dlp") or "yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio",
             "--no-playlist", "-o", str(out), url], check=False)
    if p.returncode != 0 or not out.exists():
        candidates = list(Path(workdir).glob("music.*"))
        if not candidates:
            log("音樂下載失敗，改用無配樂")
            return None
        return candidates[0]
    return out


# ---------------------------------------------------------------- 分析
FFPROBE = "ffprobe"


def probe(path):
    p = run([FFPROBE, "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", str(path)], check=False)
    try:
        d = json.loads(p.stdout)
    except Exception:
        return None
    dur = float(d.get("format", {}).get("duration") or 0)
    vs = [s for s in d.get("streams", []) if s.get("codec_type") == "video"]
    aus = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
    if not vs:
        return None
    w, h = vs[0].get("width", 1920), vs[0].get("height", 1080)
    fr = vs[0].get("r_frame_rate", "30/1")
    try:
        num, den = fr.split("/")
        fps = float(num) / float(den or 1)
    except Exception:
        fps = 30.0
    return {"path": str(path), "duration": dur, "width": w, "height": h,
            "fps": fps if fps and fps < 121 else 30.0, "has_audio": bool(aus),
            "is_image": False}


IMG_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp", ".tif", ".tiff"}


def image_to_clip(path, workdir, seconds=4.0, w=1920, h=1080):
    """相片轉成有靜音軌嘅短片，噉樣同語音片拼接時 audio 唔會斷。"""
    out = Path(workdir) / f"_img_{Path(path).stem[:24]}.mp4"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-t", f"{seconds}", "-i", str(path),
         "-f", "lavfi", "-t", f"{seconds}", "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-shortest", str(out)])
    return out


def analyze_audio(path, dur):
    """回傳 (靜音區間, 語音區間)。"""
    p = run(["ffmpeg", "-hide_banner", "-i", str(path), "-af",
             "silencedetect=noise=-32dB:d=0.55", "-f", "null", "-"], check=False)
    sil, starts, ends = [], [], []
    for line in (p.stderr or "").splitlines():
        m = re.search(r"silence_start:\s*([0-9.]+)", line)
        if m:
            starts.append(float(m.group(1)))
        m = re.search(r"silence_end:\s*([0-9.]+)", line)
        if m:
            ends.append(float(m.group(1)))
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else dur
        if e - s >= 0.4:
            sil.append((max(0, s), min(dur, e)))
    speech, cursor = [], 0.0
    for s, e in sorted(sil):
        if s - cursor > 0.6:
            speech.append((cursor, s))
        cursor = max(cursor, e)
    if dur - cursor > 0.6:
        speech.append((cursor, dur))
    return sil, speech


def analyze_scenes(path):
    p = run(["ffmpeg", "-hide_banner", "-i", str(path), "-filter:v",
             "select='gt(scene,0.32)',showinfo", "-an", "-f", "null", "-"], check=False)
    cuts = []
    for line in (p.stderr or "").splitlines():
        m = re.search(r"pts_time:\s*([0-9.]+)", line)
        if m:
            cuts.append(float(m.group(1)))
    return cuts


def analyze_black(path):
    """偵測黑場（片頭標題卡、fade），避免剪到全黑位。"""
    p = run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf",
             "blackdetect=d=0.25:pix_th=0.10", "-an", "-f", "null", "-"], check=False)
    out = []
    for line in (p.stderr or "").splitlines():
        m = re.search(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)", line)
        if m:
            out.append((float(m.group(1)), float(m.group(2))))
    return out


def black_ratio(a, b, blacks):
    if not blacks or b <= a:
        return 0.0
    overlap = 0.0
    for s, e in blacks:
        overlap += max(0.0, min(b, e) - max(a, s))
    return overlap / (b - a)


def transcribe(files, workdir):
    """用 faster-whisper 轉錄（可選）。冇裝就回傳 None。"""
    try:
        from faster_whisper import WhisperModel
    except Exception:
        log("未安裝 faster-whisper，跳過轉錄，改用靜音／場景規則")
        return None
    model_size = os.environ.get("WHISPER_MODEL", "base")
    log(f"轉錄中（model={model_size}）")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    out = []
    for f in files:
        if Path(f).suffix.lower() not in {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".mp3", ".wav", ".m4a"}:
            continue
        try:
            segs, _ = model.transcribe(str(f), vad_filter=True, beam_size=1,
                                       condition_on_previous_text=False)
            for s in segs:
                txt = (s.text or "").strip()
                if len(txt) >= 2:
                    out.append({"file": str(f), "start": s.start, "end": s.end, "text": txt})
        except Exception as exc:
            log(f"轉錄 {f} 失敗：{exc}")
    log(f"轉錄段落：{len(out)}")
    return out or None


# ---------------------------------------------------------------- EDL
def snap(t, silences, tol=0.45):
    """把切點吸去最近的靜音邊界，避免切斷字。"""
    best, bestd = t, tol
    for s, e in silences:
        for edge in (s, e):
            d = abs(edge - t)
            if d < bestd:
                best, bestd = edge, d
    return best


def build_units(media, transcripts, silences, scenes, blacks=None):
    blacks = blacks or {}
    """把素材切成可揀選單位：有字幕就跟句子，冇就跟場景／靜音。"""
    units = []
    if transcripts:
        by_file = {}
        for t in transcripts:
            by_file.setdefault(t["file"], []).append(t)
        for f, segs in by_file.items():
            segs.sort(key=lambda x: x["start"])
            cur = None
            for s in segs:
                if cur and (s["start"] - cur["end"] < 0.7) and (s["end"] - cur["start"] < 9):
                    cur["end"] = s["end"]
                    cur["text"] = (cur["text"] + " " + s["text"]).strip()
                else:
                    if cur and cur["end"] - cur["start"] >= 1.2:
                        units.append(cur)
                    cur = {"file": f, "start": s["start"], "end": s["end"], "text": s["text"]}
            if cur and cur["end"] - cur["start"] >= 1.2:
                units.append(cur)
        for u in units:
            dur = u["end"] - u["start"]
            density = len(u["text"]) / max(dur, 0.1)
            u["score"] = 1.0 + min(density / 8.0, 1.6)
            u["black"] = black_ratio(u["start"], u["end"], blacks.get(u["file"]))
    else:
        # 冇文字：用場景切點＋靜音切成 2–6 秒單位
        for m in media:
            f, dur = m["path"], m["duration"]
            cuts = [0.0] + [c for c in scenes.get(f, []) if 0.4 < c < dur - 0.3] + [dur]
            for a, b in zip(cuts, cuts[1:]):
                if b - a < 1.2:
                    continue
                if b - a > 6.0:
                    b = a + 6.0
                units.append({"file": f, "start": a, "end": b, "text": "",
                              "score": 1.0 + min((b - a) / 6.0, 0.8),
                              "black": black_ratio(a, b, blacks.get(f))})
    return units


def pick_units(units, target):
    """按時間軸三段分配預算，維持原本次序，總長貼近 target。"""
    units = [u for u in units if (u["end"] - u["start"]) >= 1.5 and u.get("black", 0) < 0.55]
    if not units:
        raise SystemExit("冇足夠長度嘅可用片段（每段最少 1.5 秒）")

    per = {}
    for u in units:
        per.setdefault(u["file"], []).append(u)
    for _, us in per.items():
        span = max(x["end"] for x in us) or 1
        for u in us:
            u["pos"] = ((u["start"] + u["end"]) / 2) / span

    units.sort(key=lambda u: (u["file"], u["start"]))
    chosen = []
    for lo, hi, share in ((0, 0.34, 0.3), (0.34, 0.67, 0.4), (0.67, 1.01, 0.3)):
        budget, used = target * share, 0.0
        for u in sorted([x for x in units if lo <= x["pos"] < hi], key=lambda x: -x["score"]):
            d = min(u["end"] - u["start"], 10.0)
            if used + d > budget + 0.6:
                continue
            chosen.append({"file": u["file"], "in": round(u["start"], 2),
                           "out": round(u["start"] + d, 2), "text": u.get("text", "")})
            used += d
            if used >= budget - 1.2:
                break

    chosen.sort(key=lambda c: (c["file"], c["in"]))
    total = sum(c["out"] - c["in"] for c in chosen)

    if total < target - 1.0:  # 未夠長，由最高分嘅剩餘單位補
        taken = {(c["file"], round(c["in"], 1)) for c in chosen}
        for u in sorted(units, key=lambda x: -x["score"]):
            if (u["file"], round(u["start"], 1)) in taken:
                continue
            d = min(u["end"] - u["start"], 10.0)
            if total + d > target + 0.5:
                continue
            chosen.append({"file": u["file"], "in": round(u["start"], 2),
                           "out": round(u["start"] + d, 2), "text": u.get("text", "")})
            total += d
            if total >= target - 0.8:
                break
        chosen.sort(key=lambda c: (c["file"], c["in"]))

    total = sum(c["out"] - c["in"] for c in chosen)
    if total > target + 0.3 and chosen:  # 超長就剪尾
        last = chosen[-1]
        last["out"] = round(last["out"] - (total - target), 2)
        if last["out"] - last["in"] < 1.2:
            chosen.pop()
    return chosen, sum(c["out"] - c["in"] for c in chosen)


def plan_with_llm(order, media, transcripts, target):
    """如果有 LLM key，交模型寫 EDL；失敗就 return None 由規則接手。"""
    key = os.environ.get("LLM_API_KEY")
    if not key or not transcripts:
        return None
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    lines = [f"[{mmss(t['start'])}-{mmss(t['end'])}] {t['text']}" for t in transcripts][:400]
    prompt = (
        "你係剪接師。以下係素材逐句轉錄（檔名可能只有一個）。\n"
        f"目標片長：{mmss(target)}。\n"
        "請揀選段落，保持時間順序，切點只可以落喺句與句之間，唔可以切斷一句。\n"
        "只回 JSON：{\"segments\":[{\"file\":\"...\",\"in\":秒,\"out\":秒,\"why\":\"短理由\"}]}\n\n"
        + "\n".join(lines)
    )
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps({"model": model, "temperature": 0.2,
                             "messages": [{"role": "user", "content": prompt}]}).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = json.loads(r.read().decode())["choices"][0]["message"]["content"]
        txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
        segs = json.loads(txt)["segments"]
        out, total = [], 0.0
        valid = {m["path"] for m in media}
        for s in segs:
            f = s["file"] if s.get("file") in valid else media[0]["path"]
            a, b = float(s["in"]), float(s["out"])
            if b - a < 0.8:
                continue
            out.append({"file": f, "in": round(a, 2), "out": round(b, 2), "text": s.get("why", "")})
            total += b - a
        if out and total >= target * 0.6:
            log(f"LLM EDL：{len(out)} 段，{mmss(total)}")
            return out
        log("LLM EDL 長度不足，改用規則編排")
    except Exception as exc:
        log(f"LLM 編排失敗（{exc}），改用規則編排")
    return None


# ---------------------------------------------------------------- 渲染
def render(edl, media_map, music, target, out_path, workdir, w, h, fps, burn_subs):
    """逐段編碼再做無損拼接；有音樂就只重編碼音軌。記憶體足跡細。"""
    parts = Path(workdir) / "parts"
    parts.mkdir(exist_ok=True)
    preset = os.environ.get("X264_PRESET", "veryfast")
    crf = os.environ.get("X264_CRF", "20")

    part_files = []
    for i, seg in enumerate(edl):
        dur = max(0.4, seg["out"] - seg["in"])
        part = parts / f"p{i:03d}.mp4"
        src = media_map[seg["file"]]
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p")
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-ss", f"{seg['in']:.3f}", "-t", f"{dur:.3f}", "-i", seg["file"]]
        if src["has_audio"]:
            cmd += ["-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", "160k",
                    "-ar", "48000", "-ac", "2"]
        else:
            cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                    "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "128k"]
        cmd += ["-vf", vf, "-c:v", "libx264", "-preset", preset, "-crf", crf,
                "-pix_fmt", "yuv420p", "-r", str(fps), "-t", f"{dur:.3f}",
                "-movflags", "+faststart", str(part)]
        run(cmd)
        part_files.append(part)

    lst = parts / "list.txt"
    lst.write_text("\n".join(f"file '{p.name}'" for p in part_files), encoding="utf-8")
    joined = parts / "joined.mp4"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(joined)])

    if music:
        filters = [
            f"[1:a]atrim=0:{target:.2f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,volume=0.9[bgmraw]",
            "[0:a]asplit=2[speech][key]",
            "[bgmraw][key]sidechaincompress=threshold=0.05:ratio=6:attack=12:release=320[bgm]",
            "[speech][bgm]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95[aout]",
        ]
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(joined), "-stream_loop", "-1", "-i", str(music),
             "-filter_complex", ";".join(filters),
             "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
             "-t", f"{target:.2f}", "-movflags", "+faststart", str(out_path)])
    else:
        shutil.copy2(joined, out_path)
    return out_path


def ensure_size(path, limit_mb=95):
    size = Path(path).stat().st_size / 1e6
    for crf in (24, 28):
        if size <= limit_mb:
            return size
        log(f"檔案 {size:.0f} MB 超過上限，CRF {crf} 重壓")
        tmp = str(path) + ".small.mp4"
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", tmp])
        Path(tmp).replace(path)
        size = Path(path).stat().st_size / 1e6
    return size


def make_poster(video, poster, at=3.0):
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(video),
         "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "4", str(poster)], check=False)


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, help="委託單文字檔")
    ap.add_argument("--out", default=".", help="repo 根目錄")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--local-dir", default=None, help="本機測試用：唔經 Drive，直接讀資料夾")
    ap.add_argument("--local-music", default=None, help="本機測試用：直接指定音樂檔")
    args = ap.parse_args()

    repo = Path(args.out).resolve()
    raw = Path(args.body).read_text(encoding="utf-8")
    order = parse_body(raw)
    target = parse_duration(order["duration"])
    log(f"委託：{order}")
    if not target:
        raise SystemExit("委託單沒有有效片長，停止。")
    if not order["drive"]:
        raise SystemExit("委託單沒有 Drive 連結，停止。")

    workdir = tempfile.mkdtemp(prefix="cut-")
    try:
        files = (sorted(p for p in Path(args.local_dir).rglob("*") if p.is_file())
                 if args.local_dir else download_drive(order["drive"], workdir))
        prepared = []
        for f in files:
            if Path(f).suffix.lower() in IMG_EXT:
                prepared.append(image_to_clip(f, workdir))
            else:
                prepared.append(f)
        media = [m for m in (probe(f) for f in prepared) if m and m["duration"] > 0.6]
        if not media:
            raise SystemExit("素材裡找不到可用的影片。")
        log(f"素材：{len(media)} 條，總長 {mmss(sum(m['duration'] for m in media))}")

        silences, scenes, blacks = {}, {}, {}
        for m in media[:40]:
            silences[m["path"]], _ = analyze_audio(m["path"], m["duration"])
            scenes[m["path"]] = analyze_scenes(m["path"])
            blacks[m["path"]] = analyze_black(m["path"])

        transcripts = transcribe([m["path"] for m in media], workdir)
        edl = plan_with_llm(order, media, transcripts, target) if transcripts else None
        if not edl:
            units = build_units(media, transcripts, silences, scenes, blacks)
            edl, total = pick_units(units, target)
            # 切點吸去靜音邊界
            for seg in edl:
                sil = _silences_for(seg["file"], media, silences)
                if sil:
                    seg["in"] = round(snap(seg["in"], sil), 2)
                    seg["out"] = round(snap(seg["out"], sil), 2)
            log(f"規則 EDL：{len(edl)} 段，{mmss(sum(s['out'] - s['in'] for s in edl))}")

        if args.dry_run:
            print(json.dumps({"target": target, "edl": edl}, ensure_ascii=False, indent=2))
            return

        music = Path(args.local_music) if args.local_music else download_music(order["music"], workdir)
        first = media[0]
        w, h = first["width"], first["height"]
        if w > 1920 or h > 1080:
            scale = min(1920 / w, 1080 / h)
            w, h = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
        w, h = w // 2 * 2, h // 2 * 2
        fps = 30 if first["fps"] > 25 else 25

        stamp = os.environ.get("RUN_ID") or "local"
        date = os.environ.get("RUN_DATE") or "2026-01-01"
        slug = f"auto-{date.replace('-', '')}-{stamp[-4:]}"
        video_rel = f"videos/{slug}.mp4"
        poster_rel = f"covers/{slug}.jpg"
        (repo / "videos").mkdir(exist_ok=True)
        (repo / "covers").mkdir(exist_ok=True)

        out_video = repo / video_rel
        render(edl, {m["path"]: m for m in media}, music, target, out_video, workdir, w, h, fps, False)
        size_mb = ensure_size(out_video)
        make_poster(out_video, repo / poster_rel, at=min(3.0, target / 3))

        meta = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                    "-of", "csv=p=0", str(out_video)]).stdout.strip()
        real = float(meta or target)
        entry = {
            "slug": slug,
            "title": _title(order),
            "subtitle": f"自動剪 · {date}",
            "desc": order["notes"][:160] or "由委託單自動剪成。",
            "video": video_rel,
            "poster": poster_rel,
            "duration": mmss(real),
            "runtime": round(real, 1),
            "size": f"{size_mb:.0f} MB",
            "date": date,
            "res": f"{h}p",
            "auto": True,
            "tags": ["自動剪", f"{mmss(target)} 目標"],
            "chapters": [{"t": 0, "label": "開始"}],
        }
        _update_json(repo, entry)

        result = {"slug": slug, "duration": mmss(real), "size": f"{size_mb:.0f} MB",
                  "segments": len(edl), "email": order["email"],
                  "url": f"https://tyhcch1234.github.io/Movie_editing/watch.html?v={slug}"}
        (repo / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        log(f"完成：{json.dumps(result, ensure_ascii=False)}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _silences_for(path, media, silences):
    return silences.get(path) or []


def _title(order):
    """優先用委託單第一行（通常係作品名），否則用 issue 標題。"""
    first = next((ln.strip() for ln in order["notes"].splitlines() if ln.strip()), "")
    if len(first) >= 4 and not first.startswith("測試"):
        return first[:40]
    t = re.sub(r"^\[委託\]\s*", "", (os.environ.get("ISSUE_TITLE") or "").strip())
    return (t or first or "自動剪作品")[:40]


def _update_json(repo, entry):
    p = repo / "assets/data/edits.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["edits"] = [e for e in data["edits"] if e["slug"] != entry["slug"]]
    data["edits"].insert(0, entry)
    data["updated"] = entry["date"]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
