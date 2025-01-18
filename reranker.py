import os
import numpy as np
from typing import List, Dict, Union
from openai import OpenAI

# Define the input and output types
InputDict = Dict[str, Union[str, List[Dict[str, str]], str]]
OutputDict = Dict[str, Union[List[Dict[str, Union[str, float]]], str]]

def embed_and_rank(input_dict: InputDict, db: dict) -> OutputDict:
    query = input_dict["query"]
    items = input_dict["items"]
    mode = input_dict.get("mode", "math")  # Default mode is "math"

    # Initialize OpenAI client
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    # Get the embedding for the query
    query_embedding = client.embeddings.create(
        input=query,
        model="text-embedding-3-large"
    ).data[0].embedding

    ranked_items = []

    for item in items:
        content = item["content"]
        item_embedding = db[item["id"]]["resume_embedding"]

        if mode == "math":
            # Compute cosine similarity manually
            similarity = np.dot(query_embedding, item_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(item_embedding))
        else:
            # TODO: AI mode for ranking (use a generative model)
            similarity = 0.0  # Placeholder for AI mode computation

        ranked_items.append({
            "id": item["id"],
            "content": content,
            "finalScore": similarity
        })

    # Sort items by finalScore in descending order
    ranked_items.sort(key=lambda x: x["finalScore"], reverse=True)

    return {
        "items": ranked_items,
        "method": mode
    }
