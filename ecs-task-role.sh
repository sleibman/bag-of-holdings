# Create a trust policy JSON file
cat > task-execution-trust.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the IAM role with the trust policy
aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document file://task-execution-trust.json

# Attach the required policies to the role
aws iam attach-role-policy --role-name ecsTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam attach-role-policy --role-name ecsTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

# Verify the role was created
aws iam get-role --role-name ecsTaskExecutionRole

