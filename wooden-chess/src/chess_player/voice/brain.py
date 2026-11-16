"""Local vision-language model (Qwen3.5, default 2B) for answering questions about the game and what the cameras see.

Loaded once in a background thread; ask() blocks until loaded. Images are downsized before going in (speed).
Thinking mode is off: answers are short and spoken aloud.
"""
import threading

import cv2
import numpy as np

from chess_player import config as C

SYSTEM = (
    "You are Robo, a chess-playing robot arm (an SO-101) with a dry, friendly sense of humour and a good understanding of chess. "
    "You play White against the person at the table. Stockfish chooses your moves and python-chess checks every rule; you never invent "
    "chess moves, evaluations or tactics yourself. Everything under 'Facts' or 'Game state' was computed by python-chess and Stockfish "
    "and is TRUE: repeat and explain it, never contradict it, and never judge a move that is not in the facts. "
    "When the facts call a human move a blunder, a mistake or an inaccuracy, say so plainly and, if the facts name Stockfish's preferred "
    "move, mention it. When the facts say a move is illegal (a foul), say it was not accepted, explain the reason given, and ask them to "
    "take it back and play a legal move. A great move deserves a compliment; a plain good move needs no comment. "
    "Your answers are spoken aloud: one or two short sentences, no lists, no markdown, no chess symbols like + or # (say 'check', 'checkmate'), "
    "say squares as letter and number ('e four'). When images are given, the first is your gripper camera (what your hand sees), the second is "
    "the webcam watching the whole board. Describe only what you can actually see, and say so when you are not sure; for the position of the "
    "pieces trust the game record in the facts over the picture."
)


class Brain:
    def __init__(self, model_id=C.VLM_MODEL):
        self.model_id = model_id
        self.ready = threading.Event()
        self.error = None
        self.lock = threading.Lock()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor

            kw = dict(dtype=torch.bfloat16, device_map="cuda" if torch.cuda.is_available() else "cpu")
            if C.VLM_4BIT:
                from transformers import BitsAndBytesConfig

                kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            self.model = AutoModelForImageTextToText.from_pretrained(self.model_id, **kw).eval()
            self.torch = torch
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            print(f"[brain] could not load {self.model_id}: {self.error}", flush=True)
        finally:
            self.ready.set()

    @property
    def status(self):
        if not self.ready.is_set():
            return "loading"
        return "error" if self.error else "ready"

    @staticmethod
    def _img(frame_bgr):
        from PIL import Image

        h, w = frame_bgr.shape[:2]
        s = C.VLM_IMAGE_WIDTH / w
        small = cv2.resize(frame_bgr, (C.VLM_IMAGE_WIDTH, int(h * s)))
        return Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))

    def ask(self, question, context="", images=(), max_new_tokens=70, names=("gripper camera", "webcam")):
        """`images` in the order of `names`; a None entry = that camera has no picture right now."""
        self.ready.wait()
        if self.error:
            return "My language brain didn't load, so I can only follow commands right now."
        content, have, missing = [], [], []
        for name, f in zip(names, images):
            if f is not None and np.size(f):
                content.append({"type": "image", "image": self._img(f)})
                have.append(name)
            else:
                missing.append(name)
        cams = (f"Images attached, in order: {', '.join(have)}. " if have else "No camera images are attached. ")
        if missing:
            cams += (f"The {' and the '.join(missing)} {'has' if len(missing) == 1 else 'have'} no picture right now: if "
                     f"asked about it, say it is not available. Never describe what you cannot see. ")
        content.append({"type": "text", "text": cams + (f"Game state: {context}\n\n" if context else "\n") + question})
        msgs = [{"role": "system", "content": [{"type": "text", "text": SYSTEM}]}, {"role": "user", "content": content}]
        with self.lock:
            inputs = self.processor.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                                        return_dict=True, return_tensors="pt",
                                                        enable_thinking=False).to(self.model.device)
            with self.torch.inference_mode():
                out = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=True, temperature=0.7,
                                          top_p=0.9)
            text = self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        return clean(text, C.VOICE_ANSWER_SENTENCES)


def clean(text, max_sentences=2):
    """Strip leftover thinking tags / markdown and keep the first sentences, so it reads well aloud."""
    import re

    if "</think>" in text:
        text = text.split("</think>")[-1]
    for ch in "*#`_":
        text = text.replace(ch, "")
    text = " ".join(text.split()).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:max_sentences])
