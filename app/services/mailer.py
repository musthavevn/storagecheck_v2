import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_smtp(host:str, port:int, user:str, pw:str, to_email:str, subject:str, body:str):
    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if int(port) == 465:
        s = smtplib.SMTP_SSL(host, int(port))
    else:
        s = smtplib.SMTP(host, int(port))
        s.starttls()

    s.login(user, pw)
    s.send_message(msg)
    s.quit()