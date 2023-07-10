## Stoop Kid: Event Driven Input Monitoring for Language Models

### A set serverless functions designed to assist in the monitoring of inputs to languagement models, including routine and specific inspection of the message queue, and event-driven triggering of more complex metric calculation based on configurable condidtions

#
Rationale:

1) Large Language Models are subject to various forms of prompt injection (indirect or otherwise); lightweight and step-wise alerting of similar prompts compared to a baseline help your application stay secure
2) User experience is crucial to the adoption of LLMs for orchestration of multi-modal agentic systems; a high cosine similarity paired with a low rouge-L could indicate poor generalization, not just an attack
3) More to come

Note: Needs logging and error-handling; this is mostly conceptual at the moment
