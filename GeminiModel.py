import google.generativeai as genai

class GeminiModel:
    def __init__(self, api_key, model_name):
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": 0,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 30720,
        }
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ]
        self.model = genai.GenerativeModel(model_name=model_name,
                                           generation_config=generation_config,
                                           safety_settings=safety_settings)

    def generate_content(self, prompts):
        response = self.model.generate_content([prompts])
        return response.text
