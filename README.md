## Stoop Kid: Event Driven Input Monitoring for Language Models

### A set serverless functions designed to assist in the monitoring of inputs to language models, including routine and specific inspection of the message queue, and event-driven triggering of more complex metric calculation based on configurable condidtions

#
Rationale:

1) Large Language Models are subject to various forms of prompt injection (indirect or otherwise); lightweight and step-wise alerting of similar prompts compared to a baseline help your application stay secure
2) User experience is crucial to the adoption of LLMs for orchestration of multi-modal agentic systems; a high cosine similarity paired with a low rouge-L could indicate poor generalization, not just an attack
3) insert additional reasons this exists

Intent:

The intent of this script is to efficiently spin up, store and retrieve messages from a Redis Cache, thereby affecting a windowing function as a means to monitor the inputs to a language model. 

The goal being to detect if the model is starting to experience drift from the baseline loaded ROUGE-L (which is calculated from a batch updated baseline stored in S3, calculated, and then stored in memory for reuse), but only after comparing the cosine similarity of messages in the dataframe to the last 5 minutes worth of messages; when complete the function spins down appropriately. 

The cosine similarity is used as a heuristic to detect similar inputs within the incoming dataframes to the last 5 minutes worth of messages (ostensibly to identify either poor generalization or attack), and the ROUGE-L score is used to more precisely compare the inputs with a baseline dataset. 

The calculation of ROUGE-L for new dataframes is only triggered when a breach of cosine similarity is detected for the last 5 minutes worth of messages. If the inputs are found to be similar, and subsequently drifting from the baseline, a message is posted to a second SQS queue for further analysis.

Note: Needs logging and additional error-handling; this is mostly conceptual and assumes the use of environment variables rather than hard-coded values
