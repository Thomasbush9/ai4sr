import dspy

class RAGPrompt(dspy.Signature):
    """Answer a question using retireved context"""
    context:str
    question:str
    answer:str

qa_agent = dspy.Predict(RAGPrompt)
