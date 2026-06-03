from __future__ import annotations

import os
import re
import smtplib
import argparse
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import markdown
from playwright.sync_api import sync_playwright


def split_emails(value: str) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in re.split(r"[;,]", value) if x.strip()]


def find_latest_markdown(report_dir: Path) -> Path:
    files = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No markdown report found in {report_dir}")
    return files[0]


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")

    body_html = markdown.markdown(
        md_text,
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "sane_lists",
            "toc",
        ],
    )

    html = f"""
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
@page {{
  size: A4;
  margin: 22mm 18mm;
}}

body {{
  font-family: "Noto Sans CJK SC", "Noto Sans CJK JP", "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
  font-size: 13px;
  line-height: 1.65;
  color: #222;
}}

h1 {{
  font-size: 24px;
  margin: 0 0 18px;
  padding-bottom: 10px;
  border-bottom: 2px solid #222;
}}

h2 {{
  font-size: 18px;
  margin-top: 24px;
  padding-bottom: 4px;
  border-bottom: 1px solid #ddd;
}}

h3 {{
  font-size: 15px;
  margin-top: 18px;
}}

p {{
  margin: 8px 0;
}}

ul, ol {{
  padding-left: 22px;
}}

li {{
  margin: 4px 0;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 12px;
}}

th, td {{
  border: 1px solid #ddd;
  padding: 6px 8px;
  vertical-align: top;
}}

th {{
  background: #f4f4f4;
}}

pre {{
  background: #f6f8fa;
  padding: 10px;
  overflow-wrap: break-word;
  white-space: pre-wrap;
  border-radius: 6px;
}}

code {{
  font-family: Consolas, Menlo, monospace;
  font-size: 12px;
}}

blockquote {{
  border-left: 4px solid #ddd;
  padding-left: 12px;
  color: #555;
}}

.footer {{
  margin-top: 32px;
  padding-top: 12px;
  border-top: 1px solid #ddd;
  font-size: 11px;
  color: #777;
}}
</style>
</head>
<body>
{body_html}
<div class="footer">
由 GitHub Actions 自动生成。基金分析仅供个人记录与参考，不构成投资建议。
</div>
</body>
</html>
"""

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={
                "top": "18mm",
                "right": "14mm",
                "bottom": "18mm",
                "left": "14mm",
            },
        )
        browser.close()


def build_email(md_path: Path, pdf_path: Path) -> EmailMessage:
    mail_from = os.getenv("MAIL_FROM") or os.getenv("MAIL_SMTP_USER")
    mail_to = split_emails(os.getenv("MAIL_TO", ""))
    mail_cc = split_emails(os.getenv("MAIL_CC", ""))
    mail_bcc = split_emails(os.getenv("MAIL_BCC", ""))

    if not mail_from:
        raise ValueError("MAIL_FROM or MAIL_SMTP_USER is required")
    if not mail_to:
        raise ValueError("MAIL_TO is required")

    subject_prefix = os.getenv("MAIL_SUBJECT_PREFIX", "基金日报")
    date_part = datetime.now().strftime("%Y-%m-%d")
    subject = f"{subject_prefix} - {date_part}"

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = ", ".join(mail_to)
    if mail_cc:
        msg["Cc"] = ", ".join(mail_cc)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg["Subject"] = subject

    text_body = f"""你好，

今日基金日报已生成，PDF 见附件。

源文件：
{md_path.name}

说明：
本邮件由 GitHub Actions 自动发送，仅供个人记录与参考，不构成投资建议。
"""

    msg.set_content(text_body)

    pdf_bytes = pdf_path.read_bytes()
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )

    attach_md = os.getenv("MAIL_ATTACH_MD", "false").lower() == "true"
    if attach_md:
        msg.add_attachment(
            md_path.read_bytes(),
            maintype="text",
            subtype="markdown",
            filename=md_path.name,
        )

    msg["_all_recipients"] = mail_to + mail_cc + mail_bcc
    return msg


def send_email(msg: EmailMessage) -> None:
    host = os.getenv("MAIL_SMTP_HOST", "")
    port = int(os.getenv("MAIL_SMTP_PORT", "465"))
    user = os.getenv("MAIL_SMTP_USER", "")
    password = os.getenv("MAIL_SMTP_PASSWORD", "")

    if not host:
        raise ValueError("MAIL_SMTP_HOST is required")
    if not user:
        raise ValueError("MAIL_SMTP_USER is required")
    if not password:
        raise ValueError("MAIL_SMTP_PASSWORD is required")

    recipients = msg["_all_recipients"]
    del msg["_all_recipients"]

    use_ssl = os.getenv("MAIL_SMTP_SSL", "").lower()
    if use_ssl:
        use_ssl_bool = use_ssl in {"1", "true", "yes", "on"}
    else:
        use_ssl_bool = port == 465

    use_starttls = os.getenv("MAIL_SMTP_STARTTLS", "").lower()
    if use_starttls:
        use_starttls_bool = use_starttls in {"1", "true", "yes", "on"}
    else:
        use_starttls_bool = port == 587

    if use_ssl_bool:
        with smtplib.SMTP_SSL(host, port, timeout=60) as server:
            server.login(user, password)
            server.send_message(msg, to_addrs=recipients)
    else:
        with smtplib.SMTP(host, port, timeout=60) as server:
            server.ehlo()
            if use_starttls_bool:
                server.starttls()
                server.ehlo()
            server.login(user, password)
            server.send_message(msg, to_addrs=recipients)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", default="reports")
    parser.add_argument("--md", default="")
    parser.add_argument("--pdf", default="")
    args = parser.parse_args()

    report_dir = Path(args.report_dir)

    md_path = Path(args.md) if args.md else find_latest_markdown(report_dir)

    if args.pdf:
        pdf_path = Path(args.pdf)
    else:
        pdf_path = md_path.with_suffix(".pdf")

    print(f"Converting markdown to PDF: {md_path} -> {pdf_path}")
    md_to_pdf(md_path, pdf_path)

    print(f"Sending email with PDF attachment: {pdf_path}")
    msg = build_email(md_path, pdf_path)
    send_email(msg)

    print("Email sent successfully.")


if __name__ == "__main__":
    main()