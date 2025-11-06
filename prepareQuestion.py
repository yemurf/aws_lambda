import json
import boto3

dynamodb = boto3.resource('dynamodb')
tasks_table = dynamodb.Table('Interview_Tasks')

def lambda_handler(event, context):
    # Step Functions가 이 람다를 호출할 때 자동으로 event에 정보를 넣어줌
    current_state = event['Payload']
    task_token = event['Token']
    execution_arn = event['Execution']['Id']

    # 현재 질문 찾기
    current_question = current_state['questions'][current_state['current_index']]

    # '우체국' 테이블에 저장
    tasks_table.put_item(
        Item={
            'executionArn': execution_arn,
            'taskToken': task_token,
            'question': current_question
        }
    )
    return {} # 이 람다의 반환값은 중요하지 않음
