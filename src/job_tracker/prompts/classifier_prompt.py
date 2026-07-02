from langchain_core.prompts import ChatPromptTemplate

CLASSIFIER_SYSTEM_PROMPT = """
You are an expert AI Classifier. Your task is to analyze an email and classify whether it is related to a job application.

Job application emails include:
- Confirmations of submitted applications.
- Interview invitations, schedulers, or confirmations.
- Technical assessments, coding tests, or assignment requests.
- Rejection letters.
- Job offers, negotiations, or onboarding.
- Direct correspondence with recruiters, hiring managers, or talent acquisition representatives about a specific role.

Non-job application emails include:
- General newsletter subscriptions or career advice (e.g. LinkedIn updates, Medium articles).
- Marketing or promotional spam from job boards (e.g. Glassdoor alerts, Indeed notifications "Jobs you might like").
- Personal emails or other unrelated business transactions.

You must respond with a JSON object containing:
1. "is_job_related": boolean (true if the email is directly related to a job application, false otherwise).
2. "confidence_score": float (from 0.0 to 1.0).
3. "reasoning": string (brief explanation of your decision).
"""

CLASSIFIER_USER_PROMPT = """
Analyze the following email:

Subject: {subject}
Sender: {sender}
Body:
{body}
"""

classifier_prompt = ChatPromptTemplate.from_messages([
    ("system", CLASSIFIER_SYSTEM_PROMPT),
    ("user", CLASSIFIER_USER_PROMPT)
])
