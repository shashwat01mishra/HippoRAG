"""Smallest possible paid check of the OpenAI-compatible gateway: one chat call, one embedding call.

Prints each response's "model" field and token usage. The key is read from OPENAI_API_KEY in the
environment (load with `set -a; source .env; set +a`) and is never printed; error text is scrubbed.
The fallback chat ID is tried only if the gateway rejects the plain one.

    python experiments/smoke_test_gateway.py [--base_url https://api.aicredits.in/v1]
"""
import argparse
import os
import sys

from openai import OpenAI

parser = argparse.ArgumentParser()
parser.add_argument("--base_url", default="https://api.aicredits.in/v1")
args = parser.parse_args()

key = os.environ.get("OPENAI_API_KEY", "")
if not key:
    sys.exit("OPENAI_API_KEY is not set in this shell; run: set -a; source .env; set +a")


def scrub(err: Exception) -> str:
    return f"{type(err).__name__}: {str(err).replace(key, '<redacted>')}"[:400]


client = OpenAI(base_url=args.base_url, max_retries=0)

chat_ids = ["gpt-4o-mini", "openai/gpt-4o-mini-2024-07-18"]
for model_id in chat_ids:
    try:
        r = client.chat.completions.create(
            model=model_id, temperature=0, max_tokens=5,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        )
        print(f"CHAT  requested={model_id!r}  response.model={r.model!r}  "
              f"reply={r.choices[0].message.content!r}  usage=(in {r.usage.prompt_tokens}, out {r.usage.completion_tokens})")
        break
    except Exception as e:
        print(f"CHAT  requested={model_id!r}  FAILED  {scrub(e)}")
else:
    sys.exit("No chat model ID accepted.")

try:
    e = client.embeddings.create(model="text-embedding-3-small", input="hello")
    print(f"EMBED requested='text-embedding-3-small'  response.model={e.model!r}  "
          f"dim={len(e.data[0].embedding)}  usage=(in {e.usage.prompt_tokens})")
except Exception as err:
    sys.exit(f"EMBED FAILED  {scrub(err)}")
