from json import load
from langchain import vectorstores
from langchain.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv
import os
load_dotenv()

def retrieve_top_k(query, index_dir=str:os.getenv('DATA'), k=5):
            embedding = AzureOpenAIEmbeddings(
            model='text-embedding-3-large',
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_KEY'),
            api_version=os.getenv('2025-01-01-preview'))
            vectorstore = FAISS.load_local(index_dir, embedding)
            return vectorstore.similarity_search(query, k=k)



