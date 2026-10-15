"""Prompt Jinne - ask 10 questions, return a sharper prompt.

No login, no history: everything lives in st.session_state and is lost on refresh/reset.
"""
import os
from typing import Optional

import streamlit as st

st.set_page_config(page_title="Prompt Jinne", page_icon="🧞", layout="centered")

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(ellipse at 50% -15%, rgba(113, 194, 170, 0.13), transparent 48%),
            #f8faf9;
        color: #1c2925;
    }
    .block-container {
        max-width: 780px;
        padding-top: 1.5rem;
        padding-bottom: 4rem;
    }
    [data-testid="stHeader"] {
        background: transparent;
    }
    [data-testid="stChatMessage"] {
        border: 1px solid #e8eeeb;
        border-radius: 18px;
        padding: 1rem 1.15rem;
        margin-bottom: 0.9rem;
        background: rgba(255, 255, 255, 0.88);
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: #edf5f1;
        border-color: #dfebe5;
    }
    [data-testid="stChatInput"] {
        border-color: #d9e4de;
        border-radius: 18px;
        background: white;
    }
    [data-testid="stProgressBar"] > div > div {
        background-color: #23866b;
    }
    .brand {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        min-height: 2.7rem;
    }
    .brand-mark {
        display: grid;
        place-items: center;
        width: 2.6rem;
        height: 2.6rem;
        border-radius: 14px;
        background: #e4f2eb;
        font-size: 1.35rem;
    }
    .brand-title {
        color: #18362d;
        font-size: 1.12rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .brand-subtitle {
        color: #718079;
        font-size: 0.8rem;
        margin-top: 0.08rem;
    }
    @media (max-width: 640px) {
        .block-container {
            padding: 1rem 1rem 3rem;
        }
        [data-testid="stChatMessage"] {
            padding: 0.8rem 0.9rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

QUESTIONS = [
    ("task", "What should the AI actually **do**? One sentence."),
    ("goal", "What outcome do you want from it? (e.g., understand a topic, ship code, draft an email)"),
    ("context", "What should the AI know beforehand? (background, past attempts, key facts)"),
    ("audience", "Who reads the output? (e.g., beginners, executives, developers)"),
    ("tone", "What tone or style? (e.g., formal, friendly, concise)"),
    ("format", "What output format? (e.g., bullet list, table, code, email)"),
    ("length", "How long? (e.g., under 100 words, one page, detailed)"),
    ("constraints", "What should it avoid? (e.g., no jargon, Python only, no pricing advice)"),
    ("examples", "Any example of good output? Paste it, or skip."),
    ("success", "What would make the answer **good enough** for you?"),
]
TOTAL = len(QUESTIONS)


# ---------- prompt building ----------

def build_template_prompt(idea: str, a: dict) -> str:
    """Deterministic fallback: structures the answers into a clean prompt."""
    parts = [f"## Role & Goal\nYou are an expert helping with: {a.get('goal') or idea}."]
    if a.get("task"):
        parts.append(f"## Task\n{a['task']}")
    if a.get("context"):
        parts.append(f"## Context\n{a['context']}")
    if a.get("audience"):
        parts.append(f"## Audience\n{a['audience']}")

    style = [f"{label}: {a[key]}" for key, label in
             (("tone", "Tone"), ("format", "Format"), ("length", "Length")) if a.get(key)]
    if style:
        parts.append("## Style & Format\n" + "\n".join(f"- {s}" for s in style))

    if a.get("constraints"):
        parts.append(f"## Constraints\n{a['constraints']}")
    if a.get("examples"):
        parts.append(f"## Example of Good Output\n{a['examples']}")
    if a.get("success"):
        parts.append(f"## Success Criteria\n{a['success']}")

    parts.append("## Before Answering\nIf something essential is ambiguous, ask one clarifying "
                 "question first. Otherwise, proceed.")
    return "\n\n".join(parts)


def refine_with_llm(idea: str, draft: str) -> Optional[str]:
    """Optional polish via Anthropic API. Runs only if ANTHROPIC_API_KEY is set."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=os.getenv("PJ_MODEL", "claude-haiku-5-5"),
            max_tokens=1200,
            messages=[{
                "role": "user",
                "content": (
                    "Rewrite the draft prompt below so it is clear, precise and high quality. "
                    "Keep every requirement. Return only the final prompt, with no preamble.\n\n"
                    f"Original idea: {idea}\n\nDraft:\n{draft}"
                ),
            }],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip() or None
    except Exception as e:  # never break the app over an optional feature
        st.toast(f"AI polish unavailable, using template version. ({e})", icon="⚠️")
        return None


# ---------- state helpers ----------

def init_state():
    st.session_state.setdefault("final_prompt", "")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("stage", "idea")   # idea -> questions -> done
    st.session_state.setdefault("step", 0)
    st.session_state.setdefault("idea", "")
    st.session_state.setdefault("answers", {})
    if not st.session_state.messages:
        add(
            "assistant",
            "Hi, I'm Prompt Jinne 🧞. Share a rough idea or prompt, and I'll ask "
            "10 quick questions to help make it clearer and more useful.",
        )


def add(role: str, content: str):
    st.session_state.messages.append({"role": role, "content": content})


def question_text(i: int) -> str:
    return f"**Question {i + 1} of {TOTAL}:** {QUESTIONS[i][1]}"


def handle_input(text: str):
    text = text.strip()
    add("user", text)
    stage = st.session_state.stage

    if stage == "idea":
        st.session_state.idea = text
        st.session_state.stage = "questions"
        st.session_state.step = 0
        add("assistant", "Got it. Let's sharpen it with 10 quick questions.\n\n" + question_text(0))

    elif stage == "questions":
        key = QUESTIONS[st.session_state.step][0]
        st.session_state.answers[key] = text
        st.session_state.step += 1
        step = st.session_state.step

        if step < TOTAL:
            add("assistant", question_text(step))
        else:
            finish()


def finish():
    """Build the final prompt and switch to the done stage."""
    st.session_state.stage = "done"
    with st.spinner("Writing your refined prompt..."):
        idea = st.session_state.idea
        answers = st.session_state.answers
        draft = build_template_prompt(idea, answers)
        final = refine_with_llm(idea, draft) or draft
    st.session_state.messages.append({"role": "assistant", "content": "Here's your refined prompt — click the copy button:"})
    st.session_state.final_prompt = final
    st.session_state.messages.append({"role": "assistant", "content": "Paste it into any AI tool. Hit **Start over** to refine another one."})


# ---------- UI ----------

init_state()

brand, actions = st.columns([5, 1], vertical_alignment="center")
with brand:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-mark">🧞</div>
            <div>
                <div class="brand-title">Prompt Jinne</div>
                <div class="brand-subtitle">A better prompt starts with a few good questions</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with actions:
    if st.session_state.stage != "idea" and st.button("Start over", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.write("")
if st.session_state.stage == "questions":
    st.progress(st.session_state.step / TOTAL)
    st.caption(f"Question {st.session_state.step + 1} of {TOTAL}")
elif st.session_state.stage == "done":
    st.progress(1.0)
    st.caption("All 10 questions answered")

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🧞" if m["role"] == "assistant" else None):
        st.markdown(m["content"])

if st.session_state.stage == "idea":
    placeholder = "Paste or describe your prompt..."
elif st.session_state.stage == "questions":
    placeholder = "Type your answer (or 'skip')..."
else:
    placeholder = "Click Start over to begin again."

user_text = st.chat_input(placeholder, disabled=st.session_state.stage == "done")
if user_text and user_text.strip():
    handle_input(user_text)
    st.rerun()
