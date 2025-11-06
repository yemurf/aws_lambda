import json
import boto3

sfn_client = boto3.client('stepfunctions')

def lambda_handler(event, context):
    body = json.loads(event.get('body', '{}'))
    task_token = body.get('taskToken')
    answer = body.get('answer')

    if not task_token or answer is None:
        return {'statusCode': 400, 'body': 'taskToken and answer are required.'}

    # 토큰을 사용하여 멈춰있던 워크플로를 재개시키고, 답변(answer)을 결과로 전달
    sfn_client.send_task_success(
        taskToken=task_token,
        output=json.dumps({'answer': answer}) # 이 output이 'Save Answer' 람다의 event가 됨
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'status': 'Answer submitted successfully.'})
    }
