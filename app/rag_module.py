import dspy
from typing import List, Dict

class RAGModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_answer = dspy.ChainOfThought("question, context -> answer")

    def forward(self, question: str, context: List[Dict[str, str]]) -> str:
        # Format context for the model
        formatted_context = "\n\n".join([f"Document {i+1}:\n{chunk['text']}" 
                                       for i, chunk in enumerate(context)])
        
        # Generate answer using DSPy
        result = self.generate_answer(
            question=question,
            context=formatted_context
        )
        
        return result.answer 