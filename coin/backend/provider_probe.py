from dotenv import load_dotenv
load_dotenv('.env')
from intelligence.agents.groq_client import complete as groq
from intelligence.agents.openrouter_client import complete as openrouter
from intelligence.agents.gemini_client import complete as gemini
import requests
import os

for name, fn in [('groq', groq), ('openrouter', openrouter), ('gemini', gemini)]:
    try:
        result = fn('State one general risk for NVDA in under 20 words.')
        print(name, 'ok', len(result))
    except requests.HTTPError as exc:
        message = str(exc.response.json().get('error', {}).get('message', ''))
        for env_name in ('GROQ_API_KEY', 'GEMINI_API_KEY', 'OPENROUTER_DEBATE_API_KEY'):
            if os.getenv(env_name):
                message = message.replace(os.getenv(env_name), '[redacted]')
        print(name, 'http', exc.response.status_code, message[:200])
    except Exception as exc:
        print(name, type(exc).__name__)

response = requests.get('https://api.groq.com/openai/v1/models',
                        headers={'Authorization': 'Bearer ' + os.getenv('GROQ_API_KEY', '')}, timeout=10)
print('groq models', response.status_code,
      [item.get('id') for item in response.json().get('data', [])][:12])
os.environ['GEMINI_MODEL'] = 'gemini-3.8-flash'
try:
    print('gemini-3.8-flash', len(gemini('State one general risk for NVDA in under 20 words.')))
except requests.HTTPError as exc:
    print('gemini-3.8-flash status', exc.response.status_code)
os.environ['GEMINI_API_KEY'] = ''
try:
    print('gemini-secondary', len(gemini('State one general risk for NVDA in under 20 words.')))
except requests.HTTPError as exc:
    print('gemini-secondary status', exc.response.status_code)
