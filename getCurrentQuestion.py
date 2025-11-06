import json
import boto3

dynamodb = boto3.resource('dynamodb')
tasks_table = dynamodb.Table('Interview_Tasks')

def lambda_handler(event, context):
    # API 경로에서 executionArn을 가져옴 (예: /interviews/arn:...)
    execution_arn = event['pathParameters']['executionArn']

    response = tasks_table.get_item(Key={'executionArn': execution_arn})

    if 'Item' in response:
        item = response['Item']
        # 한 번 전달한 질문은 다시 전달하지 않도록 테이블에서 삭제
        tasks_table.delete_item(Key={'executionArn': execution_arn})
        return {
            'statusCode': 200,
            'body': json.dumps({
                'question': item['question'],
                'taskToken': item['taskToken'] # 프론트엔드가 답변 제출 시 사용할 열쇠
            })
        }
    else:
        # 아직 Step Functions가 질문을 준비하지 못함
        return {
            'statusCode': 204, # No Content
            'body': json.dumps({'message': 'Question not ready yet. Please wait.'})
        }
