#!/usr/bin/env python3
"""完成／失敗通知。冇 SMTP secrets 就只印出嚟，唔會令 job 失敗。"""
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


def main():
    status = sys.argv[1] if len(sys.argv) > 1 else "done"
    result_file = Path("result.json")
    data = {}
    if result_file.exists():
        import json
        data = json.loads(result_file.read_text(encoding="utf-8"))

    to = data.get("email") or os.environ.get("NOTIFY_TO")
    subject = f"[Movie_editing] {status}：" + (data.get("slug") or "委託")
    lines = [
        f"狀態：{status}",
        f"作品：{data.get('slug', '-')}",
        f"長度：{data.get('duration', '-')}",
        f"大小：{data.get('size', '-')}",
        f"片段：{data.get('segments', '-')}",
        f"播放：{data.get('url', '-')}",
        "",
        "由 GitHub Actions 自動剪接。",
    ]
    body = "\n".join(lines)

    host = os.environ.get("SMTP_SERVER")
    user = os.environ.get("SMTP_USERNAME")
    pwd = os.environ.get("SMTP_PASSWORD")
    if not (host and user and pwd and to):
        print("[notify] 未設定 SMTP secrets 或冇收件地址，跳過寄信：")
        print(body)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_FROM", user)
    msg["To"] = to
    msg.set_content(body)
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)
    print(f"[notify] 已寄出：{to}")


if __name__ == "__main__":
    main()
