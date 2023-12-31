## ♫ The Dream of the 90's ♫ is alive in ~~Portland~~ ["a weird suite of Enterprise LLM tools"](https://github.com/users/rabbidave/projects/1) named after [Nicktoons](https://en.wikipedia.org/wiki/Nicktoons)
### by [some dude in his 30s](https://www.linkedin.com/in/davidisaacpierce)
#
## Utility 1) Stoop Kid: Serverless & Event Driven Input Monitoring for Language Models

![Stoop Kid](https://static.wikia.nocookie.net/heyarnold/images/a/a3/59e904f1d075f61ca93baa81.PNG/revision/latest?cb=20171105193956 "Stoop Kid")

## Description:
A set of serverless functions designed to assist in the monitoring of inputs to language models, including routine and specific inspection of the message queue, and event-driven triggering of more complex metric calculation based on continually configurable values (assuming use of an environment variable); subsequently alerts to another SQS queue

#
## Rationale:

1) Large Language Models are [subject to various forms of prompt injection](https://github.com/greshake/llm-security) ([indirect](https://github.com/greshake/llm-security#compromising-llms-using-indirect-prompt-injection) or otherwise); lightweight and step-wise alerting of similar prompts compared to a baseline help your application stay secure
2) User experience, instrumentation, and metadata capture are crucial to the adoption of LLMs for orchestration of [multi-modal agentic systems](https://en.wikipedia.org/wiki/Multi-agent_system); a high cosine similarity paired with a low rouge-L could indicate poor generalization, better prompt engineering for users, and/or an attack on the system

#
## Intent:

The intent of this StoopKid.py is to efficiently spin up, store and retrieve messages from an ElastiCache instance, thereby affecting a windowing function as a means to monitor the inputs to a language model. 

The goal being to detect if the model is starting to experience drift from the baseline loaded ROUGE-L (which should be regularly updated and stored in S3).
    
The ROUGE-L value is calculated intially from the baseline, and stored in memory. ROUGE-L is calculated for incoming messages only after comparing the cosine similarity of new messages in the dataframe to the last 5 minutes worth of messages; when complete the function spins down appropriately. 

The cosine similarity is used as a heuristic to detect similar inputs within the incoming dataframes to the last 5 minutes worth of messages (ostensibly to identify either poor generalization or attack), and the ROUGE-L score is used to more precisely compare the inputs with a baseline dataset; as a means of validating the assumption of the first function. 

If new inputs are found to be "too similar", and subsequently found to be drifting from the baseline, a message is posted to a second SQS queue for further analysis.

#
### Note: Needs logging and additional error-handling; this is mostly conceptual and assumes the use of environment variables rather than hard-coded values for cosine similarity & ROUGE-L
