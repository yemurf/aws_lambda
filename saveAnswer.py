import json

def lambda_handler(event, context):
    # 1. 'taskResult'에서 새로운 답변을 추출합니다.
    # 'Prepare Question and Wait' 단계의 출력 설정 때문에 답변이 여기에 들어옵니다.
    new_answer = event['taskResult']['answer']
    
    # 2. 기존 답변 리스트에 새로운 답변을 추가합니다.
    event['answers'].append(new_answer)
    
    # 3. 다음 질문으로 넘어가기 위해 인덱스를 1 증가시킵니다.
    event['current_index'] += 1
    
    # 4. 다음 루프를 위해 임시로 사용했던 'taskResult' 키를 삭제하여 데이터를 깔끔하게 유지합니다.
    del event['taskResult']
    
    # 5. 업데이트된 전체 면접 상태를 다음 단계(Is Interview Over?)로 전달합니다.
    return event
