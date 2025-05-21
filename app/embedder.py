from json import load
from langchain.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from langchain.schema import Document
from dotenv import load_dotenv
import os




def embed_sections(sections:list, index_dir:str, info:dict):
    documents = [Document(page_content=section) for section in sections]

    embedding = AzureOpenAIEmbeddings(
            model='text-embedding-3-large',
            azure_endpoint=info['endpoint'],
            api_key=info['key'],
            api_version=info['version'])
    vectorstore = FAISS.from_documents(documents, embedding)
    vectorstore.save_local(index_dir)


