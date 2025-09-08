import os
from attachments.dspy import Attachments
import dspy
from pathlib import Path
from dotenv import load_dotenv
from typing import Literal, List

# let's try to load
load_dotenv()
csv_path = "/Users/thomasbush/Downloads/data_names.csv"
OPENAI_KEY = os.getenv("OPENAI_KEY")
lm = dspy.LM(model="openai/gpt-4o-mini", api_key=OPENAI_KEY)
dspy.configure(lm=lm)

class NameRefiner(dspy.Signature):
    """ Given the column of names categories extracted,
    Convert each name into one of the predefined classes"""

    document: Attachments = dspy.InputField()
    names: List = dspy.OutputField()





