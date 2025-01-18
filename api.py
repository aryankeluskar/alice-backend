import json
import re
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
import requests

from dotenv import load_dotenv
load_dotenv()
import os

from reranker import embed_and_rank

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

FILTERS = {
    "roles": ["Software Engineer", "Data Scientist", "Product Manager", "Data Engineer", "Machine Learning Engineer"],
    "locations": ["San Francisco", "New York", "Seattle", "Los Angeles", "Chicago", "Austin", "Boston", "Washington D.C.", "Atlanta", "Remote"],
    "experience": ["Student", "0-2 years", "2-5 years", "5-10 years", "10+ years"],
    "education": ["High School", "Bachelors", "Masters", "PhD"],
    "salary_range": ["$0-$50,000", "$50,000-$100,000", "$100,000-$150,000", "$150,000-$200,000", "$200,000-$250,000", "$250,000-$300,000", "$300,000-$350,000", "$350,000+"],
    "visa_sponsorship": ["Yes", "No"],
    "security_clearance": ["Yes", "No"],
}

def fetch_db():
    client = MongoClient(os.getenv("MONGO_CONNECTION_STRING_P1")+ os.getenv("MONGODB_USER_PWD") +os.getenv("MONGO_CONNECTION_STRING_P2"))
    db = client['insighthire']
    collection = db['resumes']

    data = {}
    for doc in collection.find():
        # print(doc)
        data[doc["_id"]] = doc

    client.close()
    return data
    
def top5_skills(query: str, skills: list) -> list:
    if len(skills) <= 5:
        return skills

    items = []
    for i, skill in enumerate(skills):
        items.append({
            "id": str(i),
            "content": skill
        })

    payload = {
        "query": query,
        "items": items,
        "excludeFactors": ["vectorScore", "semanticScore"],
        "mode": "math"
    }

    response = embed_and_rank(payload)
    
    output = []
    for item in response.json()["items"][:5]:
        output.append(item["content"])

    return output
    
def data_to_rerankformat(data: dict=None) -> list:
    if not data:
        raise ValueError("Data, in the form of a dict, must be provided.")

    rerank_data = []

    for key, value in data.items():
        rerank_data.append({
            "id": key,
            "content": str(value["resume_text"]),
            }
        )

    return rerank_data

def make_rerank_request(items, query, db) -> dict:
    print("Making rerank request... with items: ", len(items), " and query: ", query)

    query = query
    payload = {
        "query": query,
        "items": items,
        "excludeFactors": ["vectorScore", "semanticScore"],
        "mode": "math"
    }

    response = embed_and_rank(input_dict=payload, db=db)
    
    print("Rerank request completed.")

    try: 
        response["items"]
    except Exception as e:
        return {"error": str(e), "response": response}
    
    output = []

    for person in response["items"]:
        # print(f"ID: {person['id']} - Name: {file_data[person['id']]["full_name"]} - Score: {person['finalScore']}")
        output.append({
            "_id": person["id"],
            "full_name": db[person["id"]]["full_name"],
            "finalScore": person["finalScore"]
        })

    return {"items": output}

def save_job(query: str, search_result_ids: list) -> str:
    client = MongoClient(os.getenv("MONGO_CONNECTION_STRING_P1")+ os.getenv("MONGODB_USER_PWD") +os.getenv("MONGO_CONNECTION_STRING_P2"))
    db = client['insighthire']
    collection = db['jobs']

    result = collection.insert_one({"job_description": query, "selected_candidates": [], "search_result_ids": search_result_ids})
    client.close()

    return str(result.inserted_id)

def get_title(query: str) -> str:
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are an expert in job titles. Extract or generate the most appropriate professional job title from the job description. Respond with only the title."},
                {"role": "user", "content": query}
            ],
            "temperature": 0.3,
            "max_tokens": 50
        }
    )
    
    title = response.json()["choices"][0]["message"]["content"].strip()
    return title

@app.get("/")
async def root():
    DOCS = """InsightHire Query API

    POST /search
    {
        query: string
    }

    Returns:
    {
        "job_id": "67739d6131278e318a1d7a5d",
        "title": "Software Engineer",
        "results": [ 
            {
                "_id": "19",
                "full_name": "Aryan Vinod Keluskar",
                "finalScore": 0.33333333333333337,
                "data": {
                    "_id": "19",
                    "full_name": "Aryan Vinod Keluskar",
                    "current_role": "Undergraduate Researcher at Data Mining and Machine Learning Lab",
                    "skills": [
                        "Java",
                        "C++",
                        "Python",
                        "JavaScript",
                        "SQL"
                    ],
                    "summary": "Highly analytical and skilled student with a strong concentration in software and research, boosting performance rates through meticulous data handling and innovative solutions in several projects.",
                    "location": "Chandler, AZ, USA",
                    "student": true,
                    "graduation_date": "05/2026"
                }
            }, ... ]
    }
    

    POST /save_person_for_job
    {
        job_id: string,
        person_id: string
    }

    Returns:
    {
        "status": "success",
        "message": "Person added to job."
    }
    """
    return Response(content=DOCS, media_type="text/plain")


@app.post("/search")
async def search(query: str) -> dict:

    try:
        print(f"Query: {query}")
        db = fetch_db()
        print("Fetched data: ", len(db), db.keys())
        rerank_data = data_to_rerankformat(data=db)
        print("Converted data to rerank format ", len(rerank_data))
        rerank_output = make_rerank_request(items=rerank_data, query=query, db=db)

        if "error" in rerank_output:
            return rerank_output

        print("Fulfilled rerank request ", len(rerank_output["items"]))

        result_ids = [i["_id"] for i in rerank_output["items"]]
        if len(rerank_output["items"]) > 10:
            rerank_output["items"] = rerank_output["items"][:10]

        for i in rerank_output["items"]:
            i["data"] = db[i["_id"]]
            i["data"].pop("resume_text")
            i["data"].pop("resume_embedding")

        print("Completed processing data.")

        title = get_title(query)
        job_id = save_job(query=query, search_result_ids=result_ids)
        output = {
            "job_id": job_id,
            "title": title,
            "results": rerank_output["items"]
        }

        print("Completed processing output.")

        return output
    
    except Exception as e:
        return {"error": str(e)}

@app.post("/save_person_for_job")
async def save_person_for_job(job_id: str, person_id: str):
    try:
        client = MongoClient(os.getenv("MONGO_CONNECTION_STRING_P1")+ os.getenv("MONGODB_USER_PWD") +os.getenv("MONGO_CONNECTION_STRING_P2"))
        db = client['insighthire']
        collection = db['jobs']

        collection.update_one({"_id": job_id}, {"$push": {"selected_candidates": person_id}})
        client.close()
        return {"status": "success", "message": "Person added to job."}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@app.post("/get_more_results")
async def get_more_results(job_id: str):
    # route for getting more than 10 results
    pass

@app.get("/favicon.ico")
async def favicon():
    return FileResponse("./favicon.ico")