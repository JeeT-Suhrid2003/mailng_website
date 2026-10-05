import json
import os
import smtplib
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ============================================================
# Environment variables
# ============================================================

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_APP_PASS = os.environ.get("SENDER_APP_PASS")

EMAIL_SUBJECT = os.environ.get(
    "EMAIL_SUBJECT",
    "Predefined Subject"
)

EMAIL_BODY = os.environ.get(
    "EMAIL_BODY",
    '''Dear Sir/Mam,
blah blah blah
.................'''
)

ALLOWED_ORIGIN = os.environ.get(
    "ALLOWED_ORIGIN",
    "https://emailngwebsite.vercel.app"
)


# ============================================================
# Rate limiting
# ============================================================

DAILY_LIMIT = 100
TABLE_NAME = "EmailRateLimiter"

dynamodb = boto3.resource("dynamodb")
rate_table = dynamodb.Table(TABLE_NAME)


def check_and_increment_limit():
    """
    Atomically increments today's counter.

    Returns:
        True  -> request is allowed
        False -> daily limit has been reached
    """

    # Use UTC date so the counter resets consistently.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"Checking daily rate limit for {today}")

    try:

        # ----------------------------------------------------
        # Atomically increment only if current count < 100.
        #
        # If the item doesn't exist, attribute_not_exists()
        # allows the first request to create it.
        # ----------------------------------------------------

        response = rate_table.update_item(
            Key={
                "date_key": today
            },

            UpdateExpression="ADD #count :increment",

            ExpressionAttributeNames={
                "#count": "count"
            },

            ExpressionAttributeValues={
                ":increment": 1,
                ":limit": DAILY_LIMIT
            },

            ConditionExpression=(
                "attribute_not_exists(#count) OR #count < :limit"
            ),

            ReturnValues="UPDATED_NEW"
        )

        new_count = response["Attributes"]["count"]

        print(
            f"Daily email count: {new_count}/{DAILY_LIMIT}"
        )

        return True

    except ClientError as e:

        error_code = e.response["Error"]["Code"]

        # ----------------------------------------------------
        # This means the condition:
        #
        # count < 100
        #
        # failed.
        # ----------------------------------------------------

        if error_code == "ConditionalCheckFailedException":

            print(
                f"Daily limit reached: {DAILY_LIMIT}"
            )

            return False

        # ----------------------------------------------------
        # Any other DynamoDB error should NOT allow unlimited
        # email sending.
        # ----------------------------------------------------

        print(
            "DynamoDB error:",
            e
        )

        raise


# ============================================================
# Lambda handler
# ============================================================

def lambda_handler(event, context):

    print("=== LAMBDA STARTED ===")
    print("Event:", json.dumps(event))

    try:

        # ----------------------------------------------------
        # 1. Get HTTP method
        # ----------------------------------------------------

        method = (
            event
            .get("requestContext", {})
            .get("http", {})
            .get("method", "")
        )

        print("HTTP method:", method)

        # Lambda Function URL handles CORS preflight itself,
        # but this keeps the function safe if OPTIONS reaches it.
        if method == "OPTIONS":

            print("OPTIONS request")

            return {
                "statusCode": 204,
                "body": ""
            }

        # ----------------------------------------------------
        # 2. Check request origin
        # ----------------------------------------------------

        request_headers = event.get("headers") or {}

        origin = (
            request_headers.get("origin")
            or request_headers.get("Origin")
        )

        print("Origin:", origin)

        if origin and origin != ALLOWED_ORIGIN:

            print(
                f"Rejected origin: {origin}"
            )

            return {
                "statusCode": 403,
                "body": json.dumps({
                    "error": "Forbidden origin."
                })
            }

        # ----------------------------------------------------
        # 3. Parse request body
        # ----------------------------------------------------

        raw_body = event.get("body") or "{}"

        print("Raw body:", raw_body)

        if isinstance(raw_body, str):
            body = json.loads(raw_body)
        else:
            body = raw_body

        recipient = str(
            body.get("recipient", "")
        ).strip()

        print("Recipient:", recipient)

        # ----------------------------------------------------
        # 4. Validate recipient
        # ----------------------------------------------------

        if not recipient or "@" not in recipient:

            print("Invalid recipient")

            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "A valid recipient email is required."
                })
            }

        # ----------------------------------------------------
        # 5. Check environment variables
        # ----------------------------------------------------

        if not SENDER_EMAIL:

            print(
                "ERROR: SENDER_EMAIL is missing"
            )

            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "SENDER_EMAIL environment variable is missing."
                })
            }

        if not SENDER_APP_PASS:

            print(
                "ERROR: SENDER_APP_PASS is missing"
            )

            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "SENDER_APP_PASS environment variable is missing."
                })
            }

        # ----------------------------------------------------
        # 6. Check daily limit
        # ----------------------------------------------------

        print("Checking DynamoDB rate limit...")

        allowed = check_and_increment_limit()

        if not allowed:

            print("=== DAILY LIMIT EXCEEDED ===")

            return {
                "statusCode": 429,
                "body": json.dumps({
                    "error": "Daily email limit of 100 has been reached. Try again tomorrow."
                })
            }

        # ----------------------------------------------------
        # 7. Build email
        # ----------------------------------------------------

        msg = MIMEMultipart()

        msg["From"] = (
            f"Notification <{SENDER_EMAIL}>"
        )

        msg["To"] = recipient

        msg["Subject"] = EMAIL_SUBJECT

        msg.attach(
            MIMEText(
                EMAIL_BODY,
                "plain"
            )
        )

        # ----------------------------------------------------
        # 8. Connect to Gmail SMTP
        # ----------------------------------------------------

        print(
            "Connecting to Gmail SMTP..."
        )

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=20
        ) as server:

            print(
                "SMTP connection established"
            )

            server.login(
                SENDER_EMAIL,
                SENDER_APP_PASS
            )

            print(
                "Gmail authentication successful"
            )

            print(
                "About to call sendmail..."
            )

            server.sendmail(
                SENDER_EMAIL,
                recipient,
                msg.as_string()
            )

            print(
                "sendmail() completed successfully"
            )

        print(
            "=== EMAIL SENT SUCCESSFULLY ==="
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Email sent successfully!"
            })
        }

    # --------------------------------------------------------
    # Invalid JSON
    # --------------------------------------------------------

    except json.JSONDecodeError:

        print(
            "Invalid JSON body"
        )

        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Invalid JSON request."
            })
        }

    # --------------------------------------------------------
    # Gmail authentication failure
    # --------------------------------------------------------

    except smtplib.SMTPAuthenticationError:

        print(
            "Gmail authentication failed"
        )

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Gmail authentication failed. Check SENDER_EMAIL and SENDER_APP_PASS."
            })
        }

    # --------------------------------------------------------
    # DynamoDB errors
    # --------------------------------------------------------

    except ClientError as e:

        print(
            "AWS/DynamoDB error:",
            str(e)
        )

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Rate limiter error. Email was not sent."
            })
        }

    # --------------------------------------------------------
    # Everything else
    # --------------------------------------------------------

    except Exception as e:

        print(
            "=== LAMBDA ERROR ==="
        )

        print(
            "Error type:",
            type(e).__name__
        )

        print(
            "Error:",
            str(e)
        )

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Failed to send email."
            })
        }

