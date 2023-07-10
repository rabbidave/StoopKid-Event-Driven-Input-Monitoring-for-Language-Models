# My thanks to all the 

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from rouge_score import rouge_scorer
import boto3
import time
import json

# Define constants
# Stoop Kid sits on his stoop all day, making sure he has correctly configured constants
QUEUE_SIZE_THRESHOLD = 100
TIME_WINDOW = 60 * 60
EVENT_THRESHOLD = 1000
COSINE_SIMILARITY_THRESHOLD = 0.8
ROUGE_L_THRESHOLD = 0.3
SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MyQueue'
ALERT_SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MySecondQueue'
S3_BUCKET_NAME = 'my-bucket'
BASELINE_FILE_KEY = 'baseline.csv'

# Initialize boto3 clients
# Stoop Kid also makes sure he's got runners, ears on the ground, and a way to get information out to the neighborhood
s3 = boto3.client('s3')
sqs = boto3.client('sqs')

# Load the baseline DataFrame from S3
# Stoop Kid knows the neighborhood and makes sure he drops the latest details in a storage layer that has downstream event hooks
obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key=BASELINE_FILE_KEY)
baseline_df = pd.read_csv(obj['Body'])

# Sometimes Stoop Kid needs to look closely at people walking by; some folks like to cause trouble
def compute_rougeL_scores(df: pd.DataFrame, baseline_df: pd.DataFrame) -> pd.Series:
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    scores = df.apply(lambda row: scorer.score(row['summary'], baseline_df['reference_summary'])['rougeL'].fmeasure, axis=1)
    return scores

# Sometimes Stoop Kid even needs to get off his stoop to help the neighborhood
def trigger_alert_function(df):
    message = {
        'MessageBody': df.to_json(),
        'QueueUrl': ALERT_SQS_QUEUE_URL
    }
    sqs.send_message(**message)

# Mostly Stoop Kid just sits on his stoop and watches folks go by, making sure they're not up to anything
def process_data(df):
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(df['text'])
    cosine_sim = cosine_similarity(tfidf_matrix)

    if cosine_sim.mean() >= COSINE_SIMILARITY_THRESHOLD:
        df["rougeL_score"] = compute_rougeL_scores(df, baseline_df)
        baseline_df["rougeL_score"] = compute_rougeL_scores(baseline_df, baseline_df)

        if df['rougeL_score'].mean() < ROUGE_L_THRESHOLD:
            trigger_alert_function(df)

# Stoop Kid also make sure he's correctly configured his timeouts and number of simultaneous events
def receive_message():
    response = sqs.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        AttributeNames=['All'],
        MaxNumberOfMessages=100,
        MessageAttributeNames=['All'],
        VisibilityTimeout=30,
        WaitTimeSeconds=20
    )
    return response

# Stoop Kid likes to correctly manage his serverless function based on the configured constants and conditional logic
def lambda_handler(event, context):
    last_processed_time = time.time()
    event_count = 0

    while True:
        response = receive_message()

        if 'Messages' in response:
            for message in response['Messages']:
                receipt_handle = message['ReceiptHandle']

                body = json.loads(message['Body'])
                df = pd.DataFrame(body)

                current_time = time.time()
                event_count += 1
                if len(df) >= QUEUE_SIZE_THRESHOLD or (current_time - last_processed_time) >= TIME_WINDOW or event_count >= EVENT_THRESHOLD:
                    process_data(df)
                    last_processed_time = current_time
                    event_count = 0

                # Delete message after successful processing
                sqs.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=receipt_handle
                )
        else:
            time.sleep(1)
