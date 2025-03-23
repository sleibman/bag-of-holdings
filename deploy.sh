#!/bin/bash
# deploy.sh

# Set your variables
REGION=us-east-1
REPO_NAME=fund-holdings-api
STACK_NAME=fund-holdings-api-stack

# Get repository URI
REPO_URI=$(aws ecr describe-repositories --repository-names ${REPO_NAME} --query "repositories[0].repositoryUri" --output text)

# Build and push updated Docker image
docker build -t ${REPO_NAME} .
docker tag ${REPO_NAME}:latest ${REPO_URI}:latest
docker push ${REPO_URI}:latest

# Update the ECS service to force new deployment
SERVICE_NAME=$(aws cloudformation describe-stack-resources --stack-name $STACK_NAME --logical-resource-id EcsService --query "StackResources[0].PhysicalResourceId" --output text)
CLUSTER_NAME=$(aws cloudformation describe-stack-resources --stack-name $STACK_NAME --logical-resource-id EcsCluster --query "StackResources[0].PhysicalResourceId" --output text)

aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --force-new-deployment

echo "Deployment initiated. Your API will be updated shortly."


