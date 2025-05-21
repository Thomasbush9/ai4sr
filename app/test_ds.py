import os
from dotenv import load_dotenv
import dspy



load_dotenv()


lm = dspy.LM(f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT')}", api_key = os.getenv("AZURE_OPENAI_KEY"), api_base = os.getenv("AZURE_OPENAI_ENDPOINT"))

dspy.configure(lm=lm)
# define simple dspy module

lm("Say this is a test!", temperature=0.7)  # => ['This is a test!']
print(lm(messages=[{"role": "user", "content": "Say this is a test!"}]))
