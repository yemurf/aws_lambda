import json
import boto3

dynamodb = boto3.resource('dynamodb')
postings_table = dynamodb.Table('AI_Interview_Data')

def lambda_handler(event, context):
    job_posting_id = event['job_posting_id']

    response = postings_table.get_item(Key={'job_posting_id': job_posting_id})
    item = response.get('Item', {})

    company_q = item.get('company_questions', [])
    generated_q_dicts = item.get('generated_questions', [])
    generated_q = [q['question'] for q in generated_q_dicts]

    all_questions = company_q + generated_q

    # Step Functions에 전달할 결과물
    return {
        'job_posting_id': job_posting_id,
        'questions': all_questions,
        'question_count': len(all_questions),
        'answers': [],
        'current_index': 0
    }
