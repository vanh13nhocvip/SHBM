#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module xử lý hậu kỳ (Post-processing) cho văn bản tiếng Việt.
Tích hợp sửa lỗi chính tả, chuẩn hóa văn bản và NLP.
"""

import os
import re
import logging
import threading
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class VietnamesePostProcessor:
    """
    Hệ thống sửa lỗi và chuẩn hóa Tiếng Việt cho kết quả OCR.
    """
    
    def __init__(self, use_symspell: bool = True, use_nlp: bool = True, use_deep_learning: bool = False):
        self.use_symspell = use_symspell
        self.use_nlp = use_nlp
        self.use_deep_learning = use_deep_learning
        self.sym_spell = None
        self.tokenizer = None
        self.model = None
        self.mlm_pipeline = None
        
        if use_symspell:
            self._init_symspell()
            
        if use_nlp:
            self._init_nlp()
            
        if use_deep_learning:
            self.load_deep_learning_model()

    def _init_symspell(self):
        """Khởi tạo SymSpell với từ điển hành chính."""
        try:
            from symspellpy import SymSpell, Verbosity
            # Max edit distance 2, prefix length 7
            self.sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
            
            # Load dictionary
            dict_path = os.path.join(os.path.dirname(__file__), 'resources', 'admin_terms.txt')
            if os.path.exists(dict_path):
                # We assume a fixed high frequency for admin terms if not provided
                # SymSpell expect: term<space>count
                with open(dict_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        term = line.strip()
                        if term:
                            self.sym_spell.create_dictionary_entry(term, 1000) # High frequency for keywords
                logger.info(f"Loaded admin dictionary with high-priority terms from {dict_path}")
            else:
                logger.warning(f"Admin dictionary not found at {dict_path}")
                
        except ImportError:
            logger.warning("symspellpy không được cài đặt. Bỏ qua sửa lỗi chính tả.")
            self.use_symspell = False

    def _init_nlp(self):
        """Khởi tạo các công cụ NLP (underthesea, etc.)."""
        try:
            from underthesea import word_tokenize, ner
            self.tokenizer = word_tokenize
            self.ner = ner
            logger.info("Initialized underthesea for word segmentation and NER.")
        except ImportError:
            logger.warning("underthesea không được cài đặt. Bỏ qua các tác vụ NLP.")
            self.use_nlp = False

    def load_deep_learning_model(self):
        """Khởi tạo PhoBERT trong một luồng riêng."""
        thread = threading.Thread(target=self._init_deep_learning, daemon=True)
        thread.start()
        return thread

    def _init_deep_learning(self):
        """Khởi tạo PhoBERT để xử lý ngữ cảnh."""
        logger.info("Starting PhoBERT initialization...")
        try:
            from transformers import pipeline
            # Note: This will download several hundred MBs on first run
            model_name = "vinai/phobert-base"
            self.mlm_pipeline = pipeline("fill-mask", model=model_name, tokenizer=model_name)
            self.use_deep_learning = True
            logger.info(f"Successfully initialized Deep Learning model: {model_name}")
        except Exception as e:
            logger.error(f"Deep Learning initialization failed: {e}")
            self.use_deep_learning = False

    def correct_text(self, text: str, max_edit_distance: int = 1) -> str:
        """
        Thực hiện quy trình sửa lỗi cho văn bản (toàn bộ đoạn văn).
        """
        if not text:
            return ""
            
        # 1. Chuẩn hóa cơ bản
        text = self._basic_normalize(text)
        
        # 2. Xử lý sửa lỗi
        if self.use_symspell and self.sym_spell:
            # For long text, symspell has lookup_compound which handles multiple words/typos
            try:
                suggestions = self.sym_spell.lookup_compound(text, max_edit_distance=max_edit_distance)
                if suggestions:
                    text = suggestions[0].term
            except Exception as e:
                logger.error(f"Error during SymSpell lookup_compound: {e}")
                
        return text

    def correct_word(self, word: str) -> str:
        """Sửa lỗi cho 1 từ đơn lẻ (thường dùng cho metadata fields)."""
        if not self.use_symspell or not self.sym_spell or not word:
            return word
            
        from symspellpy import Verbosity
        # Use lookup for single word
        suggestions = self.sym_spell.lookup(word, Verbosity.TOP, max_edit_distance=1, include_unknown=True)
        if suggestions:
            return suggestions[0].term
        return word

    def suggest_next_words(self, text: str, top_k: int = 5) -> List[str]:
        """
        Gợi ý từ tiếp theo dựa trên ngữ cảnh (Sử dụng PhoBERT).
        """
        if not self.use_deep_learning or not self.mlm_pipeline:
            return []
            
        try:
            # PhoBERT uses <mask> token
            masked_text = text + " <mask>"
            results = self.mlm_pipeline(masked_text, top_k=top_k)
            return [res['token_str'].replace('@@', '') for res in results]
        except Exception as e:
            logger.error(f"Error in suggest_next_words: {e}")
            return []

    def _basic_normalize(self, text: str) -> str:
        """Chuẩn hóa cơ bản bằng Regex."""
        # Fix common OCR noise
        text = text.replace('–', '-').replace('—', '-')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

# Singleton instance
_post_processor = None

def get_post_processor() -> VietnamesePostProcessor:
    global _post_processor
    if _post_processor is None:
        _post_processor = VietnamesePostProcessor()
    return _post_processor
