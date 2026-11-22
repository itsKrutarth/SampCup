# Deploying SampCup (AWS, serverless, Terraform)

Everything in AWS is created, changed and deleted by Terraform in `infra/`. Nothing is
clicked together in the console.

## What runs
| Piece | AWS service | Cost at our size |
|---|---|---|
| Website files | S3 (private bucket) | cents |
| HTTPS, caching, one address for site and API | CloudFront | free tier (1 TB, 10M requests a month) |
| API | Lambda (Python 3.12, arm64) behind a function URL | free tier (1M requests a month) |
| Database | DynamoDB on-demand, point-in-time recovery | free tier for storage; cents for requests |
| Logs | CloudWatch Logs, 30-day retention (`infra/foundation`, kept through teardowns) | free tier (5 GB) |
| Alarms and dashboard | CloudWatch alarms (4), dashboard (1), SNS | free tier |
| DNS for sampcup.com | Route 53 hosted zone (`infra/foundation`, kept through teardowns) | $0.50 a month |
| Certificate | ACM (`infra/foundation`) | free |
| Terraform state | S3 bucket `sampcup-tfstate-<account>` (from `infra/bootstrap`) | ~$0 |

There is no API Gateway, VPC, NAT gateway or server, which are the usual hidden costs.
The domain stays registered at Namecheap; only its nameservers point to Route 53.

Three Terraform layers, each with its own state:
1. `infra/bootstrap`: the state bucket (once per account, local state).
2. `infra/foundation`: Route 53 zone, certificate and the API's log group (long-lived;
   `infra/foundation.sh`), so a teardown keeps the logs.
3. `infra/terraform`: the app (`infra/deploy.sh` / `infra/destroy.sh`, safe to tear down).

## Commands (from the repo root, with AWS CLI credentials)
```sh
infra/deploy.sh plan        # build, then show what would change
infra/deploy.sh apply       # build and deploy (asks before changing anything)
infra/destroy.sh            # take everything down (the state bucket stays)
infra/ops.sh status         # alarms and last hour's traffic
infra/ops.sh logs           # follow the API log live
infra/ops.sh errors         # API errors from the last 24 hours
infra/ops.sh cost           # this month's AWS cost so far
```
First time in a new AWS account: `cd infra/bootstrap && terraform init && terraform apply`,
then `infra/foundation.sh apply`, then `infra/deploy.sh apply`.

## After a fresh deploy
```sh
cd backend
export TABLE_NAME=sampcup-prod AWS_REGION=us-east-1
.venv/bin/python -m app.cli create-admin <your-username>    # asks for your password
.venv/bin/python -m app.cli create-judges                   # court-1..court-9, prints PINs once
```
Then set the event date and registration in Admin → Overview.

## Connecting sampcup.com (once)
1. `infra/foundation.sh output name_servers` lists four Route 53 nameservers.
2. At Namecheap: Domain List → sampcup.com → Manage → Nameservers → **Custom DNS**, enter the
   four names, save. (Namecheap's own records, like the old URL redirect, stop being used.)
3. Within minutes to a few hours the certificate is issued
   (`infra/foundation.sh output certificate_status` shows `ISSUED`).
4. `infra/deploy.sh apply`: it sees the issued certificate and adds sampcup.com and
   www.sampcup.com (www redirects to sampcup.com). Every later deploy keeps them.

## Alerts by email
`infra/deploy.sh apply -var alert_email=<address>`, then click the confirmation link AWS
emails. Alarms: API server errors, Lambda errors, Lambda throttles, CloudFront 5xx rate.

## Known limit
New AWS accounts may run only 10 Lambda functions at once. CloudFront caching and the
judge app's retries make that enough for the event; to raise it, open a Service Quotas
support case for "Lambda concurrent executions".
