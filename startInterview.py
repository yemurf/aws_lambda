import json
import boto3
import os

sfn_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

def lambda_handler(event, context):
    body = json.loads(event.get('body', '{}'))
    job_posting_id = body.get('job_posting_id')

    if not job_posting_id:
        return {'statusCode': 400, 'body': json.dumps({'error': 'job_posting_id is required.'})}

    # Step Functions 워크플로 실행 시작
    response = sfn_client.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input=json.dumps({'job_posting_id': job_posting_id})
    )

    # 프론트엔드가 이 면접을 추적할 수 있도록 고유 ID를 반환
    return {
        'statusCode': 202, # Accepted
        'body': json.dumps({'executionArn': response['executionArn']})
    }
