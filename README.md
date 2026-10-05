# Mailing Website

This project contains the frontend landing page and the AWS Lambda backend used to send emails through Gmail SMTP.

## Project purpose

This folder is a separate website project from the other files in the parent `aws-testing` directory. It is meant for a simple, lightweight contact or notification flow where a browser page submits an email address to a backend function that sends the message.

## Contents

- `index.html` — static landing page / website front-end
- `lambda_function.py` — AWS Lambda email sender

## How it works

1. The front end sends a POST request to the Lambda function.
2. The Lambda validates the request payload and origin.
3. It checks a daily DynamoDB rate limit.
4. It sends the email using Gmail SMTP.
5. It returns a JSON response with the status code.

## Required environment variables

Set these in the Lambda configuration:

- `SENDER_EMAIL` — Gmail address used as the sender
- `SENDER_APP_PASS` — Gmail app password for that sender account
- `EMAIL_SUBJECT` — Optional subject line
- `EMAIL_BODY` — Optional email body
- `ALLOWED_ORIGIN` — Front-end domain allowed to call the API

## Example request body

```json
{
  "recipient": "someone@example.com"
}
```

## Rate limiting

The Lambda uses DynamoDB to track how many emails were sent in the current UTC day.

- Table name: `EmailRateLimiter`
- Primary key: `date_key`
- Default daily limit: `100`

## Deployment notes

- Deploy `lambda_function.py` as an AWS Lambda function.
- Create a DynamoDB table named `EmailRateLimiter` with a `date_key` string key.
- Give the Lambda permission to read/write the DynamoDB table.
- Use a Gmail app password, not the normal account password.
- Restrict `ALLOWED_ORIGIN` to the exact origin of the website that calls this API.

## Response codes

- `200` — email sent successfully
- `400` — invalid request or missing recipient
- `403` — forbidden origin
- `429` — daily email limit reached
- `500` — AWS, SMTP, or other internal error

## Security notes

- Keep credentials in environment variables, not source code.
- Restrict the allowed origin to the expected website domain.
- Avoid using this setup for high-volume bulk emailing; use a dedicated mail service for large-scale sending.
