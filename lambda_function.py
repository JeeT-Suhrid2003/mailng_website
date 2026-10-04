import json
import smtplib
import os
from email.mime.text import MIMEText

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASS = os.environ.get("SENDER_APP_PASS") # 16-char app password

SUBJECT = os.environ.get("EMAIL_SUBJECT", "Predefined Message")
BODY = os.environ.get("EMAIL_BODY", "Here is the fixed content you requested.")

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        recipient = body.get("recipient", "").strip()

        if not recipient or "@" not in recipient:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Invalid email address."})
            }

        msg = MIMEText(BODY)
        msg['Subject'] = SUBJECT
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, recipient, msg.as_string())

        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"message": "Sent successfully!"})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }