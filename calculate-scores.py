import boto3
import json
import os
import urllib.parse
from decimal import Decimal

# --- 1. 기본 설정 ---
BEDROCK_REGION = "us-east-1"
BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
DYNAMODB_TABLE_NAME = "InterviewScores"
# ---

# Boto3 클라이언트 및 리소스 초기화
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=BEDROCK_REGION)
dynamodb = boto3.resource('dynamodb', region_name=BEDROCK_REGION)
score_table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def lambda_handler(event, context):

    # 1. S3 이벤트 파싱
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        end_file_key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    except Exception as e: print(f"[Error] S3 이벤트 파싱 오류: {e}"); return {'statusCode': 400, 'body': 'S3 이벤트 파싱 오류'}
    print(f"[Info] 트리거 감지: {bucket}/{end_file_key}")

    # 2. jobId, applicantEmail 추출
    session_id = end_file_key.split('/')[1]
    try:
        response = s3_client.get_object(Bucket=bucket, Key=end_file_key)
        end_file_content = response['Body'].read().decode('utf-8')
        parts = end_file_content.split('|')
        if len(parts) != 2: raise ValueError("_END.txt 파일 내용 형식이 잘못되었습니다.")
        job_id = parts[0]
        applicant_email = parts[1]
    except Exception as e: print(f"[Error] _END.txt 파일 읽기/파싱 실패: {e}"); return {'statusCode': 400, 'body': '_END.txt 처리 오류'}
    print(f"[Info] 채점 시작: Session={session_id}, Job={job_id}, Applicant={applicant_email}")

    # 3. 채용 공고 로드
    try:
        job_posting_key = f"job-postings/{job_id}"
        response = s3_client.get_object(Bucket=bucket, Key=job_posting_key)
        job_posting_data = json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e: print(f"[Error] 채용 공고 로드 실패: {e}"); return {'statusCode': 500, 'body': '채용 공고 로드 오류'}

    # 4. 모든 답변 로드
    all_answers = []
    try:
        prefix = f"interview-sessions/{session_id}/"
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith("_answer.txt"):
                    answer_obj = s3_client.get_object(Bucket=bucket, Key=key)
                    answer_text = answer_obj['Body'].read().decode('utf-8')
                    question_id = key.split('/')[-1].replace('_answer.txt', '')
                    all_answers.append({"id": question_id, "answer": answer_text})
    except Exception as e: print(f"[Error] 답변 로드 실패: {e}"); return {'statusCode': 500, 'body': '답변 로드 오류'}

    answers_formatted_text = ""
    for ans in all_answers: answers_formatted_text += f"Q ({ans['id']}): {ans['answer']}\n"
    print(f"[Info] {len(all_answers)}개의 답변 로드 완료.")

    # (선택) 지원자 이름 가져오기
    applicant_name = "N/A"
    # try: ... except ...

    # --- 5. Bedrock 채점 프롬프트 ---
    criteria_text = f"""
    - 인재상(idealCandidate): {job_posting_data.get('idealCandidate', 'N/A')}
    - 주요 업무(jobDescription): {job_posting_data.get('jobDescription', 'N/A')}
    - 자격 요건(qualifications): {job_posting_data.get('qualifications', 'N/A')}
    """

    prompt = f"""Human: 당신은 채용 공고와 지원자의 면접 답변을 분석하여 평가 점수를 매기는 전문 HR 평가자입니다.
아래 <채용공고 기준>과 <지원자 답변>을 **엄격하게 비교**하여, 요청된 JSON 형식에 맞춰 **점수와 평가 의견**을 작성해야 합니다.
**절대 다른 설명이나 대화 없이, 오직 요청된 JSON 구조만 출력해야 합니다.**

<채용공고 기준>
{criteria_text}
</채용공고 기준>

<지원자 답변>
{answers_formatted_text}
</지원자 답변>

[출력 형식]
**반드시 다음 JSON 형식에 맞춰 모든 필드를 채워서 응답하세요:**
{{
  "overall_score": "100점 만점 기준 총점 (숫자만 입력, 예: 85)",
  "overall_comment": "채용 기준 대비 지원자 답변에 대한 1~2줄 요약 평가.",
  "strengths": "채용 기준과 비교 시 지원자의 강점 1~2가지 요약.",
  "weaknesses": "채용 기준과 비교 시 지원자의 약점 또는 부족한 점 1~2가지 요약.",
  "suitability_score": {{
      "ideal_candidate_fit": "인재상 적합도 점수 (1점에서 5점 사이 숫자만 입력)",
      "job_description_fit": "직무 적합도 점수 (1점에서 5점 사이 숫자만 입력)"
  }}
}}

Assistant:
"""
    # --- 프롬프트 끝 ---

    final_report = None
    try:
        body = { "anthropic_version": "bedrock-2023-05-31", "max_tokens": 2000, "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}] }
        response = bedrock_runtime.invoke_model( body=json.dumps(body), modelId=BEDROCK_MODEL_ID, accept='application/json', contentType='application/json')
        response_body = json.loads(response.get('body').read())
        scoring_result_text = response_body['content'][0]['text']

        # Bedrock 응답 파싱 (라인 115 근처 시작)
        try:
            # ```json 마크다운 제거 또는 시작이 { 인지 확인
            if "```json" in scoring_result_text:
                json_part = scoring_result_text.split("```json")[1].split("```")[0].strip()
            elif scoring_result_text.strip().startswith("{"):
                json_part = scoring_result_text.strip()
            else:
                # JSON 형식이 아닌 경우 오류 발생
                raise ValueError("Bedrock 응답에서 JSON 형식을 찾을 수 없습니다.")
            final_report = json.loads(json_part) # JSON 파싱
        except Exception as parse_e:
             print(f"[Error] Bedrock 응답 JSON 파싱 실패: {parse_e}, 응답 내용: {scoring_result_text[:500]}")
             # 파싱 실패 시, Bedrock 호출 오류로 처리하기 위해 에러 다시 발생
             raise parse_e

        print(f"[Info] Bedrock 채점 완료. 총점: {final_report.get('overall_score')}")

    except Exception as e:
        # Bedrock 호출 자체 실패 또는 위에서 발생시킨 파싱 에러 처리
        print(f"[Error] Bedrock 채점 호출 또는 JSON 파싱 오류: {e}")
        return {'statusCode': 500, 'body': 'Bedrock 채점 오류'}

    # 6. 최종 리포트 S3 저장
    try:
        report_key = f"interview-sessions/{session_id}/final_report.json"
        s3_client.put_object( Bucket=bucket, Key=report_key, Body=json.dumps(final_report, ensure_ascii=False, indent=2), ContentType='application/json')
        print(f"[Success] 최종 리포트 저장 완료: {report_key}")
    except Exception as e: print(f"[Error] S3 리포트 저장 실패: {e}")

    # 7. DynamoDB에 점수 저장
    try:
        overall_score_str = final_report.get('overall_score')
        if overall_score_str is None: raise ValueError("final_report에 'overall_score'가 없습니다.")
        try:
             # 점수 문자열에서 숫자만 추출하여 Decimal로 변환
             score_decimal = Decimal(str(overall_score_str).split('점')[0].strip())
        except Exception as decimal_e:
             print(f"[Error] 점수({overall_score_str}) Decimal 변환 실패: {decimal_e}")
             raise ValueError("overall_score를 숫자로 변환할 수 없습니다.")

        item_to_save = {
            'jobId': job_id, 'applicantEmail': applicant_email,
            'overallScore': score_decimal, 'applicantName': applicant_name,
            'reportS3Key': report_key
        }
        score_table.put_item(Item=item_to_save)
        print(f"[Success] DynamoDB 점수 저장 완료: {item_to_save}")
    except Exception as e: print(f"[Error] DynamoDB 점수 저장 실패: {e}")

    return {'statusCode': 200, 'body': '채점 및 저장 완료'}

