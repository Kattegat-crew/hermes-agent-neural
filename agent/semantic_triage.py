"""Local semantic intent triage classifier using ONNX embeddings.

Evaluates user turn intent on CPU using fastembed with zero external API calls.
Determines whether a message is purely conversational or requires tool execution,
enforcing a strict Fail-Open policy: if in doubt, intent defaults to 'action'.
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Optional

logger = logging.getLogger(__name__)

_WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), "semantic_intent_weights.json")


class SemanticIntentClassifier:
    """Local, lightweight semantic intent triage classifier running on CPU via ONNX."""

    _instance: Optional["SemanticIntentClassifier"] = None

    def __init__(self, weights_path: str = _WEIGHTS_FILE) -> None:
        self._model = None
        self._coef: Optional[list[float]] = None
        self._intercept: float = 0.0
        self._load_weights(weights_path)

    @classmethod
    def get_instance(cls) -> "SemanticIntentClassifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_weights(self, weights_path: str) -> None:
        if not os.path.isfile(weights_path):
            logger.warning("Semantic intent weights file not found at %s", weights_path)
            return
        try:
            with open(weights_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._coef = data.get("coef")
            self._intercept = float(data.get("intercept", 0.0))
        except Exception as e:
            logger.error("Failed to load semantic intent weights: %s", e)

    def _get_model(self):
        if self._model is None:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    from fastembed import TextEmbedding

                    # Lazy load the ONNX embedding model
                    self._model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            except Exception as e:
                logger.warning("fastembed unavailable or failed to initialize: %s", e)
                self._model = False
        return self._model if self._model is not False else None

    def is_available(self) -> bool:
        return self._coef is not None and self._get_model() is not None

    def classify(self, text: str, action_probability_threshold: float = 0.50) -> str:
        """Classify user prompt into 'conversational' or 'action'.

        Fail-Open policy:
        If action probability exceeds threshold (default 0.50, score > 0), classify as 'action'.
        Only messages with conversational characteristics (score <= 0, prob < 0.50)
        are classified as 'conversational' to safely decouple tools.
        """
        if not text or not isinstance(text, str) or not text.strip():
            return "action"

        model = self._get_model()
        if model is None or self._coef is None:
            return "action"

        try:
            embs = list(model.embed([text.strip()]))
            if not embs:
                return "action"
            vec = embs[0]

            score = self._intercept + sum(w * float(v) for w, v in zip(self._coef, vec))
            prob_action = 1.0 / (1.0 + math.exp(-max(min(score, 30.0), -30.0)))

            if prob_action >= action_probability_threshold:
                return "action"
            return "conversational"
        except Exception as e:
            logger.warning("Error during semantic intent classification: %s; falling back to action", e)
            return "action"


def classify_semantic_intent(text: str) -> Optional[str]:
    """Public helper for turn intent triage. Returns None if semantic classifier is unavailable."""
    classifier = SemanticIntentClassifier.get_instance()
    if not classifier.is_available():
        return None
    return classifier.classify(text)
