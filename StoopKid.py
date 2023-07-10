import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from rouge_score import rouge_scorer
import boto3
import time
import json
import os
import tempfile
from botocore.exceptions import ClientError
import datetime

# Define constants
COSINE_SIMILARITY_THRESHOLD = 0.8
ROUGE_L_THRESHOLD = 0.3
SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MyQueue'
ALERT_SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MySecondQueue'
S3_BUCKET_NAME = 'my-bucket'
BASELINE_FILE_KEY = 'baseline.csv'
MAX_PAYLOAD_SIZE = 1000000  # Define a suitable max payload size
RETRY_COUNT = 3  # Define a suitable retry count

# Initialize boto3 clients
s3 = boto3.client('s3')
sqs = boto3.client('sqs')

# Load the baseline DataFrame from S3
obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key=BASELINE_FILE_KEY)
baseline_df = pd.read_csv(obj['Body'])

def compute_rougeL_scores(df: pd.DataFrame, baseline_df: pd.DataFrame) -> pd.Series:
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    scores = df.apply(lambda row: scorer.score(row['summary'], baseline_df['reference_summary'])['rougeL'].fmeasure, axis=1)
    return scores

# Compute Rouge-L scores for the baseline dataframe once and reuse the result
baseline_rougeL_score = compute_rougeL_scores(baseline_df, baseline_df)

def trigger_alert_function(df):
    try:
        message = {
            'MessageBody': df.to_json(),
            'QueueUrl': ALERT_SQS_QUEUE_URL
        }
        sqs.send_message(**message)
    except Exception as e:
        print(f"Error sending message: {e}")
        raise

def split_dataframe(df, chunk_size=10000):  # Define a suitable chunk size
    chunks = [df[i:i+chunk_size] for i in range(0, df.shape[0], chunk_size)]
    return chunks

def process_data(df):
    def process_small_dataframe(df):
        # Add a timestamp to each message
        df['timestamp'] = datetime.datetime.now()

        # Store the dataframe in a persistent storage system (e.g., DynamoDB or S3)
        store_dataframe(df)

        # Retrieve all messages from the last 30 seconds
        start_time = datetime.datetime.now() - datetime.timedelta(seconds=30)
        df_last_30_seconds = retrieve_dataframe(start_time)

        # Calculate the cosine similarity for the last 30 seconds worth of messages
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(df_last_30_seconds['text'])
        cosine_sim = cosine_similarity(tfidf_matrix)

        if cosine_sim.mean() >= COSINE_SIMILARITY_THRESHOLD:
            df["rougeL_score"] = compute_rougeL_scores(df, baseline_df)
            if df['rougeL_score'].mean() < ROUGE_L_THRESHOLD:
                trigger_alert_function(df)

    # Check if the DataFrame is too large to process
    if df.memory_usage().sum() > MAX_PAYLOAD_SIZE:
        # If it's too large, split it into smaller DataFrames
        dfs = split_dataframe(df)
        for i, df_chunk in enumerate(dfs):
            try:
                process_small_dataframe(df_chunk)
            except Exception as e:
                print(f"Error processing chunk: {e}")
                raise
    else:
        process_small_dataframe(df)

def receive_message():
    response = sqs.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        AttributeNames=['All'],
        MaxNumberOfMessages=10,
        MessageAttributeNames=['All'],
        VisibilityTimeout=60,
        WaitTimeSeconds=20
    )
    return response

def lambda_handler(event, context):
    while True:
        try:
            response = receive_message()

            if 'Messages' in response:
                for message in response['Messages']:
                    receipt_handle = message['ReceiptHandle']

                    try:
                        body = json.loads(message['Body'])
                        df = pd.DataFrame(body)

                        process_data(df)

                        # Delete message after successful processing
                        sqs.delete_message(
                            QueueUrl=SQS_QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        raise
            else:
                # No more messages in the queue, terminate the function
                break
        except ClientError as e:
            print(f"Error receiving message: {e}")
            time.sleep(2**RETRY_COUNT)  # Exponential backoff
            RETRY_COUNT -= 1
            if RETRY_COUNT == 0:
                raise
