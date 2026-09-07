from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

model = ChatAnthropic(model="claude-haiku-4-5-20251001")
response = model.invoke("Say hello in one sentence.")
print(response.content)
