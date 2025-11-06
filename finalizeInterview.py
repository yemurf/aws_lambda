import json
import boto3
import uuid

dynamodb = boto3.resource('dynamodb')
sessions_table = dynamodb.Table('Interview_Sessions')

def lambda_handler(event, context):
    # Step Functions의 최종 상태를 받음
    final_state = event

    session_id = str(uuid.uuid4())

    sessions_table.put_item(
        Item={
            'session_id': session_id,
            'job_posting_id': final_state['job_posting_id'],
            'questions': final_state['questions'],
            'answers': final_state['answers'],
            'status': 'COMPLETED'
        }
    )

    return {
        'status': 'success',
        'session_id': session_id
    }
