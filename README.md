# bag-of-holdings
Service for ingesting, storing, and returning information on the holdings of mutual funds and ETFs

## Creating the database

Create a .env file by copying `env-template` to `.env` and inserting appropriate values.

run
```
sh pg_rds_setup.sh
```
this will run aws command line tools to create the database, and will create and execute the `create_tables.sql` file
with SQL instructions for creating the appropriate tables in the database.

After doing this for the first time, I realized that I hadn't quite specified the exact schema I wanted.
To edit the schema, I created `alter_fund_info_table.sql` with migration instructions that can be invoked by running
```
sh run_migration.sh
```
This has been kept in order to show a very simple pattern for running schema migrations.

## Populating the database

Assuming that a folder exists with csv files in the form specified by etf-holdings repository, consume all that
data and push it to the database by running:
```
python etf_processor.py
```

## Deploying the service (attempt #1)

The service consists of:

1. A FastAPI application to serve the API
2. AWS deployment configuration using AWS Lambda and API Gateway
3. Database access layer for retrieving fund data


* `app.py`: API service 
* `serverless.yml`: fund-holdings-api spec
* `mangum_handler.py`: AWS Lambda handler for interacting with FastAPI service
* `requirements.txt`: Python requirements (note that this is for the deployed service and may not exactly match what's needed for utilities above)

### Deploy to AWS
```
npm install -g serverless
npm install serverless-python-requirements
serverless deploy
```

## Deploying the service to AWS using Fargate and a Docker image in ECR

```
# Log in to AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

# Create an ECR repository
aws ecr create-repository --repository-name fund-holdings-api --region us-east-1

# Get the repository URI
export REPO_URI=$(aws ecr describe-repositories --repository-names fund-holdings-api --query "repositories[0].repositoryUri" --output text)

# Build, tag, and push your Docker image
docker build -t fund-holdings-api .
docker tag fund-holdings-api:latest ${REPO_URI}:latest
docker push ${REPO_URI}:latest
```

```
# Set up a CLI profile
ecs-cli configure profile --profile-name fund-holdings-profile --access-key xxxxx --secret-key "xxxxx"

# Configure the cluster
ecs-cli configure --cluster fund-holdings --default-launch-type FARGATE --region us-east-1 --config-name fund-holdings

# Create the cluster
ecs-cli up --cluster-config fund-holdings --force
```

Create a CloudWatch log group
```
aws logs create-log-group --log-group-name fund-holdings-logs
```

### Deploy to ECS

Make sure the necessary role exists
```
sh ecs-task-role.sh
```

```
export ECR_REPOSITORY_URI=$REPO_URI
( source .env; ecs-cli compose --project-name fund-holdings --file docker-compose.yml --ecs-params ecs-params.yml service up --create-log-groups --cluster-config fund-holdings )
```

### Add load balancer

```
# Create a load balancer
sh create_load_balancer.sh
```

Get the load balancer URL with:
`aws elbv2 describe-load-balancers --names fund-holdings-lb --query "LoadBalancers[0].DNSName" --output text`


### Add HTTPS

```
# First, request an SSL certificate using AWS Certificate Manager
aws acm request-certificate --domain-name api.divest.info --validation-method DNS

# Get the certificate ARN
export CERT_ARN=$(aws acm list-certificates --query "CertificateSummaryList[?DomainName=='api.divest.info'].CertificateArn" --output text)
```

Then add DNS validation records to the DNS config. The following command will show the name and value of a CNAME record
we need to add to Route53. Then re-run it until it says ISSUED instead of PENDING_VALIDATION:
`aws acm describe-certificate --certificate-arn $CERT_ARN`.

Then add an HTTPS listener to the load balancer:
```
# Get your load balancer ARN if you don't have it
export LB_ARN=$(aws elbv2 describe-load-balancers --names fund-holdings-lb --query "LoadBalancers[0].LoadBalancerArn" --output text)

# Get your target group ARN if you don't have it
export TG_ARN=$(aws elbv2 describe-target-groups --names fund-holdings-tg --query "TargetGroups[0].TargetGroupArn" --output text)

# Create an HTTPS listener
aws elbv2 create-listener --load-balancer-arn $LB_ARN --protocol HTTPS --port 443 --certificates CertificateArn=$CERT_ARN --default-actions Type=forward,TargetGroupArn=$TG_ARN
```

Redirect HTTP to HTTPS
```
# Get the ARN of your HTTP listener
export HTTP_LISTENER_ARN=$(aws elbv2 describe-listeners --load-balancer-arn $LB_ARN --query "Listeners[?Port==\`80\`].ListenerArn" --output text)

# Modify the HTTP listener to redirect to HTTPS
aws elbv2 modify-listener --listener-arn $HTTP_LISTENER_ARN --default-actions Type=redirect,RedirectConfig="{Protocol=HTTPS,Port=443,Host='#{host}',Path='/#{path}',Query='#{query}',StatusCode=HTTP_301}"
```

Update security group to allow HTTPS traffic
```
# Get your load balancer security group
export SG_ID=$(aws elbv2 describe-load-balancers --names fund-holdings-lb --query "LoadBalancers[0].SecurityGroups[0]" --output text)

# Allow HTTPS traffic
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0
```

Use the load balancer URL we got with `aws elbv2 describe-load-balancers --names fund-holdings-lb --query "LoadBalancers[0].DNSName" --output text` and create a CNAME record that points from api.divest.info to that URL.

Then we should be able to get a valid response from a query like


### Local development
To start the API locally at http://localhost:8000
```
pip install -r requirements.txt
uvicorn app:app --reload
```

To run a test of a locally deploy (localhost:8000) server:
```
python test_local_api.py
```

# After updates to app.py

Update and push the docker image
```
docker build -t fund-holdings-api .
docker tag fund-holdings-api:latest ${REPO_URI}:latest
docker push ${REPO_URI}:latest
```

Update ECS to use the new image
```
aws ecs update-service --cluster fund-holdings --service fund-holdings --force-new-deployment
```

# Creating API keys

Create an API key with:
```
curl -X POST https://api.divest.info/admin/api-keys \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "description": "API access for Company XYZ"}'
```

Use the API key:
```
curl -H "X-API-Key: your-api-key" https://api.divest.info/api/fund/PLTL
```

# Fund Holdings API

A RESTful API service that provides ETF fund holdings information.

## Features

- Retrieve fund metadata and holdings information
- Filter holdings by specific stock symbols
- JSON response format
- Deployed as serverless application on AWS

## API Endpoints

### GET /api/fund/{symbol}

Retrieves fund information and its latest holdings.

**Path Parameters:**
- `symbol` (required): The fund symbol (e.g., 'PLTL')

**Query Parameters:**
- `holdings` (optional): List of specific holding symbols to filter by

**Example Request:**

```
GET /api/fund/PLTL?holdings=AAPL,MSFT,GOOGL
```

**Example Response:**
```json
{
  "fund_id": "4220",
  "fund_symbol": "PLTL",
  "fund_name": "Principal US Small-Cap Adaptive Multi-Factor ETF",
  "inception_date": "2021-05-19",
  "issuer": "Principal",
  "holdings": [
    {
      "holding_symbol": "AAPL",
      "holding_name": "Apple Inc.",
      "percent": 0.0057,
      "timestamp_reported": "2023-10-11T00:00:00"
    },
    {
      "holding_symbol": "MSFT",
      "holding_name": "Microsoft Corporation",
      "percent": 0.0042,
      "timestamp_reported": "2023-10-11T00:00:00"
    }
  ]
}
```



