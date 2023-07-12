# My thanks to the open-source community; LLMs brought about a GNU revival
# My thanks to Arize AI in particular; y'all inspired this and other utilities with an awesome observability platform & sessions
# Note: This Lambda has a timeout to ensure it's spun down gracefully; manage your Lambda with Provisioned Concurrency to ensure SQS messages don't get missed

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
import redis
import pickle

# Define constants
COSINE_SIMILARITY_THRESHOLD = 0.8
ROUGE_L_THRESHOLD = 0.3
SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MyQueue'
ALERT_SQS_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/MySecondQueue'
S3_BUCKET_NAME = 'my-bucket'
BASELINE_FILE_KEY = 'baseline.csv'
MAX_PAYLOAD_SIZE = 1000000  # Define a suitable max payload size
RETRY_COUNT = 3  # Define a suitable retry count
REDIS_HOST = 'myelasticachecluster.eaorz8.ng.0001.use1.cache.amazonaws.com'  # Replace with your ElastiCache host
REDIS_PORT = 6379  # Replace with your ElastiCache port


# Initialize boto3 and redis clients
s3 = boto3.client('s3')
sqs = boto3.client('sqs')
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

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

def store_dataframe(df):
    # Convert DataFrame to bytes
    df_bytes = pickle.dumps(df)
    # Store bytes in Redis
    r.set(df['timestamp'].to_string(), df_bytes)

def retrieve_dataframe(start_time):
    # Get all keys in Redis
    keys = r.keys()
    df_list = []
    for key in keys:
        # Convert key to datetime
        key_datetime = datetime.datetime.strptime(key.decode(), '%Y-%m-%d %H:%M:%S.%f')
        # If key is within the last 5 minutes, retrieve the DataFrame
        if key_datetime >= start_time:
            df_bytes = r.get(key)
            df = pickle.loads(df_bytes)
            df_list.append(df)
    # Concatenate all DataFrames into one DataFrame
    df_last_5_minutes = pd.concat(df_list)
    return df_last_5_minutes

def process_data(df):
    def process_small_dataframe(df):
        # Add a timestamp to each message
        df['timestamp'] = datetime.datetime.now()

        # Store the dataframe in Redis
        store_dataframe(df)

        # Retrieve all messages from the last 5 minutes
        start_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
        df_last_5_minutes = retrieve_dataframe(start_time)

        # Calculate the cosine similarity for the last 5 minutes worth of messages
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(df_last_5_minutes['text'])
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
    start_time = time.time()

    while True:
        # Check if 10 minutes have passed
        if time.time() - start_time > 600:
            break

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
                        print(f'Error processing message: {e}')
                        raise
            else:
                # No more messages in the queue, terminate the function
                break
        except ClientError as e:
            print(f'Error receiving message: {e}')
            time.sleep(2**RETRY_COUNT)  # Exponential backoff
            RETRY_COUNT -= 1
            if RETRY_COUNT == 0:
                raise

