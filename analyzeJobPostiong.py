# lambda_function.py
import json
import boto3
import os
import uuid

s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1') # Bedrock 사용 가능 리전
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE']) # 환경 변수에서 테이블 이름 가져오기

def lambda_handler(event, context):
    # 1. S3 이벤트에서 버킷 이름과 파일 키(이름) 가져오기
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # 2. S3에서 파일 내용 읽기 (단순 .txt 파일로 가정)
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')

    # 3. Bedrock LLM에 보낼 프롬프트 구성
    prompt = f"""
    Human: 다음 채용 공고 텍스트를 분석해서, 이 회사의 '인재상', '경영철학', 그리고 이 직무에 필요한 '핵심역량' 5가지를 추출해줘.
    결과는 반드시 아래와 같은 JSON 형식으로만 응답해줘. 다른 설명은 붙이지 마.

    {{
      "ideal_candidate": ["인재상1", "인재상2", ...],
      "philosophy": "회사의 경영철학 요약",
      "core_competencies": ["역량1", "역량2", "역량3", "역량4", "역량5"]
    }}

    <job_posting>
    {content}
    </job_posting>

    Assistant:
    """

    # 4. Bedrock API 호출 (Claude 모델 예시)
    body = json.dumps({
        "prompt": prompt,
        "max_tokens_to_sample": 2000,
        "temperature": 0.1,
    })

    modelId = 'anthropic.claude-v2'
    accept = 'application/json'
    contentType = 'application/json'

    response = bedrock_runtime.invoke_model(body=body, modelId=modelId, accept=accept, contentType=contentType)
    response_body = json.loads(response.get('body').read())

    # 5. LLM의 응답(JSON 텍스트)을 파싱
    analysis_result = json.loads(response_body.get('completion'))

    # 6. DynamoDB에 저장
    job_posting_id = str(uuid.uuid4())
    item = {
        'job_posting_id': job_posting_id,
        'original_s3_key': key,
        'analysis': analysis_result,
        'company_questions': [], # 기업 지정 질문을 위한 빈 리스트
        'generated_questions': [] # AI 생성 질문을 위한 빈 리스트
    }
    table.put_item(Item=item)

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Analysis complete', 'job_posting_id': job_posting_id})
    }
