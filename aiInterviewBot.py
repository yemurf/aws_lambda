import json
import os
import requests

# 공통 질문 5개
COMMON_QUESTIONS = [
    "자기소개를 간단히 해주세요.",
    "본인의 강점과 약점을 말씀해주세요.",
    "왜 이 직무를 지원하셨나요?",
    "최근 프로젝트나 경험 중 가장 기억에 남는 것은 무엇인가요?",
    "5년 후 본인의 모습을 어떻게 상상하시나요?"
]

def lambda_handler(event, context):
    # ① API 키 확인
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"statusCode": 500, "body": json.dumps({"error": "OPENAI_API_KEY가 설정되지 않음"})}

    # ② 요청 데이터 파싱
    try:
        body = json.loads(event.get("body", "{}"))
    except Exception as e:
        return {"statusCode": 400, "body": json.dumps({"error": f"body 파싱 실패: {str(e)}"})}

    resume = body.get("resume", "이력서 정보 없음")
    job_type = body.get("job_type", "직무 미정")
    conversation = body.get("conversation", [])
    common_index = body.get("common_index", 0)
    job_index = body.get("job_index", 0)
    common_done = body.get("common_done", False)
    job_done = body.get("job_done", False)
    user_answer = body.get("user_answer", "").strip()

    # ③ 공통 질문 단계
    prompt = ""
    if not common_done:
        # 사용자가 답변한 경우 → AI 피드백 생성
        if user_answer:
            last_question = COMMON_QUESTIONS[common_index - 1] if common_index > 0 else COMMON_QUESTIONS[0]
            prompt = (
                f"너는 면접관이야. 아래 답변을 평가하고 부족한 점이 있다면 피드백과 꼬리 질문 1개만 해줘.\n\n"
                f"질문: {last_question}\n"
                f"답변: {user_answer}"
            )
        # 다음 질문 결정
        if common_index < len(COMMON_QUESTIONS):
            next_question = COMMON_QUESTIONS[common_index]
            common_index += 1
        else:
            common_done = True
            next_question = None
    else:
        next_question = None

    # ④ 직무 질문 단계
    if common_done and not job_done:
        if job_index == 0 and not user_answer:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "question": f"{job_type} 직무와 관련된 질문을 시작할게요. 이 직무를 선택한 이유는 무엇인가요?",
                    "common_done": True,
                    "job_index": 1
                })
            }
        elif user_answer:
            prompt = (
                f"너는 면접관이야. '{job_type}' 직무 면접 중이야. 아래 답변을 보고 적절한지 평가하고 부족하면 피드백과 꼬리 질문 1개만 해줘.\n\n"
                f"답변: {user_answer}"
            )

    # ⑤ 모든 질문이 끝난 경우
    if common_done and job_done:
        return {
            "statusCode": 200,
            "body": json.dumps({"question": "모든 질문이 끝났어요. 면접 준비 잘 하셨길 바랍니다!"})
        }

    # ⑥ AI 호출 (prompt가 있을 때만)
    ai_feedback = None
    if prompt:
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "너는 면접관이자 코치야. 응답은 항상 짧고 명확해야 해."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.6,
                    "max_tokens": 500
                },
                timeout=25
            )

            if response.status_code != 200:
                return {"statusCode": response.status_code, "body": json.dumps({"error": response.text})}

            result = response.json()
            ai_feedback = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        except Exception as e:
            ai_feedback = f"AI 호출 실패: {str(e)}"

    # ⑦ 반환
    return {
        "statusCode": 200,
        "body": json.dumps({
            "feedback_or_followup": ai_feedback,
            "question": next_question,
            "common_index": common_index,
            "job_index": job_index + 1 if common_done else job_index,
            "common_done": common_done,
            "job_done": job_done
        })
    }
