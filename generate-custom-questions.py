import json
import boto3
import os
import urllib.parse
import re

# --- 기본 설정 ---
BEDROCK_REGION = os.environ.get('AWS_REGION', 'us-east-1') # Lambda 환경 변수에서 리전 가져오기
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0" # 사용할 Bedrock 모델

# --- Boto3 클라이언트 초기화 ---
# Lambda 함수가 실행될 때마다 새로 생성되지 않도록 핸들러 함수 밖에 선언
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=BEDROCK_REGION)

# --- Bedrock: 채용 공고 질문 생성 함수 ---
def generate_job_posting_questions(ideal_candidate_text):
    """Bedrock을 호출하여 채용 공고 인재상 기반 질문 3개를 생성합니다."""
    prompt = f"""Human: 다음은 우리 회사의 인재상(idealCandidate) 설명입니다.

<idealCandidate>
{ideal_candidate_text}
</idealCandidate>

이 인재상을 바탕으로, 지원자가 이에 부합하는지 확인할 수 있는 구체적인 경험 기반의 면접 질문 3가지를 생성해 주세요.
질문은 반드시 다음 JSON 배열 형식으로만 대답해 주세요. 다른 설명은 모두 제외하고 JSON 코드만 반환해야 합니다.

[
  {{ "question": "첫 번째 질문 내용" }},
  {{ "question": "두 번째 질문 내용" }},
  {{ "question": "세 번째 질문 내용" }}
]

Assistant:
"""
    try:
        bedrock_request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000, # 충분한 토큰 설정
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        }
        # --- 👈 [수정] Guardrail 파라미터 주석 처리 ---
        response = bedrock_runtime.invoke_model(
            body=json.dumps(bedrock_request_body),
            modelId=MODEL_ID,
            accept='application/json',
            contentType='application/json'
            # guardrailIdentifier="gi0pmpvfbz8t",       # 👈 주석 처리
            # guardrailVersion="DRAFT"                  # 👈 주석 처리
        )
        response_body = json.loads(response.get('body').read())
        generated_text = response_body['content'][0]['text']

        # 생성된 텍스트가 JSON 형식이 맞는지 확인 후 파싱
        generated_questions = json.loads(generated_text)
        print(f"[Info] Bedrock이 생성한 채용 공고 질문: {generated_questions}")

        # 간단한 형식 검증
        if isinstance(generated_questions, list) and len(generated_questions) > 0 and 'question' in generated_questions[0]:
            return generated_questions[:3] # 최대 3개 반환
        else:
            print("[Error] Bedrock 채용 공고 질문 응답 형식이 예상과 다릅니다.")
            return []
    except json.JSONDecodeError as json_err:
        print(f"[Error] Bedrock 채용 공고 질문 JSON 파싱 실패: {json_err}")
        # Bedrock 원본 응답도 함께 로깅하면 디버깅에 도움됨
        try:
            print(f"Bedrock 원본 응답 (파싱 실패): {generated_text}")
        except NameError: # generated_text 변수가 정의되기 전에 에러난 경우
             pass
        return []
    except Exception as e:
        print(f"[Error] Bedrock 채용 공고 질문 생성 실패: {e}")
        return []

# --- Bedrock: 이력서 질문 생성 함수 ---
def generate_resume_questions(resume_text):
    """Bedrock을 호출하여 이력서 내용 기반 질문 2개를 생성합니다."""
    try:
        # 1. resume_text (JSON 문자열)를 파이썬 딕셔너리로 파싱
        resume_data = json.loads(resume_text)
        # 2. 실제 전공과 희망 직무 추출
        actual_major = resume_data.get('academicRecord', {}).get('major', '알 수 없음')
        actual_desired_job = resume_data.get('jobPreference', {}).get('desiredJob', '알 수 없음')
        actual_experience = resume_data.get('jobPreference', {}).get('experienceLevel', '알 수 없음')
    except json.JSONDecodeError:
        print("[Error] 이력서 JSON 파싱 실패. 기본 프롬프트 사용.")
        actual_major = "해당 전공"
        actual_desired_job = "지원 직무"
        actual_experience = "경력 수준"

    # 3. 추출한 정보로 프롬프트 동적 생성
    prompt = f"""Human: 당신은 지원자를 평가하는 면접관입니다. 다음은 지원자의 이력서 내용입니다.

<resume_content>
{resume_text}
</resume_content>

이 지원자는 **{actual_major}을(를) 전공**했으며 **{actual_desired_job}({actual_experience})**을(를) 희망하고 있습니다.
이력서에 구체적인 프로젝트나 경력 사항은 부족할 수 있습니다.

지원자의 **전공 지식, 학습 능력, 문제 해결 능력, 성장 가능성** 등을 파악할 수 있는 **기본적이면서도 의미 있는 질문 2개**를 생성해주세요.

[규칙]
1. 자기소개, 강점/약점 같은 너무 일반적인 질문은 제외합니다.
2. **학력({actual_major})**이나 **희망 직무({actual_desired_job})**와 관련된 질문을 우선적으로 고려합니다.
3. 질문 앞에 번호(1., 2.)를 붙여주세요.
4. 질문 외 다른 설명은 하지 마세요.
5. 반드시 다음 JSON 배열 형식으로만 대답해 주세요. 다른 설명은 모두 제외하고 JSON 코드만 반환해야 합니다.
[
  {{ "id": "q_resume_1", "text": "첫 번째 질문 내용" }},
  {{ "id": "q_resume_2", "text": "두 번째 질문 내용" }}
]

Assistant:
"""
    try:
        bedrock_request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        }
        # --- 👈 [수정] Guardrail 파라미터 주석 처리 ---
        response = bedrock_runtime.invoke_model(
            body=json.dumps(bedrock_request_body),
            modelId=MODEL_ID,
            accept='application/json',
            contentType='application/json'
            # guardrailIdentifier="gi0pmpvfbz8t",       # 👈 주석 처리
            # guardrailVersion="DRAFT"                  # 👈 주석 처리
        )
        response_body = json.loads(response.get('body').read())
        generated_text = response_body['content'][0]['text']

        # 생성된 텍스트가 JSON 형식이 맞는지 확인 후 파싱
        generated_questions = json.loads(generated_text)
        print(f"[Info] Bedrock이 생성한 이력서 질문: {generated_questions}")

        # 간단한 형식 검증
        if isinstance(generated_questions, list) and len(generated_questions) > 0 and 'id' in generated_questions[0] and 'text' in generated_questions[0]:
            return generated_questions[:2] # 최대 2개 반환
        else:
            print("[Error] Bedrock 이력서 질문 응답 형식이 예상과 다릅니다.")
            return []
    except json.JSONDecodeError as json_err:
        print(f"[Error] Bedrock 이력서 질문 JSON 파싱 실패: {json_err}")
        # Bedrock 원본 응답도 함께 로깅하면 디버깅에 도움됨
        try:
             print(f"Bedrock 원본 응답 (파싱 실패): {generated_text}")
        except NameError: # generated_text 변수가 정의되기 전에 에러난 경우
             pass
        return []
    except Exception as e:
        print(f"[Error] Bedrock 이력서 질문 생성 실패: {e}")
        return []

# --- 메인 Lambda 핸들러 함수 ---
def lambda_handler(event, context):
    try:
        # 1. S3 이벤트 정보 추출
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    except Exception as e:
        print(f"[Error] S3 이벤트 파싱 오류: {e}")
        return {'statusCode': 400, 'body': 'S3 이벤트 파싱 오류'}

    print(f"[Info] 감지된 버킷: {bucket}, 파일: {key}")

    output_key = "N/A" # 결과 파일 경로 초기화
    generated_questions = [] # 생성된 질문 리스트 초기화

    # --- 2. 경로(key)에 따라 분기 처리 ---
    if key.startswith('job-postings/') and key.endswith('.json'):
        # === 채용 공고 처리 ===
        print("[Info] 채용 공고 파일 감지됨. 질문 생성을 시작합니다.")
        try:
            # S3에서 파일 읽기
            response = s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            job_posting_data = json.loads(content)
            ideal_candidate_text = job_posting_data.get('idealCandidate')

            if not ideal_candidate_text:
                print(f"[Error] 'idealCandidate' 필드 누락 (파일: {key})")
                return {'statusCode': 400, 'body': "'idealCandidate' 필드 누락"}

            # Bedrock 호출
            generated_questions = generate_job_posting_questions(ideal_candidate_text)

            # 결과 저장
            if generated_questions:
                original_filename = key.split('/')[-1]
                base_filename = os.path.splitext(original_filename)[0] # 확장자 제거
                output_key = f"custom-questions/{base_filename}_questions.json"
                s3_client.put_object(
                    Bucket=bucket, Key=output_key,
                    Body=json.dumps(generated_questions, ensure_ascii=False, indent=2),
                    ContentType='application/json'
                )
                print(f"[Success] 채용 공고 질문 저장 완료: {output_key}")
            else:
                print("[Warn] 채용 공고 질문 생성 결과 없음.")

        except Exception as e:
            print(f"[Error] 채용 공고 처리 중 오류: {e}")
            return {'statusCode': 500, 'body': f'채용 공고 처리 오류: {str(e)}'}

    elif key.startswith('resumes/') and key.endswith('.json'):
        # === 이력서 처리 ===
        print("[Info] 이력서 파일 감지됨. 질문 생성을 시작합니다.")
        try:
            # S3에서 파일 읽기
            response = s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            # resume_data = json.loads(content) # resume_text_for_prompt 만 필요하므로 파싱 생략 가능
            resume_text_for_prompt = content # JSON 문자열 그대로 사용

            # Bedrock 호출
            generated_questions = generate_resume_questions(resume_text_for_prompt)

            # 결과 저장
            if generated_questions:
                original_filename = key.split('/')[-1]
                base_filename = os.path.splitext(original_filename)[0] # 확장자 제거
                output_key = f"resume-questions/{base_filename}_questions.json"
                s3_client.put_object(
                    Bucket=bucket, Key=output_key,
                    Body=json.dumps(generated_questions, ensure_ascii=False, indent=2),
                    ContentType='application/json'
                )
                print(f"[Success] 이력서 질문 저장 완료: {output_key}")
            else:
                print(f"[Warn] 이력서 질문 생성 결과 없음: {key}")

        except Exception as e:
            print(f"[Error] 이력서 처리 중 오류: {e}")
            return {'statusCode': 500, 'body': f'이력서 처리 오류: {str(e)}'}

    else:
        # === 처리 대상 아닌 경우 ===
        print(f"[Info] 처리 대상 파일 아님 (무시): {key}")
        return {'statusCode': 200, 'body': '처리 대상 아님'}

    # --- 3. 최종 성공 응답 ---
    return {
        'statusCode': 200,
        'body': json.dumps(f'S3 파일({key}) 처리 완료. 생성된 질문 파일: {output_key if generated_questions else "없음"}')
    }
