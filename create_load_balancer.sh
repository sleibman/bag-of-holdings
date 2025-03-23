
source .env

# Create a load balancer
aws elbv2 create-load-balancer --name fund-holdings-lb --subnets ${VPC_SUBNET_ID_1} ${VPC_SUBNET_ID_2} --security-groups ${VPC_SECURITY_GROUP_ID_1} ${VPC_SECURITY_GROUP_ID_2}

# Get the load balancer ARN
LB_ARN=$(aws elbv2 describe-load-balancers --names fund-holdings-lb --query "LoadBalancers[0].LoadBalancerArn" --output text)

# Create a target group
aws elbv2 create-target-group --name fund-holdings-tg --protocol HTTP --port 8000 --vpc-id ${VPC_ID} --target-type ip --health-check-path / --health-check-interval-seconds 30

# Get the target group ARN
TG_ARN=$(aws elbv2 describe-target-groups --names fund-holdings-tg --query "TargetGroups[0].TargetGroupArn" --output text)

# Create a listener
aws elbv2 create-listener --load-balancer-arn $LB_ARN --protocol HTTP --port 80 --default-actions Type=forward,TargetGroupArn=$TG_ARN

# Update the ECS service to use the load balancer
ecs-cli compose --project-name fund-holdings service up --container-name api --container-port 8000 --target-group-arn $TG_ARN --cluster-config fund-holdings

aws ecs update-service \
  --cluster fund-holdings \
  --service $SERVICE_NAME \
  --load-balancers "targetGroupArn=$TG_ARN,containerName=api,containerPort=8000" \
  --force-new-deployment
