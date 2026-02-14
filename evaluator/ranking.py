"""
Ranking Engine: use LLM to rank vehicles and return top 10.
"""
import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Lazy Groq client."""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError('Install groq: pip install groq')
    key = getattr(settings, 'GROQ_API_KEY', None) or ''
    if not key:
        raise ValueError('GROQ_API_KEY is not set in environment or Django settings.')
    return Groq(api_key=key)


def _vehicle_text(vehicle: dict) -> str:
    """Build a short text description for the LLM."""
    parts = [
        f"Name/Model: {vehicle.get('name') or 'N/A'}",
        f"Price (LKR): {vehicle.get('price') or 'N/A'}",
        f"Mileage (km): {vehicle.get('mileage') or 'N/A'}",
        f"Year: {vehicle.get('year') or 'N/A'}",
    ]
    desc = (vehicle.get('description') or '')[:800]
    if desc:
        parts.append(f"Description/Features: {desc}")
    return '\n'.join(parts)


def rank_vehicles_with_llm(vehicles: list[dict], model: str = 'llama-3.3-70b-versatile') -> list[dict]:
    """
    Use LLM to rank vehicles and return top 10 ranked vehicles.

    Args:
        vehicles: list of vehicle dicts with keys like 'name', 'price', 'mileage', 'year', 'description'
        model: Groq model to use

    Returns:
        list of top 10 vehicles (same structure as input, in ranked order)
    """
    if not vehicles:
        return []
    
    if len(vehicles) <= 10:
        # If 10 or fewer, just return all (no need to rank)
        return vehicles

    # Format vehicles for LLM
    vehicle_lines = []
    for i, vehicle in enumerate(vehicles):
        vehicle_text = _vehicle_text(vehicle)
        vehicle_lines.append(f"[Index {i}]\n{vehicle_text}")

    prompt = f"""You are a vehicle evaluation expert. Rank the following vehicles from best to worst based on:
- Overall value for money
- Condition and reliability
- Features and specifications
- Ownership experience
- Maintenance costs

Vehicles to rank (each starts with [Index N]):
{chr(10).join(vehicle_lines)}

Respond with ONLY a valid JSON object with one key:
"ranked_indices": array of exactly 10 integers representing the indices (0-{len(vehicles)-1}) of the top 10 vehicles in ranked order (best first).

No markdown, no extra text."""

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.3,
            max_tokens=512,
        )
        text = (response.choices[0].message.content or '').strip()
        # Strip markdown code block if present
        if text.startswith('```'):
            lines = text.split('\n')
            text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
        data = json.loads(text)
        ranked_indices = data.get('ranked_indices') or []
        
        if not isinstance(ranked_indices, list):
            ranked_indices = []
        
        # Validate and filter indices
        valid_indices = [int(x) for x in ranked_indices 
                        if isinstance(x, (int, float)) and 0 <= int(x) < len(vehicles)][:10]
        
        # If we don't have 10 valid indices, fill with remaining vehicles
        used_indices = set(valid_indices)
        while len(valid_indices) < 10 and len(valid_indices) < len(vehicles):
            for i in range(len(vehicles)):
                if i not in used_indices:
                    valid_indices.append(i)
                    used_indices.add(i)
                    break
        
        # Return vehicles in ranked order
        return [vehicles[i] for i in valid_indices[:10]]
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning('LLM ranking JSON parse failed: %s', e)
        # Fallback: return first 10 vehicles
        return vehicles[:10]
    except Exception as e:
        logger.exception('LLM ranking failed: %s', e)
        # Fallback: return first 10 vehicles
        return vehicles[:10]
