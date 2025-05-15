import os
from dotenv import load_dotenv
import openai
from openai import AzureOpenAI
from openai.lib.azure import model_copy


env_path = os.path.join(os.path.dirname(__file__), "..", ".env")

# load env variables
load_dotenv(dotenv_path=env_path)

# configure the model

api_key = os.getenv("AZURE_OPENAI_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
version = os.getenv("AZURE_OPENAI_API_VERSION")

client = openai.AzureOpenAI(
        api_version=version,
        azure_endpoint=endpoint,
        api_key=api_key)


response = client.chat.completions.create(
        messages = [
                {"role":"system",
                 "content":"you are a helpful assinstant.",
                 },
                {
                    "role":"user",
                    "content":"Explain the main steps of a systematic review."
                },
            ],
        max_tokens=4096,
        temperature=1.0,
        top_p=1.0,
        model=deployment
    )
print("\n Response:\n", response.choices[0].message.content)
