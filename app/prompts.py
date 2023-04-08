# flake8: noqa
from langchain.prompts import PromptTemplate

## Use a shorter template to reduce the number of tokens in the prompt

stuff_template = """Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

{context}

Question: {question}
Answer in {language}:"""

STUFF_PROMPT = PromptTemplate(
    input_variables=["context", "question", "language"],
    template=stuff_template
)

refine_template = (
    "The original question is as follows: {question}\n"
    "We have provided an existing answer: {existing_answer}\n"
    "We have the opportunity to refine the existing answer"
    "(only if needed) with some more context below.\n"
    "------------\n"
    "{context_str}\n"
    "------------\n"
    "Given the new context, refine the existing answer to better"
    "answer the question (in {language}) and keep the answer relevant to the question."
    "If the context isn't useful, return the existing answer."
)
REFINE_PROMPT =  PromptTemplate(
    input_variables=["question", "existing_answer", "context_str", "language"],
    template=refine_template,
)


refine_question_template = (
    "Context information is below. \n"
    "---------------------\n"
    "{context_str}"
    "\n---------------------\n"
    "Given the context information and not prior knowledge, "
    "answer the question (in {language}): {question}\n"
)

REFINE_QUESTION_PROMPT = PromptTemplate(
    input_variables=["context_str", "question", "language"], 
    template=refine_question_template,
)

detect_language_template = (
    "Given the paragraph below. \n"
    "---------------------\n"
    "{text}"
    "\n---------------------\n"
    "Detect the language that the text is writen and, "
    "return only the ISO 639-1 code of the language detected.\n"
)

DETECT_LANGUAGE_PROMPT = PromptTemplate(
    input_variables=["text"], 
    template=detect_language_template,
)