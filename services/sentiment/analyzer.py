#!/usr/bin/env python3
"""
Sentiment Analyzer - Uses FinBERT for financial sentiment analysis
"""
import torch
import logging
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import re
from typing import Dict, List

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyzes sentiment of financial text using FinBERT model."""

    def __init__(self, model_name: str = "ProsusAI/finbert", batch_size: int = 20):
        """Initialize sentiment analyzer.

        Args:
            model_name: HuggingFace model name
            batch_size: Number of texts to process in one batch
        """
        self.model_name = model_name
        self.batch_size = batch_size

        logger.info(f"Loading sentiment model: {model_name}")

        # Load tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)

        # Move to GPU if available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()  # Set to evaluation mode

        logger.info(f"✅ Model loaded on device: {self.device}")

    def preprocess_text(self, text: str) -> str:
        """Clean and normalize text before sentiment analysis.

        Args:
            text: Raw text to preprocess

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove URLs
        text = re.sub(r'http\S+|www.\S+', '', text)

        # Remove mentions (@user)
        text = re.sub(r'@\w+', '', text)

        # Remove hashtag symbol but keep text
        text = re.sub(r'#(\w+)', r'\1', text)

        # Remove excess whitespace
        text = ' '.join(text.split())

        # Lowercase
        text = text.lower()

        return text

    def analyze(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of a single text.

        Args:
            text: Text to analyze

        Returns:
            Dict with sentiment scores and overall score
        """
        # Preprocess
        clean_text = self.preprocess_text(text)

        if not clean_text:
            return {
                "score": 0.0,
                "positive": 0.33,
                "negative": 0.33,
                "neutral": 0.34,
                "confidence": 0.34
            }

        # Tokenize
        inputs = self.tokenizer(
            clean_text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True
        )

        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Get probabilities
        probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]

        # FinBERT outputs: [positive, negative, neutral]
        positive = float(probs[0])
        negative = float(probs[1])
        neutral = float(probs[2])

        # Calculate overall score (-1 to +1)
        score = positive - negative

        # Confidence is the max probability
        confidence = float(max(probs))

        return {
            "score": score,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "confidence": confidence
        }

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, float]]:
        """Analyze sentiment of multiple texts in batch.

        Args:
            texts: List of texts to analyze

        Returns:
            List of sentiment result dicts
        """
        if not texts:
            return []

        # Preprocess all texts
        clean_texts = [self.preprocess_text(text) for text in texts]

        # Handle empty texts
        results = []
        valid_indices = []
        valid_texts = []

        for i, text in enumerate(clean_texts):
            if text:
                valid_indices.append(i)
                valid_texts.append(text)
            else:
                results.append({
                    "score": 0.0,
                    "positive": 0.33,
                    "negative": 0.33,
                    "neutral": 0.34,
                    "confidence": 0.34
                })

        if not valid_texts:
            return results

        # Tokenize batch
        inputs = self.tokenizer(
            valid_texts,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True
        )

        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Get probabilities
        probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()

        # Process results
        batch_results = []
        for prob in probs:
            positive = float(prob[0])
            negative = float(prob[1])
            neutral = float(prob[2])

            score = positive - negative
            confidence = float(max(prob))

            batch_results.append({
                "score": score,
                "positive": positive,
                "negative": negative,
                "neutral": neutral,
                "confidence": confidence
            })

        # Merge results back (handling empty texts)
        final_results = []
        valid_idx = 0

        for i in range(len(texts)):
            if i in valid_indices:
                final_results.append(batch_results[valid_idx])
                valid_idx += 1
            else:
                final_results.append({
                    "score": 0.0,
                    "positive": 0.33,
                    "negative": 0.33,
                    "neutral": 0.34,
                    "confidence": 0.34
                })

        return final_results
