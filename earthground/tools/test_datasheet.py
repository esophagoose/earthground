from langchain.chains.question_answering import load_qa_chain
from langchain_community.document_loaders import (PyPDFLoader,
                                                  UnstructuredPDFLoader)
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain_community.llms import OpenAI
from langchain_community.vectorstores import Chroma

# Replace book.pdf with any pdf of your choice
loader = UnstructuredPDFLoader("book.pdf")
pages = loader.load_and_split()
embeddings = OpenAIEmbeddings()
docsearch = Chroma.from_documents(pages, embeddings).as_retriever()

# Choose any query of your choice
query = "Who is Rich Dad?"
docs = docsearch.get_relevant_documents(query)
chain = load_qa_chain(OpenAI(temperature=0), chain_type="stuff")
output = chain.run(input_documents=docs, question=query)
print(output)
