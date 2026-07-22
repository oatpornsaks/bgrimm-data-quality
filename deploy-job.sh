#!/bin/bash
# Usage: ./deploy-job.sh <job-json-file> [aws-profile]
# Example: ./deploy-job.sh glue-dq/bgrimm-datagov-amr-data-quality/bgrimm-datagov-amr-data-quality.json bgrimm-prod

JOB_FILE="$1"
PROFILE="${2:-bgrimm-prod}"

if [ -z "$JOB_FILE" ]; then
  echo "Usage: ./deploy-job.sh <job-json-file> [aws-profile]"
  exit 1
fi

JOB_NAME="$(jq -r '.name' "$JOB_FILE")"
TEMP_FILE=$(mktemp /tmp/glue-job-XXXXXX.json)

echo "Deploying job: $JOB_NAME"
echo "Profile: $PROFILE"

# Convert camelCase JSON to PascalCase format for create-job
jq '{
  Name: .name,
  JobMode: .jobMode,
  Description: .description,
  Role: .role,
  ExecutionProperty: {
    MaxConcurrentRuns: .executionProperty.maxConcurrentRuns
  },
  Command: {
    Name: .command.name,
    ScriptLocation: .command.scriptLocation,
    PythonVersion: .command.pythonVersion
  },
  DefaultArguments: .defaultArguments,
  Connections: {
    Connections: .connections.connections
  },
  MaxRetries: .maxRetries,
  Timeout: .timeout,
  NumberOfWorkers: .numberOfWorkers,
  WorkerType: .workerType,
  GlueVersion: .glueVersion,
  ExecutionClass: .executionClass,
  CodeGenConfigurationNodes: (.codeGenConfigurationNodes | fromjson)
}' "$JOB_FILE" > "$TEMP_FILE"

# Try to delete existing job (ignore error if not found)
echo "Deleting existing job (if exists)..."
aws glue delete-job --job-name "$JOB_NAME" --profile "$PROFILE" 2>/dev/null

# Create job
echo "Creating job..."
aws glue create-job --cli-input-json "file://$TEMP_FILE" --profile "$PROFILE"

if [ $? -eq 0 ]; then
  echo "Successfully deployed: $JOB_NAME"
else
  echo "Failed to deploy: $JOB_NAME"
fi

# Cleanup
rm -f "$TEMP_FILE"
