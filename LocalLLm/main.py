import ollama

def chat_with_ollama():
    response = ollama.chat(model='qwen', messages=[
        {
            'role': 'user',
            'content': 'what is the maximum input of ollama qwen LLM. is it possible to use mistral to build an ATS?',
        },
    ])
    
    print("Ollama's Response:")
    print(response['message']['content'])

if __name__ == "__main__":
    chat_with_ollama()