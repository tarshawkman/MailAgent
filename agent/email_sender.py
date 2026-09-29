"""
Email Sender — SMTP sending with multi-attachment and CC support.
"""
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Union

class EmailSender:
    def __init__(self, email: str, password: str, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        self.email = (email or "").strip()
        self.password = (password or "").strip()
        self.server = (smtp_server or "smtp.gmail.com").strip()
        self.port = int(smtp_port or 587)

    def send(
        self,
        to_email: str,
        cc_email: str = "",
        subject: str = "",
        body: str = "",
        attachments: Optional[Union[str, List[str]]] = None,
        sender_name: str = "",
    ) -> Dict:
        try:
            if not self.email or not self.password:
                return {
                    "success": False,
                    "error": "SMTP sender email or app password is not configured in .env"
                }

            to_email = (to_email or "").strip()
            if not to_email:
                return {"success": False, "error": "Recipient email (To) is required."}

            msg = MIMEMultipart()
            from_field = f"{sender_name} <{self.email}>" if sender_name else self.email
            msg["From"] = from_field
            msg["To"] = to_email
            msg["Subject"] = subject or "Research Collaboration Inquiry"

            recipients = [to_email]
            if cc_email:
                msg["Cc"] = cc_email
                recipients.extend(e.strip() for e in cc_email.split(",") if e.strip())

            msg.attach(MIMEText(body or "", "plain", "utf-8"))

            attach_list: List[str] = []
            if isinstance(attachments, str):
                attach_list = [attachments]
            elif isinstance(attachments, list):
                attach_list = [a for a in attachments if isinstance(a, str) and a.strip()]

            attached_names = []
            for path in attach_list:
                if path and os.path.isfile(path):
                    with open(path, "rb") as fh:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(fh.read())
                    encoders.encode_base64(part)
                    fname = os.path.basename(path)
                    part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
                    msg.attach(part)
                    attached_names.append(fname)

            with smtplib.SMTP(self.server, self.port, timeout=30) as srv:
                srv.ehlo()
                srv.starttls()
                srv.ehlo()
                srv.login(self.email, self.password)
                srv.sendmail(self.email, recipients, msg.as_string())

            attach_str = f" with {len(attached_names)} attachment(s) ({', '.join(attached_names)})" if attached_names else ""
            cc_str = f" (CC: {cc_email})" if cc_email else ""
            return {
                "success": True,
                "message": f"Email successfully sent to {to_email}{cc_str}{attach_str}!",
                "recipients": recipients,
                "attachments": attached_names,
            }
        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "error": "Authentication failed. For Gmail, use a 16-character App Password (not your normal password). Generate one at: Google Account -> Security -> 2-Step Verification -> App Passwords."
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}
