import os
import sys

if sys.platform == "win32":
    cuda_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin"
    if os.path.exists(cuda_path):
        try:
            os.add_dll_directory(cuda_path)
        except Exception:
            pass

from llama_cpp import Llama

from app.config import (
    LLM_MAX_TOKENS,
    LLM_MODEL_PATH,
    LLM_N_CTX,
    LLM_N_GPU_LAYERS,
    LLM_N_THREADS,
    LLM_TEMPERATURE,
)

_llm_instance = None


def get_llm():
    global _llm_instance
    if _llm_instance is None:
        print(f"Loading Mistral 7B model from {LLM_MODEL_PATH} (threads={LLM_N_THREADS})...")
        _llm_instance = Llama(
            model_path=LLM_MODEL_PATH,
            n_ctx=LLM_N_CTX,
            n_threads=LLM_N_THREADS,
            n_gpu_layers=LLM_N_GPU_LAYERS,
            verbose=False,
        )
        print("Mistral Loaded Successfully!")
    return _llm_instance


# Backwards compatibility alias
class _LLMProxy:
    def __call__(self, *args, **kwargs):
        return get_llm()(*args, **kwargs)

llm = _LLMProxy()


def _build_prompt(context, question, max_context_chars=2500):
    if len(context) > max_context_chars:
        context = context[:max_context_chars] + "\n...[context truncated]"

    return f"""[INST]
You are a helpful AI assistant.

Answer ONLY using the provided context.

If the answer is not available in the context, reply:
"I couldn't find that information in the document."

Context:
{context}

Question:
{question}
[/INST]
"""


def generate_answer(context, question, max_context_chars=2500):
    """Generate answer non-streamed."""
    prompt = _build_prompt(context, question, max_context_chars=max_context_chars)
    l = get_llm()
    output = l(
        prompt,
        max_tokens=LLM_MAX_TOKENS,
        temperature=LLM_TEMPERATURE,
        top_p=0.95,
        stop=["</s>"],
    )
    return output["choices"][0]["text"].strip()


def stream_answer(context, question, max_context_chars=2500):
    """Stream answer token by token."""
    prompt = _build_prompt(context, question, max_context_chars=max_context_chars)
    l = get_llm()
    response = l(
        prompt,
        max_tokens=LLM_MAX_TOKENS,
        temperature=LLM_TEMPERATURE,
        top_p=0.95,
        stop=["</s>"],
        stream=True,
    )
    for chunk in response:
        delta = chunk["choices"][0].get("text", "")
        if delta:
            yield delta
