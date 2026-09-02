"""Live real-document E2E: client Gmail -> agent Gmail -> client Gmail.
Uses the repo's fake passport JPG, local OCR, and live DeepSeek extraction.
"""
import imaplib, os, smtplib, tempfile, time, uuid
from typing import cast
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from uk_visa_consultant.channels.email import EmailAdapter
from uk_visa_consultant.config import load_env
from uk_visa_consultant.gateway.loop import Gateway

load_env()
CLIENT=os.environ['EMAIL_CLIENT_USER']; CPASS=os.environ['EMAIL_CLIENT_PASSWORD']
AGENT=os.environ['EMAIL_IMAP_USER']; APASS=os.environ['EMAIL_IMAP_PASSWORD']
SAMPLE=Path('examples/documents/fake-passport.jpg')
TAG=f"real-passport-{uuid.uuid4().hex[:10]}"; SUBJECT=f"UK visitor test {TAG}"
ROOT=f"<{TAG}-root@e2e>"; DOCMID=f"<{TAG}-doc@e2e>"

def send_client(body, mid, refs=None, attach=None):
    m=EmailMessage(); m['From']=CLIENT; m['To']=AGENT; m['Subject']=SUBJECT; m['Message-ID']=mid
    if refs: m['In-Reply-To']=refs; m['References']=refs
    m.set_content(body)
    if attach:
        m.add_attachment(attach.read_bytes(), maintype='image', subtype='jpeg', filename=attach.name)
    with smtplib.SMTP_SSL('smtp.gmail.com',465) as s:
        s.login(CLIENT,CPASS); s.send_message(m)

def fetch(account: str, password: str, folder: str, mid: str, timeout: int=45) -> bytes:
    deadline=time.time()+timeout
    while time.time()<deadline:
        c=imaplib.IMAP4_SSL('imap.gmail.com',993); c.login(account,password); c.select(folder)
        typ,ids=c.search(None,'HEADER','Message-ID',f'"{mid}"')
        if typ=='OK' and ids and ids[0]:
            uid=ids[0].split()[-1]; _,raw=c.fetch(uid,'(RFC822)')
            c.logout()
            assert raw and isinstance(raw[0], tuple)
            return cast(bytes, raw[0][1])
        c.logout(); time.sleep(1)
    raise TimeoutError(f'missing {mid}')

def body(raw):
    m=BytesParser(policy=policy.default).parsebytes(raw)
    part=m.get_body(preferencelist=('plain',)); return part.get_content() if part else ''

seen=Path(tempfile.mkdtemp())/'seen.json'
adapter=EmailAdapter(seen_path=seen); gateway=Gateway()

send_client('I am applying for a visitor visa.',ROOT)
raw=fetch(AGENT,APASS,'INBOX',ROOT); incoming=adapter.receive_email(raw)
assert incoming is not None
reply=gateway.handle(incoming); receipt=adapter.send(reply)
assert receipt.ok and receipt.external_id, receipt.error
fetch(CLIENT,CPASS,'INBOX',receipt.external_id)

send_client('Here is my passport.',DOCMID,ROOT,SAMPLE)
raw=fetch(AGENT,APASS,'INBOX',DOCMID); incoming=adapter.receive_email(raw)
assert incoming is not None
assert len(incoming.attachments)==1 and incoming.attachments[0].mime=='image/jpeg'
reply=gateway.handle(incoming); receipt=adapter.send(reply)
assert receipt.ok and receipt.external_id, receipt.error
raw_reply=fetch(CLIENT,CPASS,'INBOX',receipt.external_id); text=body(raw_reply)
low=text.lower()
assert 'funds' in low and 'accommodation' in low, text
assert 'passport: provide' not in low and 'needs ocr' not in low, text
print(f'PASS {TAG}')
print('attachment=image/jpeg; OCR=macos-vision; LLM=deepseek-chat')
print('reply='+' '.join(text.split()))
