# from langchain.document_loaders import PyPDFLoader  
import google.generativeai as genai
# from langchain.vectorstores import Chroma
from langchain.prompts import PromptTemplate
import os
import PyPDF2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import numpy as np
from GeminiModel import GeminiModel
import re
import requests
from bs4 import BeautifulSoup
import re


def cosine_similarity(a, b):
    return np.dot(a, b.T) / (np.linalg.norm(a, axis=1)[:, np.newaxis] * np.linalg.norm(b, axis=1))

def clean_text1(text):
    # Remove leading zeros in decimal numbers
    text = re.sub(r'(\d)0+(\.\d+)', r'\1\2', text)
    
    # Add missing commas in large numbers (e.g., converting "1234567890" to "1,234,567,890")
    text = re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1,', text)
    
    # Add other cleaning rules as needed
    
    return text

def pdf_to_string(file_path):
    pdf_file = open(file_path, 'rb')
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    total_pages = len(pdf_reader.pages)
    output = ''

    for page in pdf_reader.pages:
        page_text = page.extract_text() or '' 
        cleaned_page_text = clean_text1(page_text)
        output += cleaned_page_text

    pdf_file.close()
    return output

def limit_to_approx_words(sentence, limit=200, backtrack_limit=100):
    """
    Truncates a sentence to a specified limit of words, attempting to end with a full stop, question mark,
    or exclamation point within a backtrack limit if possible.
    
    Parameters:
    - sentence (str): The sentence to truncate.
    - limit (int, optional): The maximum number of words desired in the truncated sentence. Defaults to 200.
    - backtrack_limit (int, optional): The maximum number of words to backtrack through to find a suitable
      ending punctuation. Defaults to 100.
    
    Returns:
    - str: The truncated sentence, ideally ending with a complete sentence.
    """
    words = sentence.split()
    if len(words) <= limit:
        return sentence
    
    # Join words up to the limit, then strip to remove any leading or trailing whitespace.
    limited_text = " ".join(words[:limit]).strip()
    # Attempt to find a sentence-ending punctuation within the backtrack limit.
    for i in range(limit - 1, max(0, limit - backtrack_limit), -1):
        if words[i][-1] in ".!?":
            # Return the text up to and including the punctuation.
            return " ".join(words[:i + 1])
    
    # If no suitable punctuation is found, return the text up to the word limit.
    return limited_text


def clean_text(text):
    """
    Cleans the input text by removing newline characters and reducing all instances of multiple
    spaces to a single space.
    
    Parameters:
    - text (str): The input text to be cleaned.
    
    Returns:
    - str: The cleaned text with newline characters removed and multiple spaces reduced to a single space.
    """
    # Use regex to replace one or more whitespace characters (including spaces, tabs, and newlines)
    # with a single space, and then strip leading and trailing whitespace from the result.
    cleaned_text = re.sub(r'\s+', ' ', text).strip()
    return cleaned_text

def split_into_segments(sentence, limit = 200, backtrack_limit = 100):
    """
    Splits a long sentence into multiple smaller segments based on specified limits, ensuring
    segments end with complete sentences where possible.
    
    Parameters:
    - sentence (str): The long sentence to split.
    - limit (int): The approximate limit for the number of words in each segment.
    - backtrack_limit (int): The maximum number of words to backtrack in an effort to end a segment with complete sentences.
    
    Returns:
    - list: A list of sentence segments.
    """
    segments = []
    # Clean the sentence to remove excessive whitespace and newline characters.
    remaining_sentence = clean_text(sentence)
    
    while remaining_sentence:
        # Generate a segment that respects the limit and attempts to end with complete sentences.
        segment = limit_to_approx_words(remaining_sentence, limit, backtrack_limit)
        segments.append(segment)
        # Update the remaining sentence by removing the processed segment and leading spaces.
        remaining_sentence = remaining_sentence[len(segment):].lstrip()
        if not remaining_sentence:
            break
    return segments


load_dotenv()




class LLM_PDF_Backend:
    def __init__(self, filePath):
        self.GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=self.GOOGLE_API_KEY)
        self.document = pdf_to_string(filePath)
        self.model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
        self.chunks = split_into_segments(self.document)
        self.embedded_data = self.model.encode(self.chunks)
    
    def validate(self, question, answer):
        queries = [f"""Verify if the question and answer pair respectively is right or wrong. Return True if the answer is correct and in any other case return False. Answer only in Single word. 
                Question: {question}
                Answer: {answer}"""]
        embedded_queries = self.model.encode(queries)
        try:
            return bool(self.infer(queries, embedded_queries))
        except Exception as e:
            print(e)
            return False
    
    def getFlashCards(self):
        queries = ['Generate three question and answer respectively from the given context such that answer is in a single word in the json format: [{"question": "First generated question", "answer":"OneWordAnswer1}, {"question": "Second generated question", "answer":"OneWordAnswer2"}, {"question": "Third generated question", "answer": "OneWordAnswer2}] \n ask descriptive questions with answers in word not just number. ask one question with a number answer.']
        embedded_queries = self.model.encode(queries)
        print("infer problem ey idhi")
        return self.infer(queries, embedded_queries)
    
    def infer(self, queries, embedded_queries):
        GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")
        Gemini = GeminiModel(api_key = GOOGLE_API_KEY, model_name = "gemini-1.5-flash")
        print("ghemini loaded")
        for i, query_vec in enumerate(embedded_queries):
            similarities = cosine_similarity(query_vec[np.newaxis, :], self.embedded_data)
            print("similarities done")
            top_indices = np.argsort(similarities[0])[::-1][:3]
            print("top_indices done")
            top_doct = [self.chunks[index] for index in top_indices]
            print("top_doct done")
            print(f"Query : {queries[i]} Contexts : {top_doct[0]}")
            argumented_prompt = f"You are an expert question answering system, I will give you question and context and you will return the answer. Query : {queries[i]} Contexts : {top_doct[0]}"
            model_output = Gemini.generate_content(argumented_prompt)
            model_output = model_output.replace("```json", "")
            model_output = model_output.replace("```", "")
            print("Gemini.generate_content done:", model_output)
            print(type(model_output))
        return model_output
    
    def getCheckWebsite(self, url):
        title = get_page_title(url)
        queries = [f"""Check if the given title is any relevant to the given context. If the context is in any way related to the title return True, else return False. Answer in Single word only.
                   Title: {title}"""]
        
        embedded_queries = self.model.encode(queries)
        response = self.infer(queries, embedded_queries)
        try:
            return bool(response)
        except Exception as e:
            print(e)
            return False

def get_page_title(url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to get title for YouTube
            if 'youtube.com' in url:
                title = soup.find('meta', property='og:title')
                if title:
                    return title['content']
            
            # General title extraction
            title = soup.title.string if soup.title else None
            return title.strip() if title else "Title not found"
        except Exception as e:
            print(f"Error fetching website content: {e}")
            return None
