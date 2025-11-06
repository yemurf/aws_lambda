import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
# 환경 변수에서 테이블 이름을 가져옵니다.
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

def lambda_handler(event, context):
    # 1. API Gateway의 경로 변수에서 job_posting_id 가져오기
    try:
        path_params = event.get('pathParameters', {})
        job_posting_id = path_params.get('job_posting_id')
        if not job_posting_id:
            raise ValueError("job_posting_id is missing from path parameters.")

        # 2. 요청 본문(Request Body)에서 새로운 질문 목록 가져오기
        body = json.loads(event.get('body', '{}'))
        company_questions = body.get('company_questions') # 'company_questions' 키는 필수
        if company_questions is None:
            raise ValueError("company_questions is missing from request body.")

    except (ValueError, json.JSONDecodeError) as e:
        return {
            'statusCode': 400, # Bad Request
            'body': json.dumps({'error': str(e)})
        }

    # 3. DynamoDB에 company_questions 필드를 업데이트(교체)
    try:
        response = table.update_item(
            Key={'job_posting_id': job_posting_id},
            # 'company_questions' 필드의 값을 :c 값으로 설정(SET)합니다.
            UpdateExpression="SET company_questions = :c",
            # UpdateExpression에서 사용할 변수(:c)의 실제 값을 지정합니다.
            ExpressionAttributeValues={
                ':c': company_questions
            },
            ReturnValues="UPDATED_NEW" # 업데이트된 후의 값을 반환하도록 설정
        )
        return {
            'statusCode': 200, # OK
            'body': json.dumps({
                'message': 'Company questions updated successfully.',
                'updatedAttributes': response.get('Attributes', {})
            })
        }
    except Exception as e:
        # DynamoDB 업데이트 중 에러 발생 시
        return {
            'statusCode': 500, # Internal Server Error
            'body': json.dumps({'error': f"Could not update the database: {str(e)}"})
        }
