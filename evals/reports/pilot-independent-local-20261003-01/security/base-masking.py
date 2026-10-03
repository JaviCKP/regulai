"""Strict transport contract for the mandatory company privacy barrier."""
import json
from urllib.parse import urlsplit

import requests

from .policy import digest


def mask_identity(config):
    return digest([config.api_url, config.detect, config.language])


def valid_masks(masks):
    """An empty or malformed chain cannot be treated as an identity transform."""
    try:
        return bool(masks) and all(
            config.active and config.detect == 'both'
            and urlsplit(config.api_url).scheme in {'http', 'https'}
            and bool(urlsplit(config.api_url).netloc)
            and not urlsplit(config.api_url).username and not urlsplit(config.api_url).password
            for config in masks
        )
    except ValueError:
        return False


def mask_texts(texts, masks, before_call=None, after_call=None, *, timeout=10):
    """Mask a structured batch atomically; never guess segment boundaries."""
    if not isinstance(texts, list) or not texts or any(not isinstance(text, str) for text in texts):
        raise ValueError('Invalid masking input')
    if not valid_masks(masks):
        raise ValueError('Required masking is not configured')
    current = texts
    for config in masks:
        value = json.dumps(current, ensure_ascii=False)
        payload = {'text': value, 'detect': ['pii', 'secrets']}
        if config.language:
            payload['language'] = config.language
        seconds = before_call(config, value) if before_call else timeout
        response = requests.post(config.api_url.rstrip('/') + '/api/mask', json=payload,
                                 timeout=seconds, allow_redirects=False)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get('masked'), str):
            raise ValueError('Invalid masking response')
        masked = json.loads(result['masked'])
        if not isinstance(masked, list) or len(masked) != len(current) or any(not isinstance(text, str) for text in masked):
            raise ValueError('Invalid masking segments')
        if after_call:
            after_call(config)
        current = masked
    return current
