# lambda_function.py
import json
import boto3
import os

bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

def lambda_handler(event, context):
    # 1. API Gateway로부터 job_posting_id와 기업 지정 질문 받기
    path_params = event.get('pathParameters', {})
    job_posting_id = path_params.get('job_posting_id')

    body = json.loads(event.get('body', '{}'))
    company_questions = body.get('company_questions', []) # 기업이 직접 등록한 질문 리스트

    # 2. DynamoDB에서 해당 공고의 분석 결과 가져오기
    response = table.get_item(Key={'job_posting_id': job_posting_id})
    item = response.get('Item')
    if not item:
        return {'statusCode': 404, 'body': 'Job posting not found'}

    core_competencies = item['analysis']['core_competencies']

    # 3. LLM에 질문 생성을 요청하는 프롬프트 구성
    prompt = f"""
    Human: 다음 핵심 역량들에 대해 지원자의 경험과 문제 해결 능력을 심층적으로 파악할 수 있는 행동 기반 면접 질문(Behavioral Event Interview)을 역량별로 2개씩 생성해줘.
    결과는 반드시 아래와 같은 JSON 배열 형식으로만 응답해줘. 다른 설명은 붙이지 마.

    [
      {{"competency": "역량명1", "question": "질문 내용1"}},
      {{"competency": "역량명1", "question": "질문 내용2"}},
      {{"competency": "역량명2", "question": "질문 내용3"}},
      ...
    ]

    <core_competencies>
    {', '.join(core_competencies)}
    </core_competencies>

    Assistant:
    """

    # 4. Bedrock API 호출 (이전과 동일한 로직)
    # ... (invoke_model 호출 부분)
    # response_body = ...
    # generated_questions = json.loads(response_body.get('completion'))

    # --- (이 부분은 실제 Bedrock 호출 코드로 대체해야 합니다) ---
    # 아래는 예시 결과 데이터입니다.
    generated_questions = [
        {"competency": core_competencies[0], "question": f"{core_competencies[0]} 역량이 가장 중요했던 프로젝트 경험에 대해 말씀해주세요."},
        {"competency": core_competencies[0], "question": f"{core_competencies[0]} 역량을 발휘하여 팀 내 갈등을 해결한 경험이 있나요?"}
    ]
    # --- 예시 데이터 끝 ---

    # 5. DynamoDB에 기업 지정 질문과 AI 생성 질문 업데이트
    table.update_item(
        Key={'job_posting_id': job_posting_id},
        UpdateExpression="SET company_questions = :c, generated_questions = :g",
        ExpressionAttributeValues={
            ':c': company_questions,
            ':g': generated_questions
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Questions generated and saved successfully'})
    }
