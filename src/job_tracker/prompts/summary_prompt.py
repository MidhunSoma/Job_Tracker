from langchain_core.prompts import ChatPromptTemplate

SUMMARY_SYSTEM_PROMPT = """
You are an expert AI Summarizer. Your task is to summarize the core details of a job application email thread.
Provide a concise, 1-2 sentence summary of what the email is about, including key deadlines, interview times, or action items if any.
"""

SUMMARY_USER_PROMPT = """
Summarize this email conversation:
Subject: {subject}
Body: {body}
"""

summary_prompt = ChatPromptTemplate.from_messages([
    ("system", SUMMARY_SYSTEM_PROMPT),
    ("user", SUMMARY_USER_PROMPT)
])
